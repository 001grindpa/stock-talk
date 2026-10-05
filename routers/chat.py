from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from agent.graph import run_agent
from database import get_db
from routers.auth import normalize_wallet, require_wallet

router = APIRouter()
logger = logging.getLogger(__name__)


async def _run_chat(
    payload: dict[str, Any], session_wallet: str | None, db: Session
) -> tuple[dict[str, Any], int]:
    message = payload.get("message")
    message = message.strip() if isinstance(message, str) else ""
    if not message:
        return {"error": "message is required"}, 400

    wallet = normalize_wallet(payload.get("wallet"))
    if wallet:
        if not session_wallet or session_wallet != wallet:
            return {"error": "Sign in with your wallet first."}, 401

    balances = payload.get("balances")
    if not isinstance(balances, list):
        balances = []
    thread_id = payload.get("thread_id")
    thread_id = thread_id.strip() if isinstance(thread_id, str) else ""
    result = await run_agent(
        db=db,
        message=message,
        wallet=wallet,
        balances=balances,
        thread_id=thread_id or "page-session",
        history=[],
    )
    return {
        "message": result.get("message") or "",
        "action": result.get("action") or {"type": "none"},
    }, 200


@router.post("/api/chat")
async def api_chat(request: Request, db: Session = Depends(get_db)):
    payload = await request.json()
    result, status_code = await _run_chat(
        payload, normalize_wallet(request.session.get("wallet")), db
    )
    return JSONResponse(result, status_code=status_code)


async def _send_progress(websocket: WebSocket) -> None:
    await asyncio.sleep(5)
    await websocket.send_json({"type": "status", "text": "Still thinking…"})
    await asyncio.sleep(10)
    await websocket.send_json({"type": "status", "text": "Gathering resources…"})
    await asyncio.sleep(10)
    await websocket.send_json({"type": "status", "text": "Finalizing…"})


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    session_wallet = normalize_wallet(websocket.session.get("wallet"))
    try:
        payload = await websocket.receive_json()
        if not isinstance(payload, dict):
            await websocket.send_json(
                {"type": "error", "status": 400, "error": "Invalid chat request."}
            )
            return

        message = payload.get("message")
        if not isinstance(message, str) or not message.strip():
            await websocket.send_json(
                {"type": "error", "status": 400, "error": "message is required"}
            )
            return
        if normalize_wallet(payload.get("wallet")):
            _, error = require_wallet(websocket, payload.get("wallet"))
            if error:
                await websocket.send_json(
                    {
                        "type": "error",
                        "status": 401,
                        "error": "Sign in with your wallet first.",
                    }
                )
                return

        await websocket.send_json({"type": "status", "text": "Thinking…"})
        progress_task = asyncio.create_task(_send_progress(websocket))
        try:
            result, _ = await _run_chat(payload, session_wallet, db)
        finally:
            progress_task.cancel()
            try:
                await progress_task
            except asyncio.CancelledError:
                pass
        await websocket.send_json({"type": "final", **result})
    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("WebSocket chat failed")
        try:
            await websocket.send_json(
                {"type": "error", "status": 500, "error": "Chat failed."}
            )
        except WebSocketDisconnect:
            return
