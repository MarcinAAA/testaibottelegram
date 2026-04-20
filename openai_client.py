import base64
from typing import Any

from openai import OpenAI


def reply_chat(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_text: str,
) -> str:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_text},
        ],
        temperature=0.4,
    )
    choice = response.choices[0].message.content
    return (choice or "").strip()


def reply_chat_with_image(
    client: OpenAI,
    model: str,
    system_prompt: str,
    user_text: str,
    image_bytes: bytes,
    image_mime: str,
) -> str:
    """Vision: requires a vision-capable model (e.g. gpt-4o-mini, gpt-4o)."""
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_url = f"data:{image_mime};base64,{b64}"
    user_content: list[dict[str, Any]] = [
        {"type": "text", "text": user_text},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.4,
    )
    choice = response.choices[0].message.content
    return (choice or "").strip()
