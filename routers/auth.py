from __future__ import annotations

import re
import time

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import JSONResponse

from services.auth import build_siwe_message, generate_nonce, verify_signature

router = APIRouter(prefix="/api/auth", tags=["auth"])
WALLET_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def normalize_wallet(value: str | None) -> str | None:
    if not value:
        return None
    wallet = value.strip()
    if not WALLET_RE.fullmatch(wallet):
        return None
    return wallet.lower()


def require_wallet(
    request: Request | WebSocket, request_wallet: str | None = None
) -> tuple[str | None, JSONResponse | None]:
    session_wallet = normalize_wallet(request.session.get("wallet"))
    requested_wallet = normalize_wallet(request_wallet)
    if not session_wallet or not requested_wallet or session_wallet != requested_wallet:
        return None, JSONResponse(
            {"error": "Sign in with your wallet first."}, status_code=401
        )
    return session_wallet, None


@router.post("/nonce")
async def api_auth_nonce(request: Request):
    payload = await request.json()
    wallet = normalize_wallet(payload.get("wallet"))
    if not wallet:
        return JSONResponse({"error": "valid wallet is required"}, status_code=400)

    nonce = generate_nonce()
    message = build_siwe_message(wallet, nonce)
    request.session["auth_nonce"] = nonce
    request.session["auth_wallet"] = wallet
    request.session["auth_expires"] = int(time.time()) + 300
    return {"message": message, "nonce": nonce}


@router.post("/verify")
async def api_auth_verify(request: Request):
    payload = await request.json()
    wallet = normalize_wallet(payload.get("wallet"))
    message = payload.get("message")
    signature = payload.get("signature")
    if not wallet or not message or not signature:
        return JSONResponse(
            {"error": "wallet, message, and signature are required"},
            status_code=400,
        )

    auth_nonce = request.session.get("auth_nonce")
    auth_wallet = request.session.get("auth_wallet")
    auth_expires = request.session.get("auth_expires")
    if not auth_nonce or not auth_wallet or not auth_expires:
        return JSONResponse(
            {"error": "No pending sign-in request."}, status_code=400
        )

    if time.time() > float(auth_expires):
        request.session.pop("auth_nonce", None)
        request.session.pop("auth_wallet", None)
        request.session.pop("auth_expires", None)
        return JSONResponse(
            {"error": "Sign-in nonce expired. Please try again."}, status_code=400
        )

    if auth_wallet.lower() != wallet.lower():
        return JSONResponse({"error": "Wallet mismatch."}, status_code=400)
    if auth_nonce not in message or wallet.lower() not in message.lower():
        return JSONResponse(
            {"error": "Message does not match expected nonce or wallet."},
            status_code=400,
        )
    if not verify_signature(wallet, message, signature):
        return JSONResponse({"error": "Invalid signature."}, status_code=400)

    request.session["wallet"] = wallet
    request.session.pop("auth_nonce", None)
    request.session.pop("auth_wallet", None)
    request.session.pop("auth_expires", None)
    return {"ok": True, "wallet": wallet}


@router.get("/me")
async def api_auth_me(request: Request):
    wallet = normalize_wallet(request.session.get("wallet"))
    if not wallet:
        return JSONResponse(
            {"error": "Sign in with your wallet first."}, status_code=401
        )
    return {"wallet": wallet}


@router.post("/logout")
async def api_auth_logout(request: Request):
    for key in ("wallet", "auth_nonce", "auth_wallet", "auth_expires"):
        request.session.pop(key, None)
    return {"ok": True}
