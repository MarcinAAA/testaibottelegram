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
