"""Download Telegram-hosted files via Bot API (async)."""

import httpx
from aiogram import Bot


async def fetch_file_bytes(bot: Bot, file_id: str) -> tuple[bytes, str]:
    """Return file bytes and Telegram `file_path` (for MIME guessing)."""
    tg_file = await bot.get_file(file_id)
    if not tg_file.file_path:
        raise RuntimeError("Telegram returned empty file_path")
    path = tg_file.file_path
    url = f"https://api.telegram.org/file/bot{bot.token}/{path}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content, path


def guess_image_mime(file_path: str) -> str:
    p = file_path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
