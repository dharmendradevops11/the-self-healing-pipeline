import importlib

import pytest

PACKAGES = [
    "ingest",
    "investigate",
    "gate",
    "fix",
    "test",
    "pr",
    "notify",
    "guardrails",
    "ledger",
    "llm",
    "library",
    "common",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports_and_names_its_chapter(name):
    module = importlib.import_module(f"healer.{name}")
    assert module.__doc__ and "Ch " in module.__doc__ or "all" in module.__doc__
