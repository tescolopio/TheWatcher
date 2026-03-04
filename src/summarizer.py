"""Generate TTRPG session summaries via a local Ollama LLM.

Sends the raw transcript to a locally running Ollama instance and returns a
structured Markdown summary formatted for an Obsidian note.
"""

import logging
import os
from typing import Any

import ollama

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert tabletop RPG session note-taker.
Your task is to turn a raw voice-chat transcript into a clean, structured \
Markdown session summary.

Include the following sections:
## Session Overview
A short paragraph summarising the main events of the session.

## Key Events
A numbered list of the most important events in chronological order.

## NPC Interactions
Notable interactions with non-player characters (names, outcomes).

## Player Decisions
Significant choices or actions taken by the players and their consequences.

## Cliffhangers / Open Threads
Unresolved plot threads, mysteries, or cliffhangers to carry into the next \
session.

Keep the summary concise but comprehensive.  Preserve character names, place \
names, and important story details exactly as mentioned in the transcript.\
"""


def summarize(transcript: str) -> str:
    """Use a local Ollama model to summarise a session transcript.

    Args:
        transcript: Raw text of the session as returned by the transcriber.

    Returns:
        Structured Markdown summary string.

    Raises:
        ollama.ResponseError: If Ollama returns an error response.
        Exception: If the Ollama service is unreachable.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "mistral")

    logger.info("Summarising transcript with Ollama model '%s' at %s", model, base_url)

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Here is the session transcript:\n\n{transcript}"},
    ]

    client = ollama.Client(host=base_url)
    response = client.chat(model=model, messages=messages)

    return str(response.message.content).strip()
