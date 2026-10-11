"""Chapter 14: one team is easy, two hundred services is not."""

import json
from pathlib import Path

import fakeredis
import pytest

from healer.library.scale import RedisDistributedRateLimiter

pytest.importorskip("lupa")  # the limiter is a Lua script


def limiter(limit=3, period=60):
    return RedisDistributedRateLimiter(fakeredis.FakeRedis(), limit=limit, period=period)


class TestDistributedLimiter:
    def test_it_admits_up_to_the_limit_then_refuses(self):
        lim = limiter()
        assert [lim.acquire(now=100.0) for _ in range(5)] == [True, True, True, False, False]

    def test_refused_requests_do_not_use_up_slots(self):
        """The first printed version added before checking, so rejections crowded out real work."""
        lim = limiter(limit=2, period=60)
        assert lim.acquire(now=100.0) and lim.acquire(now=101.0)
        assert not any(lim.acquire(now=102.0 + i) for i in range(20))  # a flood is refused
        assert lim.redis.zcard(lim.key) == 2  # ...and left no trace
        assert lim.acquire(now=161.5)  # the window slides: the first slot has expired

    def test_two_calls_in_the_same_instant_both_count(self):
        """A unique member per call: equal timestamps must not overwrite each other."""
        lim = limiter(limit=2)
        assert lim.acquire(now=50.0) and lim.acquire(now=50.0)
        assert lim.redis.zcard(lim.key) == 2 and not lim.acquire(now=50.0)

    def test_two_limiters_share_one_budget_through_redis(self):
        client = fakeredis.FakeRedis()
        a = RedisDistributedRateLimiter(client, limit=2)
        b = RedisDistributedRateLimiter(client, limit=2)
        assert a.acquire(now=1.0) and b.acquire(now=1.0) and not a.acquire(now=1.0)


def test_the_cross_account_trust_policy_requires_an_external_id():
    policy = json.loads(
        (Path(__file__).parents[2] / "infra/policies/cross-account-trust.json").read_text()
    )
    assert policy["Action"] == "sts:AssumeRole"
    assert "sts:ExternalId" in policy["Condition"]["StringEquals"]  # confused-deputy protection
