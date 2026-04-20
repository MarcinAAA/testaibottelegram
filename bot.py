import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject, User
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from config import Settings, load_settings
from openai_client import reply_chat, reply_chat_with_image
from pdf_extract import extract_pdf_text
from telegram_file import fetch_file_bytes, guess_image_mime


def _openai_user_message(exc: Exception) -> str:
    if isinstance(exc, AuthenticationError):
        return (
            "OpenAI rejected the API key (401). Check OPENAI_API_KEY in .env — "
            "https://platform.openai.com/api-keys"
        )
    if isinstance(exc, RateLimitError):
        return (
            "OpenAI returned 429 — usually **no quota / billing not enabled**.\n"
            "Add a payment method or credits: https://platform.openai.com/account/billing\n"
            "(Free trial credits may be used up.)"
        )
    if isinstance(exc, APIConnectionError):
        return "Could not reach OpenAI. Check your internet and try again."
    if isinstance(exc, APIError):
        return f"OpenAI error: {getattr(exc, 'message', str(exc))}"
    return f"Unexpected error: {type(exc).__name__}: {exc}"


TELEGRAM_TEXT_SAFE = 4000  # under Telegram’s 4096 limit


async def send_model_reply(message: Message, text: str) -> None:
    """Send possibly long model output in chunks."""
    t = (text or "").strip()
    if not t:
        await message.answer("(empty model response)")
        return
    while t:
        await message.answer(t[:TELEGRAM_TEXT_SAFE])
        t = t[TELEGRAM_TEXT_SAFE:]


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant in Telegram (ChatGPT-style).
Answer clearly and step-by-step when the user asks how-to questions.
Detect the user's language from their message and reply in the same language.
For screenshots, UI images, or documents: describe what you see and answer the user's question.
Keep answers concise unless the user asks for detail."""

MAX_UPLOAD_BYTES = 18 * 1024 * 1024  # under Telegram's ~20 MB limit

router = Router()


class SettingsMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings) -> None:
        super().__init__()
        self.settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self.settings
        return await handler(event, data)


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Hi! I’m an AI assistant powered by OpenAI.\n\n"
        "• Send text — natural conversation, any language.\n"
        "• Send a photo / screenshot — I’ll analyze the image (add a caption if you have a question).\n"
        "• Send a PDF — I’ll read the text and answer (caption optional).\n\n"
        "Commands: /help, /rephrase (reply to my message), /escalate (notify admins)."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Text — chat in any language (matched to the user’s language).\n"
        "Photo / screenshot — vision analysis; optional caption = your question.\n"
        "PDF — text extraction + answer; scanned-only PDFs may not work.\n\n"
        "/rephrase — reply to my answer, then send /rephrase for a simpler version.\n"
        "/escalate — notify admins (set ADMIN_TELEGRAM_IDS). Reply to a message before "
        "/escalate to include context.\n\n"
        "Uses OpenAI Chat Completions (multimodal). Use a vision-capable model in .env "
        "(default gpt-4o-mini)."
    )


def _format_user_label(user: User) -> str:
    if user.username:
        return f"@{user.username}"
    name = (user.full_name or "").strip() or "unknown name"
    return f'"{name}" (no @username set in Telegram)'


@router.message(Command("escalate"))
async def cmd_escalate(message: Message, settings: Settings) -> None:
    if not settings.admin_telegram_ids:
        await message.answer("Escalation is not configured (no ADMIN_TELEGRAM_IDS).")
        return
    if message.from_user is None:
        await message.answer("Cannot escalate: missing sender info.")
        return
    text = message.text or ""
    who = _format_user_label(message.from_user)
    header = f"Escalation from user {message.from_user.id} ({who}) in chat {message.chat.id}\n\n"
    context = ""
    if message.reply_to_message:
        rm = message.reply_to_message
        if rm.text:
            context = f"\n\n--- User replied to this message ---\n{rm.text[:6000]}"
        elif rm.caption:
            context = f"\n\n--- User replied to media caption ---\n{rm.caption[:6000]}"
    body = header + text + context
    for admin_id in settings.admin_telegram_ids:
        try:
            await message.bot.send_message(admin_id, body[:4090])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to notify admin %s: %s", admin_id, exc)
    await message.answer("Your message was forwarded to admins.")


@router.message(F.reply_to_message, Command("rephrase"))
async def cmd_rephrase(message: Message, settings: Settings) -> None:
    rm = message.reply_to_message
    if rm is None:
        await message.answer("Reply to one of my text messages, then send /rephrase.")
        return
    original = (rm.text or rm.caption or "").strip() or None
    if not original:
        await message.answer("Reply to a message that contains text (my answer), then send /rephrase.")
        return
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Rewrite the following assistant answer in simpler words and shorter sentences. "
        "Keep the same language as the text.\n\n" + original
    )
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        text = reply_chat(client, settings.openai_model, SYSTEM_PROMPT, prompt)
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        logger.warning("OpenAI error in /rephrase: %s", exc)
        await message.answer(_openai_user_message(exc))
        return
    await send_model_reply(message, text)


@router.message(F.photo)
async def on_photo(message: Message, settings: Settings) -> None:
    if not message.photo:
        return
    photo = message.photo[-1]
    if photo.file_size and photo.file_size > MAX_UPLOAD_BYTES:
        await message.answer("Image too large for this bot (try under ~18 MB).")
        return
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        data, path = await fetch_file_bytes(message.bot, photo.file_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram download failed: %s", exc)
        await message.answer("Could not download the image. Please try again.")
        return
    mime = guess_image_mime(path)
    caption = (message.caption or "").strip()
    user_part = (
        caption
        if caption
        else (
            "The user sent an image or screenshot with no caption. "
            "Describe what you see and give helpful, step-by-step guidance if relevant."
        )
    )
    client = OpenAI(api_key=settings.openai_api_key)
    try:
        text = reply_chat_with_image(
            client, settings.openai_model, SYSTEM_PROMPT, user_part, data, mime
        )
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        logger.warning("OpenAI error in on_photo: %s", exc)
        await message.answer(_openai_user_message(exc))
        return
    await send_model_reply(message, text)


@router.message(F.document)
async def on_document(message: Message, settings: Settings) -> None:
    doc = message.document
    if doc is None:
        return
    if doc.file_size and doc.file_size > MAX_UPLOAD_BYTES:
        await message.answer("File too large (max ~18 MB for this bot).")
        return
    mime = (doc.mime_type or "").lower()
    name = (doc.file_name or "").lower()

    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        data, path = await fetch_file_bytes(message.bot, doc.file_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Telegram document download failed: %s", exc)
        await message.answer("Could not download the file. Please try again.")
        return

    client = OpenAI(api_key=settings.openai_api_key)

    if mime == "application/pdf" or name.endswith(".pdf"):
        extracted = extract_pdf_text(data)
        if not extracted:
            await message.answer(
                "Could not read text from this PDF. It may be scan-only images inside the PDF — "
                "try sending screenshots instead."
            )
            return
        cap = (message.caption or "").strip()
        prompt = (
            "The user uploaded a PDF.\n"
            + (f"User question / note: {cap}\n\n" if cap else "")
            + "Extracted text:\n---\n"
            + extracted
        )
        try:
            text = reply_chat(client, settings.openai_model, SYSTEM_PROMPT, prompt)
        except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
            logger.warning("OpenAI error in on_document pdf: %s", exc)
            await message.answer(_openai_user_message(exc))
            return
        await send_model_reply(message, text)
        return

    if mime.startswith("image/"):
        img_mime = mime if mime in ("image/png", "image/jpeg", "image/webp") else guess_image_mime(path)
        cap = (message.caption or "").strip()
        user_part = (
            cap
            if cap
            else (
                "The user sent an image file with no caption. "
                "Describe it and help step-by-step if applicable."
            )
        )
        try:
            text = reply_chat_with_image(
                client, settings.openai_model, SYSTEM_PROMPT, user_part, data, img_mime
            )
        except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
            logger.warning("OpenAI error in on_document image: %s", exc)
            await message.answer(_openai_user_message(exc))
            return
        await send_model_reply(message, text)
        return

    await message.answer(
        "This file type is not supported yet. Send a PDF or an image (PNG / JPEG / WebP)."
    )


@router.message(F.text)
async def on_text(message: Message, settings: Settings) -> None:
    client = OpenAI(api_key=settings.openai_api_key)
    await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
    try:
        text = reply_chat(client, settings.openai_model, SYSTEM_PROMPT, message.text or "")
    except (AuthenticationError, RateLimitError, APIConnectionError, APIError) as exc:
        logger.warning("OpenAI error in on_text: %s", exc)
        await message.answer(_openai_user_message(exc))
        return
    await send_model_reply(message, text)


async def main() -> None:
    settings = load_settings()
    bot = Bot(settings.telegram_bot_token)
    dp = Dispatcher()
    dp.message.middleware(SettingsMiddleware(settings))
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Normal shutdown when you press Ctrl+C in the terminal
        print("\nBot stopped (Ctrl+C).")
