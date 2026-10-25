"""Create the TALP Vertex AI client using the project's local .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

DEFAULT_MODEL = "gemini-3.7-flash"


def generate_text(prompt, *, model=DEFAULT_MODEL):
    with create_client() as client:
        reply = client.models.generate_content(model=model, contents=prompt)
    return reply.text


def create_client():
    load_dotenv(Path(__file__).resolve().parent / ".env")
    api_key = os.environ.get("TALP_KEY", "").strip()
    if not api_key:
        raise ValueError("Set TALP_KEY in the project's .env file before running.")
    return genai.Client(
        vertexai=True,
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=90000,
            retry_options=types.HttpRetryOptions(attempts=5)
        ),
    )


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test the TALP API using .env.")
    parser.add_argument("prompt", nargs="?", default="Reply with exactly: API works")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    args = parser.parse_args()
    print(f"Calling {args.model}...", flush=True)
    try:
        result = generate_text(args.prompt, model=args.model)
        if not result:
            raise RuntimeError("The API returned no text.")
    except Exception as exc:
        # Avoid printing provider exceptions that could include request credentials.
        raise SystemExit(
            f"API check failed ({type(exc).__name__}). "
            "Check TALP_KEY in .env, network access, and model availability."
        ) from None
    print(result)
