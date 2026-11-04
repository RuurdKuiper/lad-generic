"""Authenticated account clients shared by current BYOD publishing tools."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "byod-gemma-2-9b": "gemma",
    "byod-llama-3.1-8b": "llama",
    "byod-qwen2.5-7b": "qwen",
    "byod-ministral-8b": "ministral",
}


def accounts():
    from dotenv import load_dotenv
    from huggingface_hub import HfApi
    from huggingface_hub.utils._auth import get_stored_tokens

    load_dotenv(ROOT / ".env")
    dove = get_stored_tokens().get("BYOD-update")
    if not dove:
        raise RuntimeError("Saved Dovelove deployment credential not found")
    result = {
        "Ruurd": HfApi(token=os.getenv("HF_TOKEN")),
        "Dovelove": HfApi(token=dove),
    }
    for owner, api in result.items():
        if api.whoami()["name"].casefold() != owner.casefold():
            raise RuntimeError("Credential account mismatch: " + owner)
    return result
