"""Read-only Base JSON-RPC helpers. Never signs and never holds keys."""

from __future__ import annotations

import os

import httpx

ERC20_BALANCE_OF = "0x70a08231"
ERC20_ALLOWANCE = "0xdd62ed3e"


def rpc_url() -> str:
    return os.getenv("BASE_RPC_URL") or "https://mainnet.base.org"


def _pad_address(address: str) -> str:
    return address.lower().replace("0x", "").rjust(64, "0")


def _eth_call(to: str, data: str) -> str | None:
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": to, "data": data}, "latest"],
    }
    try:
        response = httpx.post(rpc_url(), json=payload, timeout=20.0)
        response.raise_for_status()
        return response.json().get("result")
    except Exception:
        return None


def _decode_uint(result: str | None) -> int | None:
    if not result or result == "0x":
        return None
    try:
        return int(result, 16)
    except ValueError:
        return None


def token_balance(token: str, owner: str) -> int | None:
    data = ERC20_BALANCE_OF + _pad_address(owner)
    return _decode_uint(_eth_call(token, data))


def token_allowance(token: str, owner: str, spender: str) -> int | None:
    data = ERC20_ALLOWANCE + _pad_address(owner) + _pad_address(spender)
    return _decode_uint(_eth_call(token, data))
