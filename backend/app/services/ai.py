"""Claude-powered features: the coach's agent loop, usage grading, mnemonics.

Every prompt is grounded in the word's verified data from the database so the
model explains *our* answer key instead of inventing its own.
"""
import inspect
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

import anthropic
from fastapi import HTTPException, status

from app.config import get_settings
from app.secrets_config import get_secrets
from app.models import Word
from app.services.limits import current_meter

log = logging.getLogger(__name__)

FALLBACK_BETA = "server-side-fallback-2026-07-01"

USAGE_SYSTEM = """You grade whether a student used a GRE vocabulary word correctly
in a sentence they wrote. Judge meaning and nuance, not style. A sentence is
correct only if the word is used with its proper meaning and part of speech and
the context makes that meaning plausible. Minor typos elsewhere do not matter.
Feedback must be one or two sentences addressed to the student."""

USAGE_SCHEMA = {
    "type": "object",
    "properties": {
        "correct": {"type": "boolean"},
        "score": {"type": "number", "description": "0.0 to 1.0"},
        "feedback": {"type": "string"},
        "improved_sentence": {"type": "string"},
    },
    "required": ["correct", "score", "feedback", "improved_sentence"],
    "additionalProperties": False,
}

MNEMONIC_SYSTEM = """You write memorable, accurate mnemonics for GRE words.
Return one mnemonic of at most two sentences: a sound-alike or vivid image that
links the word's sound to its meaning. No preamble."""


def word_entry(word: Word) -> str:
    return json.dumps(
        {
            "word": word.lemma,
            "part_of_speech": word.pos,
            "definition": word.definition,
            "nuance": word.nuance,
            "common_phrases": word.phrases,
            "examples": word.examples,
            "synonyms": word.synonyms,
            "antonyms": word.antonyms,
            "often_confused_with": word.confusables,
        },
        indent=2,
    )


class AIUnavailable(HTTPException):
    def __init__(self, detail: str, code: int = status.HTTP_503_SERVICE_UNAVAILABLE):
        super().__init__(code, detail)


class ClaudeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: anthropic.AsyncAnthropic | None = None

    @property
    def enabled(self) -> bool:
        return self.settings.ai_enabled

    @property
    def client(self) -> anthropic.AsyncAnthropic:
        if self._client is None:
            key = get_secrets().anthropic_api_key
            # No key here: the SDK falls back to the environment or an `ant auth login` profile.
            self._client = anthropic.AsyncAnthropic(api_key=key.get_secret_value()) if key else anthropic.AsyncAnthropic()
        return self._client

    def _ready(self, params: dict) -> dict:
        """Check AI is on and add the server's fallback settings."""
        if not self.enabled:
            raise AIUnavailable("AI features are disabled on this server")
        if self.settings.claude_fallbacks:
            params |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        return params

    @staticmethod
    def _failure(exc: anthropic.APIError) -> AIUnavailable:
        """What the student sees when the API call fails."""
        if isinstance(exc, anthropic.AuthenticationError):
            return AIUnavailable("Claude API credentials are missing or invalid")
        if isinstance(exc, anthropic.RateLimitError):
            return AIUnavailable("AI is busy, try again shortly", status.HTTP_429_TOO_MANY_REQUESTS)
        if isinstance(exc, anthropic.BadRequestError):
            log.error("Claude rejected request: %s", exc.message)
            return AIUnavailable("AI request was rejected", status.HTTP_502_BAD_GATEWAY)
        if isinstance(exc, anthropic.APIStatusError):
            log.error("Claude API error %s (request %s)", exc.status_code, exc.request_id)
            return AIUnavailable("AI service error, try again")
        return AIUnavailable("Could not reach the AI service")

    @staticmethod
    def _record(response) -> object:
        """Add the call's tokens to the student's request in progress (see services/limits.py)."""
        meter = current_meter.get()
        if meter is not None:
            meter.add(getattr(response, "usage", None))
        if response.stop_reason == "refusal":
            raise AIUnavailable("The AI declined this request", status.HTTP_422_UNPROCESSABLE_ENTITY)
        return response

    async def _create(self, **params) -> object:
        """One Messages API call, with the server's model, effort and fallbacks."""
        params = self._ready(params)
        try:
            return await self.client.beta.messages.create(model=self.settings.claude_model, **params)
        except anthropic.APIError as exc:
            raise self._failure(exc) from exc

    async def _turn(self, **params) -> AsyncIterator[tuple[str, object]]:
        """One streamed Messages API call: yields ("text", delta) as the reply is written, then
        ("message", the final message)."""
        params = self._ready(params)
        try:
            async with self.client.beta.messages.stream(model=self.settings.claude_model, **params) as stream:
                async for text in stream.text_stream:
                    yield "text", text
                response = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise self._failure(exc) from exc
        yield "message", response

    @staticmethod
    def _text(response) -> str:
        return "".join(b.text for b in response.content if b.type == "text").strip()

    async def _complete(
        self,
        system: str,
        messages: list[dict],
        *,
        max_tokens: int = 2000,
        effort: str = "low",
        schema: dict | None = None,
    ) -> str:
        output_config: dict = {"effort": effort}
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        response = self._record(await self._create(
            max_tokens=max_tokens, system=system, messages=messages, output_config=output_config,
        ))
        return self._text(response)

    async def agent(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        run_tool: Callable[[str, dict], Awaitable[str] | str],
        *,
        max_tokens: int = 2000,
        max_steps: int = 6,
        effort: str = "low",
    ) -> AsyncIterator[tuple[str, str]]:
        """Let Claude call `tools` (run by `run_tool`) until it writes its reply, streaming as it goes.

        Yields ("text", delta) while the reply is written, ("tool", name) when a tool runs, and
        finally ("reply", the whole reply). The stable system prompt and tool definitions are
        cached, and so is the conversation up to the latest student or tool-result message.
        """
        system_blocks = [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
        messages = list(messages)
        parts: list[str] = []
        for step in range(max_steps + 1):
            last = step == max_steps  # out of steps: answer with what it has
            params = dict(max_tokens=max_tokens, system=system_blocks, messages=_cache_latest(messages),
                          tools=tools, output_config={"effort": effort})
            if last:
                params["tool_choice"] = {"type": "none"}
            text, response = "", None
            async for kind, value in self._turn(**params):
                if kind == "text":
                    if not text and any(parts):
                        yield "text", "\n\n"
                    text += value
                    yield "text", value
                else:
                    response = value
            parts.append(text.strip())
            self._record(response)
            if response.stop_reason != "tool_use" or last:
                break
            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                yield "tool", block.name
                try:
                    out = run_tool(block.name, block.input or {})
                    out = await out if inspect.isawaitable(out) else out
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
                except Exception as exc:  # report the failure to Claude rather than the student
                    log.warning("Tool %s failed: %s", block.name, exc)
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": f"Tool error: {exc}", "is_error": True})
            messages.append({"role": "user", "content": results})
        yield "reply", "\n\n".join(p for p in parts if p)

    async def check_usage(self, word: Word, sentence: str) -> dict:
        prompt = (
            f"<word_entry>\n{word_entry(word)}\n</word_entry>\n\n"
            f"<student_sentence>\n{sentence}\n</student_sentence>\n\n"
            f"Did the student use \"{word.lemma}\" correctly?"
        )
        text = await self._complete(
            USAGE_SYSTEM,
            [{"role": "user", "content": prompt}],
            max_tokens=2000,
            effort="medium",
            schema=USAGE_SCHEMA,
        )
        result = json.loads(text)
        result["score"] = max(0.0, min(1.0, float(result.get("score", 0.0))))
        return result

    async def mnemonic(self, word: Word) -> str:
        prompt = f"<word_entry>\n{word_entry(word)}\n</word_entry>\n\nWrite a mnemonic for \"{word.lemma}\"."
        return await self._complete(MNEMONIC_SYSTEM, [{"role": "user", "content": prompt}], max_tokens=1000)


def _cache_latest(messages: list[dict]) -> list[dict]:
    """A copy of `messages` with a cache breakpoint on the latest student or tool-result
    message, so the next call (the next tool step or the next question) reuses it."""
    out = list(messages)
    for i in range(len(out) - 1, -1, -1):
        if out[i]["role"] != "user":
            continue
        content = out[i]["content"]
        blocks = [{"type": "text", "text": content}] if isinstance(content, str) else [dict(b) for b in content]
        blocks[-1]["cache_control"] = {"type": "ephemeral"}
        out[i] = {**out[i], "content": blocks}
        break
    return out


claude = ClaudeService()
