"""管理员登录防护「剩余秒数」浮点尾差回归(#PB-34)。

缺陷:锁定时间由 `locked_until = now + lock_seconds` 写入,事后用 `ceil(locked_until - now)` 取整;
float64 在该减法上会产生 +1 ulp 的**正**尾差(实测 base=130398.254 时,1ms 步长下 24.8% 的时点得到
1800.0000000000146 → `ceil` = **1801**),用户会看到「请在 1801 秒后重试」,越过配置窗口 1800。

本用例用**假时钟**把 base 钉在大数量级(含两个已知溢出量级)并以 0.001 秒步长扫描,断言:
① 锁定瞬间 `record_failure` 返回值 == lock_seconds;② 任何时点返回值都 <= lock_seconds;
③ 仍处于锁定态时 `locked_seconds` ∈ [1, lock_seconds];④ 过期后 == 0;
⑤ 限流器的「需等待秒数」同样不得超过窗口(不同类,见用例注释)。

隔离:独立 store/limiter 实例 + 假时钟;不触碰进程内真实状态、不 sleep、不写库、不 monkeypatch 全局时钟。
"""
import math

from app.services.auth import _LoginAttemptStore, _LoginRateLimiter

# 已知会触发 +1 ulp 尾差的量级(前者为总控实测量级,后者为开机 1 小时量级)
BASE_TIMES = (130398.254, 3600.002)
LOCK_SECONDS = 1800.0
TTL = 1800.0
MAX_ATTEMPTS = 5
STEP = 0.001
# 扫过整个锁定窗口(1800s / 0.001s = 1_800_000 步,取足量样本并留出边界余量)
SCAN_STEPS = 1_800_000


class _FakeClock:
    """可控单调时钟(替身),避免真实等待 30 分钟。"""

    def __init__(self, start: float) -> None:
        self.now = float(start)

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _store_at(base: float) -> tuple:
    clock = _FakeClock(base)
    return _LoginAttemptStore(max_entries=10, clock=clock), clock


def _lock_key() -> str:
    return "admin"


def _lock(store, key: str) -> int:
    """连续失败 MAX_ATTEMPTS 次触发锁定,返回锁定瞬间的剩余秒数。"""
    returned = [store.record_failure(key, MAX_ATTEMPTS, LOCK_SECONDS, TTL) for _ in range(MAX_ATTEMPTS)]
    assert returned[:MAX_ATTEMPTS - 1] == [0] * (MAX_ATTEMPTS - 1), returned
    return returned[-1]


def test_lock_moment_returns_exactly_lock_seconds():
    """锁定瞬间的返回值恒等于 lock_seconds(不得因浮点尾差变成 1801)。"""
    for base in BASE_TIMES:
        store, _ = _store_at(base)
        returned = [store.record_failure(_lock_key(), MAX_ATTEMPTS, LOCK_SECONDS, TTL)
                    for _ in range(MAX_ATTEMPTS)]
        assert returned[:MAX_ATTEMPTS - 1] == [0] * (MAX_ATTEMPTS - 1), (base, returned)
        assert returned[-1] == LOCK_SECONDS, (base, returned[-1])


def test_locked_seconds_stays_within_window_over_full_scan():
    """仍处于锁定态时 `locked_seconds` ∈ [1, lock_seconds];最大值恰为 lock_seconds。"""
    key = _lock_key()
    for base in BASE_TIMES:
        store, clock = _store_at(base)
        assert _lock(store, key) == LOCK_SECONDS
        deadline = base + LOCK_SECONDS
        seen_max = 0
        for _ in range(SCAN_STEPS):
            clock.advance(STEP)
            if clock.now >= deadline:
                break
            left = store.locked_seconds(key, TTL)
            assert left >= 1, (base, clock.now, left)
            assert left <= LOCK_SECONDS, ("超出锁定窗口", base, clock.now, left)
            seen_max = max(seen_max, left)
        assert seen_max == LOCK_SECONDS, (base, seen_max)


def test_record_failure_while_locked_never_exceeds_window():
    """锁定态内再次失败时,返回的剩余秒数同样不得超过 lock_seconds。"""
    key = _lock_key()
    for base in BASE_TIMES:
        store, clock = _store_at(base)
        assert _lock(store, key) == LOCK_SECONDS
        for _ in range(20):
            clock.advance(TTL / 20.0)
            left = store.record_failure(key, MAX_ATTEMPTS, LOCK_SECONDS, TTL)
            assert 0 <= left <= LOCK_SECONDS, (base, clock.now, left)


def test_locked_seconds_is_zero_once_expired():
    """恰好到期与过期之后都必须为 0(不得把「刚过期」判成仍锁定)。"""
    key = _lock_key()
    for base in BASE_TIMES:
        store, clock = _store_at(base)
        assert _lock(store, key) == LOCK_SECONDS
        clock.advance(LOCK_SECONDS)                       # 恰好到期
        assert store.locked_seconds(key, TTL) == 0, (base, clock.now)
        clock.advance(STEP)                               # 过期之后
        assert store.locked_seconds(key, TTL) == 0, (base, clock.now)


def test_rate_limiter_retry_after_never_exceeds_window():
    """限流器(不同类):`stamps[0] <= now` 使差值非负且上界即 window,故不得超过窗口。"""
    window, max_requests = 60.0, 3
    for base in BASE_TIMES:
        clock = _FakeClock(base)
        limiter = _LoginRateLimiter(max_entries=10, clock=clock)
        keys = ["ip:test"]
        for _ in range(max_requests):
            assert limiter.record(keys, max_requests, window) == 0
        same_instant = limiter.record(keys, max_requests, window)
        assert same_instant == window, same_instant              # 同一瞬间:恰好 == window,不是 window+1
        seen_max = same_instant
        for _ in range(20000):
            clock.advance(STEP)
            left = limiter.record(keys, max_requests, window)
            if left == 0:
                break
            assert 0 < left <= window, (base, clock.now, left)
            seen_max = max(seen_max, left)
        assert seen_max == window, (base, seen_max)


def test_seconds_rounding_is_far_below_clock_resolution():
    """抹尾差精度必须远小于时钟分辨率(1ms),否则会改变产品语义。"""
    assert math.ceil(round(1800.0000000000146, 6)) == 1800
    assert math.ceil(round(1799.9999999999985, 6)) == 1800
    assert math.ceil(round(0.0000001, 6)) == 0                   # 亚微秒余量不再算作 1 秒
