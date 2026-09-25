import secrets
from datetime import datetime, timezone

from eth_account import Account
from eth_account.messages import encode_defunct


def generate_nonce() -> str:
    """Generate a 32-character hexadecimal nonce (16 bytes)."""
    return secrets.token_hex(16)


def build_siwe_message(address: str, nonce: str) -> str:
    """
    Build sign-in message matching:
    Stocktalk
    Sign in to prove you own this Base wallet.
    Address: 0x…
    Nonce: <32 hex>
    Issued at: ISO-8601 UTC
    """
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        "Stocktalk\n"
        "Sign in to prove you own this Base wallet.\n"
        f"Address: {address}\n"
        f"Nonce: {nonce}\n"
        f"Issued at: {issued_at}"
    )


def verify_signature(address: str, message: str, signature: str) -> bool:
    """
    Verify signature using encode_defunct and Account.recover_message.
    The recovered address must match the claimed address (case-insensitive).
    """
    if not address or not message or not signature:
        return False
    try:
        signable = encode_defunct(text=message)
        recovered = Account.recover_message(signable, signature=signature)
        if recovered and recovered.lower() == address.lower():
            return True

        if "\r" in message:
            signable_norm = encode_defunct(text=message.replace("\r\n", "\n").replace("\r", "\n"))
            recovered_norm = Account.recover_message(signable_norm, signature=signature)
            if recovered_norm and recovered_norm.lower() == address.lower():
                return True
        else:
            signable_crlf = encode_defunct(text=message.replace("\n", "\r\n"))
            recovered_crlf = Account.recover_message(signable_crlf, signature=signature)
            if recovered_crlf and recovered_crlf.lower() == address.lower():
                return True
        return False
    except Exception:
        return False
