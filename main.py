from __future__ import annotations

import logging
import os
import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from agent.registry import seed_tokens
from database import SessionLocal, initialize_database
from routers import actions, auth, chat, pages

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    with SessionLocal() as db:
        seed_tokens(db)
    yield


app = FastAPI(title="Stocktalk", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=(
        os.getenv("STOCKTALK_SECRET_KEY")
        or os.getenv("FLASK_SECRET_KEY")
        or secrets.token_urlsafe(32)
    ),
    same_site="lax",
    https_only=os.getenv("COOKIE_HTTPS_ONLY", "0").strip().lower()
    in {"1", "true", "yes"},
)
app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)
app.include_router(pages.router)
app.include_router(auth.router)
app.include_router(chat.router)
app.include_router(actions.router)


@app.exception_handler(404)
async def handle_not_found(_request: Request, _exc: Exception):
    return RedirectResponse("/", status_code=302)


if not os.getenv("STOCKTALK_SECRET_KEY") and not os.getenv("FLASK_SECRET_KEY"):
    logger.warning(
        "No persistent session secret configured; wallet sessions will reset on restart."
    )
