"""AI narration with a Nigerian-English delivery (OpenAI text-to-speech)."""
import os
from pathlib import Path

import httpx
import openai

INSTRUCTIONS = (
    "Speak as a warm, friendly narrator with a natural Nigerian English accent. "
    "Clear, calm and reassuring, at a gentle pace suited to a health education video."
)


def synthesize(text, out_path, api_key=None, voice="coral"):
    client = openai.OpenAI(
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
        timeout=httpx.Timeout(120.0, connect=30.0),
        max_retries=3,  # backoff on timeouts, 429s, 5xx
    )
    try:  # gpt-4o-mini-tts accepts style/accent instructions
        resp = client.audio.speech.create(model="gpt-4o-mini-tts", voice=voice, input=text,
                                          instructions=INSTRUCTIONS, response_format="mp3")
    except (openai.BadRequestError, openai.NotFoundError, openai.PermissionDeniedError):
        # fallback only if the model or parameter is unsupported, never on timeouts
        resp = client.audio.speech.create(model="tts-1", voice="nova", input=text,
                                          response_format="mp3")
    Path(out_path).write_bytes(resp.content)
    return Path(out_path)