"""Chapter 14 (regions) and Chapter 17 (models)."""

import pytest

from healer.config import Settings, build_model
from healer.llm.router import AllRegionsFailed, FallbackProvider, RegionRouter


class Fake:
    def __init__(self, name, error=None):
        self.name, self.error, self.calls = name, error, 0

    def invoke(self, prompt, **kwargs):
        self.calls += 1
        if self.error:
            raise self.error
        return self.name


class Throttled(Exception):
    response = {"Error": {"Code": "ThrottlingException"}}


class Broken(Exception):
    response = {"Error": {"Code": "ServiceUnavailableException"}}


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class TestRegionRouter:
    def test_it_round_robins_on_every_request_not_just_on_failure(self):
        router = RegionRouter({"a": Fake("a"), "b": Fake("b"), "c": Fake("c")})
        assert [router.invoke("x") for _ in range(6)] == ["a", "b", "c", "a", "b", "c"]

    def test_a_throttled_region_is_skipped_for_this_request_only(self):
        a, b = Fake("a", Throttled()), Fake("b")
        router = RegionRouter({"a": a, "b": b})
        assert router.invoke("x") == "b" and router.throttled["a"] == 1
        a.error = None
        assert router.invoke("x") == "b"  # b's turn
        assert router.invoke("x") == "a"  # a is back: throttling is not a hard failure

    def test_a_hard_failure_takes_the_region_out_for_a_while(self):
        clock = Clock()
        a, b = Fake("a", Broken()), Fake("b")
        router = RegionRouter({"a": a, "b": b}, cooldown_seconds=60, clock=clock)
        router.invoke("x")
        a.error = None
        assert [router.invoke("x") for _ in range(3)] == ["b", "b", "b"]
        assert a.calls == 1  # not retried during the cooldown
        clock.now = 61
        assert "a" in [router.invoke("x") for _ in range(2)]

    def test_everything_down_is_an_error_not_a_hang(self):
        router = RegionRouter({"a": Fake("a", Throttled()), "b": Fake("b", Broken())})
        with pytest.raises(AllRegionsFailed):
            router.invoke("x")

    def test_it_needs_a_region(self):
        with pytest.raises(ValueError):
            RegionRouter({})


class TestModelFallback:
    def test_the_fallback_answers_only_when_the_primary_cannot(self):
        primary, fallback = Fake("sonnet"), Fake("opus")
        provider = FallbackProvider(primary, fallback)
        assert provider.invoke("x") == "sonnet" and fallback.calls == 0
        primary.error = Broken()
        assert provider.invoke("x") == "opus" and provider.fallbacks_used == 1


def test_settings_build_the_chapter_17_model_trio():
    from unittest.mock import MagicMock

    s = Settings(
        bedrock_model_id="sonnet",
        bedrock_fallback_model_id="opus",
        bedrock_quick_model_id="haiku",
        bedrock_regions="us-east-1,us-west-2",
    )
    session = MagicMock()
    assert isinstance(build_model(s, session), FallbackProvider)
    assert build_model(s, session, model_id="haiku").__class__ is RegionRouter
    s2 = Settings(bedrock_model_id="sonnet", bedrock_region="us-east-1")
    assert build_model(s2, session).model_id == "sonnet"
