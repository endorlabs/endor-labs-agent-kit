"""Safe, patch-bound validation in a disposable checkout.

This module deliberately treats the user's worktree as read-only.  Validation
runs in an owned temporary clone at an exact commit, and only explicitly
allowlisted untracked inputs may cross that boundary.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tempfile
from typing import Iterator, Sequence


class ValidationIsolationError(RuntimeError):
    """Raised when a safe validation checkout cannot be prepared."""


class ValidationIsolationCleanupError(ValidationIsolationError):
    """Raised when an owned disposable checkout cannot be removed."""


def _run_git(
    repo: Path,
    *args: str,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ("git", *args),
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
            input=input_text,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or str(exc)
        raise ValidationIsolationError(detail) from exc


def _entry_digest(path: Path) -> str:
    if path.is_symlink():
        payload = b"symlink\0" + os.readlink(path).encode("utf-8", errors="surrogateescape")
    else:
        payload = b"file\0" + path.read_bytes()
    return hashlib.sha256(payload).hexdigest()


def worktree_snapshot(repo: str | Path) -> tuple[tuple[str, str, int], ...]:
    """Return a byte-sensitive snapshot of worktree state, excluding Git metadata."""

    root = Path(repo).resolve()
    if not root.is_dir():
        raise ValidationIsolationError(f"repository does not exist: {root}")

    entries: list[tuple[str, str, int]] = []
    for current, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = sorted(name for name in dirnames if name != ".git")
        current_path = Path(current)
        for filename in sorted(filenames):
            if filename == ".git":
                continue
            path = current_path / filename
            relative = path.relative_to(root).as_posix()
            entries.append((relative, _entry_digest(path), path.lstat().st_mode))

    status = subprocess.run(
        ("git", "status", "--porcelain=v2", "-z", "--untracked-files=all", "--ignore-submodules=none"),
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout
    entries.append(("<git-status>", hashlib.sha256(status).hexdigest(), 0))
    return tuple(entries)


def _safe_allowlisted_path(raw_path: str) -> PurePosixPath:
    relative = PurePosixPath(raw_path)
    if (
        not raw_path
        or relative.is_absolute()
        or ".." in relative.parts
        or "." in relative.parts
        or ".git" in relative.parts
    ):
        raise ValidationIsolationError(f"unsafe allowlisted path: {raw_path!r}")
    return relative


@dataclass(frozen=True)
class ValidationEnvironment:
    """A disposable checkout plus patch-bound validation evidence."""

    root: Path
    checkout: Path
    source_revision: str
    patch_sha256: str

    def run(self, command: Sequence[str]) -> dict[str, object]:
        if not command:
            raise ValidationIsolationError("validation command cannot be empty")
        completed = subprocess.run(
            tuple(command),
            cwd=self.checkout,
            check=False,
            capture_output=True,
            text=True,
        )
        return {
            "command": list(command),
            "exit_code": completed.returncode,
            "status": "passed" if completed.returncode == 0 else "failed",
            "stdout": completed.stdout,
            "stderr": completed.stderr,
            "source_revision": self.source_revision,
            "patch_sha256": self.patch_sha256,
        }


def _copy_allowlisted_inputs(
    source_repo: Path,
    checkout: Path,
    allowlisted_untracked: Sequence[str],
) -> None:
    for raw_path in allowlisted_untracked:
        relative = _safe_allowlisted_path(raw_path)
        source = source_repo.joinpath(*relative.parts)
        destination = checkout.joinpath(*relative.parts)
        if not source.is_file() or source.is_symlink():
            raise ValidationIsolationError(
                f"allowlisted input must be a regular non-symlink file: {raw_path!r}"
            )
        if destination.exists() or destination.is_symlink():
            raise ValidationIsolationError(
                f"allowlisted input would overwrite checkout content: {raw_path!r}"
            )
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination, follow_symlinks=False)


@contextmanager
def isolated_validation_environment(
    repo: str | Path,
    *,
    source_revision: str,
    patch_diff: str,
    allowlisted_untracked: Sequence[str] = (),
) -> Iterator[ValidationEnvironment]:
    """Yield a disposable exact-revision checkout with ``patch_diff`` applied."""

    source_repo = Path(repo).resolve()
    baseline = worktree_snapshot(source_repo)
    resolved_revision = _run_git(
        source_repo, "rev-parse", "--verify", f"{source_revision}^{{commit}}"
    ).stdout.strip()
    patch_sha256 = hashlib.sha256(patch_diff.encode("utf-8")).hexdigest()
    owned_root = Path(tempfile.mkdtemp(prefix="endor-agent-kit-validation-")).resolve()
    checkout = owned_root / "checkout"
    environment = ValidationEnvironment(
        root=owned_root,
        checkout=checkout,
        source_revision=resolved_revision,
        patch_sha256=patch_sha256,
    )

    body_error: BaseException | None = None
    try:
        _run_git(
            owned_root,
            "clone",
            "--no-hardlinks",
            "--no-checkout",
            str(source_repo),
            str(checkout),
        )
        _run_git(checkout, "checkout", "--detach", resolved_revision)
        _copy_allowlisted_inputs(source_repo, checkout, allowlisted_untracked)
        if patch_diff:
            _run_git(checkout, "apply", "--check", "--whitespace=error-all", "-", input_text=patch_diff)
            _run_git(checkout, "apply", "--whitespace=error-all", "-", input_text=patch_diff)
        try:
            yield environment
        except BaseException as exc:
            body_error = exc
            raise
    finally:
        cleanup_error: OSError | None = None
        try:
            shutil.rmtree(owned_root)
        except OSError as exc:
            cleanup_error = exc

        unchanged = worktree_snapshot(source_repo) == baseline
        if not unchanged and body_error is None:
            raise ValidationIsolationError(
                "user worktree changed while isolated validation was running"
            )
        if cleanup_error is not None and body_error is None:
            raise ValidationIsolationCleanupError(
                f"failed to remove owned validation checkout {owned_root}: {cleanup_error}"
            ) from cleanup_error
