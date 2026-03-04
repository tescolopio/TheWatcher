"""Generate TTRPG session summaries via a local Ollama LLM.

Sends the raw transcript to a locally running Ollama instance and returns a
structured Markdown summary formatted for an Obsidian note.

v0.3 addition: configurable retry with exponential back-off via
  ``OLLAMA_MAX_RETRIES`` (default 3) and ``OLLAMA_RETRY_DELAY_S`` (default 2).

v0.5 addition: optional speaker-labelled transcript support.  When *speakers*
  is provided the system prompt gains an extra instruction block asking the
  model to respect ``[CharacterName]: ...`` labels and output a
  **Party Members** section.
"""

import logging
import os
import time
from typing import Any, Optional

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

_SPEAKER_PROMPT_SUFFIX = """\

The transcript uses speaker labels formatted as ``[CharacterName]: dialogue``.
Preserve these attributions in the summary.

Add an additional section at the end:
## Party Members
A bulleted list of the character names present in this session (exactly as
they appear in the speaker labels — do not paraphrase).\
"""


def summarize(
    transcript: str,
    speakers: Optional[list[str]] = None,
    max_retries: Optional[int] = None,
    retry_delay: Optional[float] = None,
) -> str:
    """Use a local Ollama model to summarise a session transcript.

    Args:
        transcript:   Raw text of the session as returned by the transcriber.
        speakers:     Optional list of character names present in the session.
                      When provided, the system prompt is extended to ask the
                      model to attribute dialogue by speaker and produce a
                      **Party Members** section.
        max_retries:  Maximum number of Ollama call attempts.  Overrides the
                      ``OLLAMA_MAX_RETRIES`` env var (default 3).
        retry_delay:  Base delay (seconds) between retries; doubles each attempt
                      (exponential back-off).  Overrides ``OLLAMA_RETRY_DELAY_S``
                      (default 2.0).

    Returns:
        Structured Markdown summary string.

    Raises:
        ollama.ResponseError: If Ollama returns an error response.
        Exception: If all retry attempts are exhausted.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "mistral")
    _max_retries = max_retries if max_retries is not None else int(os.getenv("OLLAMA_MAX_RETRIES", "3"))
    _retry_delay = retry_delay if retry_delay is not None else float(os.getenv("OLLAMA_RETRY_DELAY_S", "2.0"))

    system_content = _SYSTEM_PROMPT + (_SPEAKER_PROMPT_SUFFIX if speakers else "")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": f"Here is the session transcript:\n\n{transcript}"},
    ]

    client = ollama.Client(host=base_url)

    last_exc: Optional[Exception] = None
    for attempt in range(1, _max_retries + 1):
        try:
            logger.info(
                "Summarising with Ollama model '%s' at %s (attempt %d/%d)",
                model,
                base_url,
                attempt,
                _max_retries,
            )
            response = client.chat(model=model, messages=messages)
            return str(response.message.content).strip()
        except Exception as exc:
            last_exc = exc
            if attempt < _max_retries:
                wait = _retry_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Ollama attempt %d/%d failed: %s — retrying in %.1f s",
                    attempt,
                    _max_retries,
                    exc,
                    wait,
                )
                time.sleep(wait)
            else:
                logger.error("All %d Ollama attempts exhausted: %s", _max_retries, exc)

    raise RuntimeError(f"Ollama unreachable after {_max_retries} retries") from last_exc
