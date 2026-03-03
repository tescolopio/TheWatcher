"""Audio transcription via Whisper.

Supports two backends, selected automatically:
  1. whisper.cpp – called as a subprocess when ``WHISPER_CPP_PATH`` points to
     a valid executable.  Fast, CPU-only, no Python dependencies.
  2. openai-whisper Python package – used as a fallback when whisper.cpp is
     not configured.  Requires the ``openai-whisper`` pip package.
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _transcribe_with_whisper_cpp(audio_path: Path) -> str:
    """Run the whisper.cpp binary and return the transcript text.

    Args:
        audio_path: Path to the WAV file to transcribe.

    Returns:
        Transcript text as a single string.

    Raises:
        RuntimeError: If the whisper.cpp process exits with a non-zero code.
    """
    whisper_cpp_path = os.environ["WHISPER_CPP_PATH"]
    model = os.getenv("WHISPER_MODEL", "base")
    model_file = Path(whisper_cpp_path).parent / "models" / f"ggml-{model}.bin"

    result = subprocess.run(
        [whisper_cpp_path, "-m", str(model_file), "-f", str(audio_path), "--output-txt", "-"],
        capture_output=True,
        text=True,
        timeout=600,
    )

    if result.returncode != 0:
        raise RuntimeError(f"whisper.cpp exited with code {result.returncode}: {result.stderr.strip()}")

    return result.stdout.strip()


def _transcribe_with_python_whisper(audio_path: Path) -> str:
    """Use the openai-whisper Python package to transcribe an audio file.

    Args:
        audio_path: Path to the audio file to transcribe.

    Returns:
        Transcript text as a single string.
    """
    import whisper  # noqa: PLC0415 – optional dependency; imported lazily

    model_name = os.getenv("WHISPER_MODEL", "base")
    logger.info("Loading Whisper model '%s'…", model_name)
    model = whisper.load_model(model_name)
    result = model.transcribe(str(audio_path))
    return result["text"].strip()


def transcribe(audio_path: Path) -> str:
    """Transcribe *audio_path* using the configured Whisper backend.

    Selection logic:
      - If ``WHISPER_CPP_PATH`` is set and points to an executable file,
        whisper.cpp is used.
      - Otherwise the openai-whisper Python package is used.

    Args:
        audio_path: Path to the WAV file produced by the recorder.

    Returns:
        Full transcript as a plain string.
    """
    whisper_cpp_path = os.getenv("WHISPER_CPP_PATH", "")
    if whisper_cpp_path and Path(whisper_cpp_path).is_file():
        logger.info("Using whisper.cpp backend at '%s'", whisper_cpp_path)
        return _transcribe_with_whisper_cpp(audio_path)

    logger.info("Using openai-whisper Python backend")
    return _transcribe_with_python_whisper(audio_path)
