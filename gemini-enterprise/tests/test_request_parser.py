"""Unit tests for message parsing: repo-URL normalization and severity words."""

from __future__ import annotations

import pytest

from service.a2a.models import Severity
from service.a2a.request_parser import parse_task_message


def _message(text: str = "", metadata: dict | None = None) -> dict:
    message: dict = {"role": "user", "parts": [{"kind": "text", "text": text}]}
    if metadata is not None:
        message["metadata"] = metadata
    return message


def test_github_url_with_git_suffix_normalizes():
    request = parse_task_message(
        _message("Scan https://github.com/acme/service-api.git please")
    )
    assert request.repo_full_name == "acme/service-api"
    assert request.repo_url == "https://github.com/acme/service-api.git"


def test_gitlab_subgroup_url_keeps_full_project_path():
    request = parse_task_message(
        _message("Check https://gitlab.com/group/subgroup/repo for findings")
    )
    assert request.repo_full_name == "group/subgroup/repo"


def test_gitlab_modern_in_repo_path_is_cut_at_separator():
    request = parse_task_message(
        _message("See https://gitlab.com/group/proj/-/blob/main/pom.xml")
    )
    assert request.repo_full_name == "group/proj"


def test_gitlab_legacy_in_repo_path_is_cut_at_reserved_segment():
    request = parse_task_message(
        _message("From https://gitlab.com/group/proj/issues/5 please")
    )
    assert request.repo_full_name == "group/proj"


def test_github_deep_path_keeps_owner_repo():
    request = parse_task_message(
        _message("Fix https://github.com/acme/service-api/blob/main/pom.xml")
    )
    assert request.repo_full_name == "acme/service-api"


def test_sentence_final_punctuation_is_stripped():
    request = parse_task_message(
        _message("Scan https://github.com/acme/service-api. Then report.")
    )
    assert request.repo_full_name == "acme/service-api"


def test_unresolvable_gitlab_path_leaves_full_name_unset():
    request = parse_task_message(
        _message("See https://gitlab.com/group/-/issues today")
    )
    # No two-segment project path remains; never pass a raw path through.
    assert request.repo_full_name is None
    assert request.repo_url is not None


def test_metadata_repo_url_derives_full_name():
    request = parse_task_message(
        _message("Any P0s?", metadata={"repo_url": "https://github.com/acme/thing"})
    )
    assert request.repo_url == "https://github.com/acme/thing"
    assert request.repo_full_name == "acme/thing"


def test_metadata_ref_is_captured():
    request = parse_task_message(
        _message(
            "Check acme/service-api",
            metadata={"ref": "release-2.1"},
        )
    )
    assert request.ref == "release-2.1"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("critical findings in acme/app", [Severity.P0]),
        ("high severity findings in acme/app", [Severity.P1]),
        ("p0 and p1 findings in acme/app", [Severity.P0, Severity.P1]),
        ("findings in acme/app", [Severity.P0, Severity.P1]),
    ],
)
def test_severity_words_map_to_buckets(text, expected):
    assert parse_task_message(_message(text)).severity_filter == expected
