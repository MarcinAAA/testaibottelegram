import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher, F, Router
from aiogram.enums import ChatAction
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, TelegramObject, User
from openai import APIConnectionError, APIError, AuthenticationError, OpenAI, RateLimitError

from config import Settings, load_settings
from openai_client import reply_chat


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

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a helpful assistant in Telegram.
Answer clearly and step-by-step when the user asks how-to questions.
If the user writes in another language, respond in that same language.
Keep answers concise unless the user asks for detail."""

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
        "Hi! Send me a message and I’ll reply using AI.\n"
        "Commands: /help, /rephrase (reply to my last answer), /escalate (forward to admin)."
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "/rephrase — reply to the bot’s last message to get a simpler explanation.\n"
        "/escalate — forward this chat context to admins (configure ADMIN_TELEGRAM_IDS)."
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
    for admin_id in settings.admin_telegram_ids:
        try:
            await message.bot.send_message(admin_id, header + text)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to notify admin %s: %s", admin_id, exc)
    await message.answer("Your message was forwarded to admins.")


@router.message(F.reply_to_message, Command("rephrase"))
async def cmd_rephrase(message: Message, settings: Settings) -> None:
    original = message.reply_to_message.text if message.reply_to_message else None
    if not original:
        await message.answer("Reply to a bot message with /rephrase.")
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
    await message.answer(text or "(empty model response)")


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
    await message.answer(text or "(empty model response)")


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
