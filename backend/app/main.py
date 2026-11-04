import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.routers.api import router
from app.seed.items import sync_items
from app.seed.seed import sync_bank

log = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    if get_settings().seed_on_startup:
        with SessionLocal() as db:
            log.info("Vocabulary bank synced: %s", sync_bank(db))
            log.info("Question bank synced: %s", sync_items(db))
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


@app.get("/health")
def health():
    return {"ok": True}
