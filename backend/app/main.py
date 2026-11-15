import time

_started = time.perf_counter()  # before the app's imports, to time them

import logging  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import SessionLocal, init_db  # noqa: E402
from app.routers.api import router  # noqa: E402
from app.seed.items import sync_items  # noqa: E402
from app.seed.seed import sync_bank  # noqa: E402

log = logging.getLogger("uvicorn.error")
_imported = time.perf_counter()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Timed, because on Vercel this runs on every cold start; printed so it shows in Vercel's logs.
    steps = {"imports": _imported - _started}
    t = time.perf_counter()
    init_db()
    steps["migrations"] = time.perf_counter() - t
    if get_settings().seed_on_startup:
        with SessionLocal() as db:
            t = time.perf_counter()
            log.info("Vocabulary bank synced: %s", sync_bank(db))
            steps["word bank"] = time.perf_counter() - t
            t = time.perf_counter()
            log.info("Question bank synced: %s", sync_items(db))
            steps["question bank"] = time.perf_counter() - t
    print("Startup: " + ", ".join(f"{k} {v:.2f}s" for k, v in steps.items()), flush=True)
    yield


app = FastAPI(title="GRE Prep API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


# /health for Docker; /api/health is the path Vercel routes to this service.
@app.get("/health")
@app.get("/api/health")
def health():
    return {"ok": True}
