import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _parse_admin_ids(raw: str | None) -> frozenset[int]:
    if not raw:
        return frozenset()
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    return frozenset(int(x) for x in parts)


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_model: str
    admin_telegram_ids: frozenset[int]


def load_settings() -> Settings:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not token:
        raise RuntimeError("Missing TELEGRAM_BOT_TOKEN")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return Settings(
        telegram_bot_token=token,
        openai_api_key=key,
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip(),
        admin_telegram_ids=_parse_admin_ids(os.environ.get("ADMIN_TELEGRAM_IDS")),
    )
