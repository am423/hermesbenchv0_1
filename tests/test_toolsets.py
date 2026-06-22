"""Regression tests for real-agent toolset exposure."""
from __future__ import annotations

from hermesbench.hermes_invocation import allowed_tools_to_toolsets


def test_search_files_uses_file_toolset() -> None:
    # Hermes' "search" toolset is web_search only; search_files lives in file.
    assert allowed_tools_to_toolsets(["search_files"]) == "file"


def test_file_mutation_tools_share_file_toolset() -> None:
    assert allowed_tools_to_toolsets(["read_file", "patch", "write_file", "search_files"]) == "file"


def test_mixed_allowed_tools_are_stable_sorted_toolsets() -> None:
    assert allowed_tools_to_toolsets(["terminal", "search_files", "execute_code"]) == "code_execution,file,terminal"
