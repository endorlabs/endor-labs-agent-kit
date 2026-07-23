"""Publish deterministic runtime helpers with every generated agent surface."""

from __future__ import annotations

from pathlib import Path
import shutil


ARTIFACT_SUMMARIZER_NAME = "summarize_endor_artifact.py"
RUNTIME_DIRECTORY = "runtime"


def write_artifact_summarizer(package_root: Path) -> Path:
    """Copy the canonical artifact summarizer into one runtime package."""

    target = package_root / RUNTIME_DIRECTORY / ARTIFACT_SUMMARIZER_NAME
    return write_artifact_summarizer_file(target)


def write_artifact_summarizer_file(target: Path) -> Path:
    """Copy the canonical artifact summarizer to an explicit package-local path."""

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(_artifact_summarizer_source(), target)
    return target


def _artifact_summarizer_source() -> Path:
    source = Path(__file__).resolve().parents[1] / "artifact_summary.py"
    if not source.is_file():
        raise FileNotFoundError(source)
    return source
