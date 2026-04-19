# Telegram AI bot (MVP)

A minimal **Python 3.12 + [aiogram](https://docs.aiogram.dev/) 3 + [OpenAI](https://platform.openai.com/)** Telegram bot:

- Natural replies to user text (chat completions)
- `/rephrase` — reply to a **bot** message, then send `/rephrase` (or send `/rephrase` as a reply to that message) for a simpler rewrite
- `/escalate` — forwards a notice to Telegram users listed in `ADMIN_TELEGRAM_IDS`
- Friendly handling of common OpenAI errors (quota, invalid key, network)

## Why put this on GitHub?

- **Proof for clients** — a public (or private) repo link is standard in proposals (Upwork, email, etc.).
- **Backup** — you do not lose the project if your PC dies.
- **History** — commits show how the project evolved.

Never commit `.env` (secrets). This repo includes `.gitignore` for that.

---

## Requirements

- **Python 3.12 or 3.11** (recommended: **3.12** on Windows so wheels install without compiling).
- Avoid **Python 3.14** for now — `aiohttp` / `pydantic-core` often lack prebuilt wheels and require Visual C++ / Rust toolchains.

---

## Quick start (local)

```powershell
cd telegram-ai-bot
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in values (see below). Then:

```powershell
python bot.py
```

Stop the bot with **Ctrl+C** (shutdown is normal; you should see `Bot stopped (Ctrl+C).`).

If PowerShell blocks `Activate.ps1`:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

You can skip activation and call the venv Python directly:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe bot.py
```

---

## Environment variables (`.env`)

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | From [@BotFather](https://t.me/BotFather) (`/newbot`). |
| `OPENAI_API_KEY` | Yes | From [API keys](https://platform.openai.com/api-keys). Billing may be required — see below. |
| `OPENAI_MODEL` | No | Default: `gpt-4o-mini` (cheap for testing). |
| `ADMIN_TELEGRAM_IDS` | No | Comma-separated numeric user IDs who receive `/escalate` DMs. Get your ID from [@userinfobot](https://t.me/userinfobot). |

**OpenAI `429` / `insufficient_quota`:** add a payment method or credits under [Billing](https://platform.openai.com/account/billing). Free trial credits can run out.

**Escalation header shows odd `@` text:** if you have no Telegram **username**, the bot prints your **display name** instead of `@None` (after the latest `bot.py`).

---

## Deploy (Railway, Render, etc.)

1. Set the same variables in the host’s **environment** UI (not committed to git).
2. **Start command:** `python bot.py` (or `python -u bot.py` for immediate logs).
3. Use **Python 3.12** in the service settings if the platform lets you choose.

---

## What this MVP does **not** include yet

Typical **phase 2** items from real job posts:

- Photo / PDF upload and analysis (Vision + parsing)
- Usage limits per user, subscriptions (e.g. Stripe)
- Streaming tokens into Telegram messages
- Persistent conversation storage (database)

Add these incrementally or scope them as a separate milestone for clients.

---

## Project layout

| File | Role |
|------|------|
| `bot.py` | Aiogram handlers, middleware, polling entrypoint |
| `openai_client.py` | Thin wrapper around `chat.completions` |
| `config.py` | Loads settings from `.env` |
| `requirements.txt` | Dependencies |

---

## License

No license file included — add one (e.g. MIT) if you open-source the repo.
