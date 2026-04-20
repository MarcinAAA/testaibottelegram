# Telegram AI bot (demo-ready)

**Python 3.12 + [aiogram](https://docs.aiogram.dev/) 3 + [OpenAI](https://platform.openai.com/)** — matches a typical “Telegram + OpenAI” freelance brief:

| Feature | Status |
|--------|--------|
| ChatGPT-style text chat | Yes (`Chat Completions`) |
| OpenAI integration | Yes |
| Multi-language | Yes (model replies in the user’s language; no separate detector) |
| Step-by-step answers | Yes (system prompt) |
| **Screenshots / photos** | Yes (**vision** via `image_url` + base64) |
| **PDF documents** | Yes (**text extract** with [pypdf](https://pypdf.readthedocs.io/), then model) |
| Rephrase if user is stuck | Yes (`/rephrase` — reply to bot text/caption first) |
| Escalation to admins | Yes (`/escalate`; optional **reply** to include thread context) |
| Clean structure | Split modules (`telegram_file`, `pdf_extract`, `openai_client`) |
| Long answers | Chunked under Telegram’s 4096 char limit |

### Responses API vs Chat Completions

The job text often mentions **“Responses API”**. This repo uses **`chat.completions`** (including **multimodal** images), which is the standard, well-supported path in the official Python SDK and covers the same product needs for this demo. If a client contractually requires the **Responses** endpoint only, that can be swapped in a small follow-up — behavior for users stays the same.

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

## What this repo does **not** include (optional next work)

- **Usage limits** per user / billing (Stripe)
- **Streaming** partial tokens into Telegram
- **Conversation database** (history, admin web UI)
- **DOCX / XLSX** and other office formats (only **PDF + common images** today)
- **OCR** for scan-only PDFs (send **photos** of pages instead)

---

## Project layout

| File | Role |
|------|------|
| `bot.py` | Aiogram handlers, middleware, polling entrypoint |
| `openai_client.py` | `chat.completions` text + vision (`image_url`) |
| `telegram_file.py` | Download Telegram file bytes (HTTP) |
| `pdf_extract.py` | PDF → plain text (best-effort) |
| `config.py` | Loads settings from `.env` |
| `requirements.txt` | Dependencies |

---

## License

No license file included — add one (e.g. MIT) if you open-source the repo.
