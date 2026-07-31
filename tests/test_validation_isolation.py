from __future__ import annotations

import shutil
import subprocess

import pytest

from endor_agent_kit.validation_isolation import (
    ValidationIsolationCleanupError,
    isolated_validation_environment,
    worktree_snapshot,
)


def _git(repo, *args):
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Validation Fixture")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    (repo / "requirements.txt").write_text("example==1.0\n", encoding="utf-8")
    (repo / "build").mkdir()
    (repo / "build" / "generated.txt").write_text("committed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "initial")
    return repo


PATCH = (
    "--- a/requirements.txt\n"
    "+++ b/requirements.txt\n"
    "@@ -1,1 +1,1 @@\n"
    "-example==1.0\n"
    "+example==1.1\n"
)


def test_validation_isolation_preserves_tracked_and_untracked_user_files(tmp_path):
    repo = _repo(tmp_path)
    (repo / "build" / "generated.txt").write_text("user-modified\n", encoding="utf-8")
    (repo / "local-settings.xml").write_text("required input\n", encoding="utf-8")
    (repo / "private-note.txt").write_text("must not copy\n", encoding="utf-8")
    baseline = worktree_snapshot(repo)

    with isolated_validation_environment(
        repo,
        source_revision="HEAD",
        patch_diff=PATCH,
        allowlisted_untracked=("local-settings.xml",),
    ) as isolated:
        assert (isolated.checkout / "requirements.txt").read_text(encoding="utf-8") == "example==1.1\n"
        assert (isolated.checkout / "local-settings.xml").read_text(encoding="utf-8") == "required input\n"
        assert not (isolated.checkout / "private-note.txt").exists()
        evidence = isolated.run(("git", "diff", "--check"))
        assert evidence["status"] == "passed"
        assert evidence["patch_sha256"] == isolated.patch_sha256

    assert worktree_snapshot(repo) == baseline
    assert (repo / "build" / "generated.txt").read_text(encoding="utf-8") == "user-modified\n"


def test_validation_isolation_does_not_initialize_or_mutate_user_submodules(tmp_path):
    submodule = tmp_path / "submodule"
    submodule.mkdir()
    _git(submodule, "init")
    _git(submodule, "config", "user.name", "Submodule Fixture")
    _git(submodule, "config", "user.email", "fixture@example.invalid")
    (submodule / "module.txt").write_text("module\n", encoding="utf-8")
    _git(submodule, "add", ".")
    _git(submodule, "commit", "-m", "submodule")

    repo = _repo(tmp_path)
    _git(repo, "-c", "protocol.file.allow=always", "submodule", "add", str(submodule), "vendor/sub")
    _git(repo, "commit", "-am", "add submodule")
    baseline = worktree_snapshot(repo)

    with isolated_validation_environment(repo, source_revision="HEAD", patch_diff=PATCH) as isolated:
        assert (isolated.checkout / ".gitmodules").is_file()
        assert not (isolated.checkout / "vendor" / "sub" / "module.txt").exists()

    assert worktree_snapshot(repo) == baseline
    assert (repo / "vendor" / "sub" / "module.txt").is_file()


def test_validation_isolation_cleanup_failure_never_mutates_user_worktree(tmp_path, monkeypatch):
    repo = _repo(tmp_path)
    baseline = worktree_snapshot(repo)
    owned_root = None
    real_rmtree = shutil.rmtree

    def fail_cleanup(_path):
        raise OSError("cleanup blocked")

    monkeypatch.setattr("endor_agent_kit.validation_isolation.shutil.rmtree", fail_cleanup)
    with pytest.raises(ValidationIsolationCleanupError, match="cleanup blocked"):
        with isolated_validation_environment(repo, source_revision="HEAD", patch_diff=PATCH) as isolated:
            owned_root = isolated.root

    assert worktree_snapshot(repo) == baseline
    monkeypatch.undo()
    assert owned_root is not None
    real_rmtree(owned_root)
