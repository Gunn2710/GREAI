# TODO

- [x] CI pipeline (GitHub Actions): backend tests, frontend lint + build
- [x] Host frontend on Vercel
- [x] Host backend on Vercel (move migrations and word-bank sync out of startup into a deploy step)
- [x] Use Supabase's Session pooler string for Docker and Vercel (direct connection is IPv6-only)
- [x] Add phrases to each word: always the most common way the word is actually used (e.g. "widely lauded", "laud someone for something"), not made-up combos
- [ ] More example sentences per word (3–4, different contexts)
- [x] Home page (with different sections)
- [ ] Clerk production instance
- [x] Grow the word bank to 1000
- [x] Reading Comprehension
- [ ] Mock test mode
- [x] Quant section
- [ ] Writing section
- [ ] Streaks and reminders
- [ ] Make it phone screen compatible
- [x] Add simple github action CI to check for secret safety
- [x] Per user Chat history after refresh
- [x] Simplify backend tests
- [x] New/Old word leaning
- [ ] Add RBAC/user tiers and change Clerk restrictions

## Agent

Groundwork
- [x] Streamed coach replies
- [x] Per-user daily limits on Claude usage
- [x] Prompt caching for the coach
- [ ] Model choice: Haiku for small jobs (daily brief, note-taking)
- [ ] Log of coach actions, with undo
- [ ] Behavior checks: saved conversations run against the fake Claude (no early answers, stays on topic, only changes things after you confirm)

Actions, confirmed with a button
- [x] Drill my mix-ups: a short session on the word pairs you keep confusing
- [x] Bring back misses: make words you got wrong due again now
- [x] "I already know this one": mark a word as known
- [x] Change study settings: new word frequency, study mode, daily new words
- [x] Send you to the right practice type
- [x] Save "your sentence" from the chat, with feedback

Memory
- [x] Coach notes: facts it keeps between chats, which you can see and delete
- [ ] Explanations shaped by your preferences (roots, mnemonics)

Speaks up first
- [ ] Daily brief on Home
- [ ] Debrief after a study session
- [ ] Pace warnings against the test date
- [ ] Weekly review

Multi-step planning
- [ ] "Plan my week" / "plan until my test", with plan vs actual on the dashboard
- [ ] Pace and starting set suggested after the placement check

Teaching in the study loop
- [ ] Why your answer was wrong: contrast with the word you picked
- [ ] Step-by-step hints
- [ ] Custom reading passages with your words (costs the most; later)
