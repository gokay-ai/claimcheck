from claimcheck.ratelimit import RateLimiter


def test_a_client_is_limited_inside_the_window_and_freed_after_it() -> None:
    now = [0.0]
    limiter = RateLimiter(per_client=2, window_seconds=60, daily_cap=100, clock=lambda: now[0])
    assert limiter.check("a").allowed
    assert limiter.check("a").allowed
    blocked = limiter.check("a")
    assert not blocked.allowed
    assert 0 < blocked.retry_after_seconds <= 61
    assert limiter.check("b").allowed
    now[0] = 61.0
    assert limiter.check("a").allowed


def test_the_daily_cap_applies_across_clients() -> None:
    now = [0.0]
    limiter = RateLimiter(per_client=5, window_seconds=60, daily_cap=2, clock=lambda: now[0])
    assert limiter.check("a").allowed
    assert limiter.check("b").allowed
    assert not limiter.check("c").allowed
    now[0] = 86_401.0
    assert limiter.check("c").allowed
