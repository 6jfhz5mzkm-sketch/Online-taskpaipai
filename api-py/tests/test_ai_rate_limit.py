"""AI 分析限流并发回归测试(B5)。

背景:ai.py 的 _analysis_rate_ok 对模块级 _analysis_window 做无锁 read-modify-write,
FastAPI 同步端点在线程池并发时计数互相覆盖,5/min 限流失准。
本用例用 barrier + 极小线程切换间隔放大竞态:修复前放行数 > 5,修复后恰好 5。
"""

import sys
import threading
import uuid

from app.services import ai

_WORKERS = 32


def test_analysis_rate_limit_under_concurrency():
    """32 线程同时命中同一 IP:5/min 窗口下只允许 5 次通过,其余全部拒绝。"""
    ip = "_test_rate_" + uuid.uuid4().hex[:8]
    barrier = threading.Barrier(_WORKERS)
    allowed = []
    collect_lock = threading.Lock()

    def hit():
        barrier.wait()
        ok = ai._analysis_rate_ok(ip)
        with collect_lock:
            allowed.append(ok)

    old_interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)   # 放大线程切换,让无锁版本的竞态稳定复现
    try:
        threads = [threading.Thread(target=hit) for _ in range(_WORKERS)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old_interval)
        ai._analysis_window.pop(ip, None)

    passed = allowed.count(True)
    assert passed == 5, f"5/min 限流失准:放行 {passed}/{_WORKERS}"
    assert allowed.count(False) == _WORKERS - 5
