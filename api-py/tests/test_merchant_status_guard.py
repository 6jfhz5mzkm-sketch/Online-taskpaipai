"""商家账号状态守卫回归(P0 权限)。

真源:project/docs/后端技术方案.md §6.1 飞书登录规则 —— status=0(禁用)商家不得继续使用系统;
      §4.3 失败场景表 —— 无权限 403。
口径:禁用(status=0)/已退出(status=2)商家的 token 访问任何商家端接口,应一律 403。

现状(例外登记 · 2026-09-15 用户裁决「商家 status 拦截不做,记一下」):
      get_current_merchant(app/api/deps.py) 只校验 JWT 签名与过期,不查库校验 status;
      对照 get_current_admin 会查库并校验 status=1 —— 两端不对称即本缺口的根因。
      故下列 3 条「禁用/已退出」用例以 xfail(strict=True) 登记为**预期失败**,而非删除或跳过。

移除条件(必须先实现拦截、再删标记):
      当「禁用商家」功能落地(管理后台/接口能把 merchant.status 置 0 或 2)时,
      **先**在商家鉴权侧( get_current_merchant 或其依赖链)实现 status 拦截使这 3 条转绿,
      **再**删除这 3 个 xfail 标记,并同步撤掉真源文档中的例外登记。
      strict=True 即移除条件的技术保障:若拦截被提前实现,用例会 XPASS → 测试套件变红,
      强制实现者回来撤掉标记,例外不会静默长期存在。

隔离:临时商家(_test_ 前缀)+ 其派生行在 finally 清理。
"""

import uuid

import pytest
from sqlalchemy import text

from app.core.security import create_merchant_token

# 3 条例外共用的 xfail 理由(单一真源;只描述缺口与移除条件,不写实现细节)
_XFAIL_REASON = (
    "商家鉴权侧未实现 status 拦截(真源 project/docs/后端技术方案.md §6.1 §4.3 已要求,"
    "V1 不做:2026-09-15 用户裁决「商家 status 拦截不做」);"
    "get_current_merchant 只校验 JWT、不查库校验 merchant.status,"
    "移除条件=实现「禁用商家」功能时先在鉴权侧实现拦截,再删除本标记"
)

# 纯读路径,不依赖任务/配置种子数据
READ_ENDPOINTS = [
    ("GET", "/api/merchant/info", None),
    ("GET", "/api/merchant/category", None),
    ("GET", "/api/shop/summary?time_range=7d", None),
]


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _make_merchant(session, status: int, stage: str = "shop_setup") -> str:
    merchant_id = "_test_status_" + uuid.uuid4().hex[:8]
    session.execute(
        text(
            "INSERT INTO merchant (merchant_id, nickname, current_stage, status) "
            "VALUES (:m, '_test 商家', :s, :st)"
        ),
        {"m": merchant_id, "s": stage, "st": status},
    )
    session.commit()
    return merchant_id


def _cleanup(session, merchant_id: str) -> None:
    session.execute(text("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM merchant WHERE merchant_id = :m"), {"m": merchant_id})
    session.commit()


def test_active_merchant_is_allowed(client, session):
    """对照组:status=1(正常)商家访问同样接口应全部放行(与禁用组形成对照)。"""
    merchant_id = _make_merchant(session, status=1)
    try:
        for method, path, payload in READ_ENDPOINTS:
            resp = client.request(method, path, headers=_headers(merchant_id), json=payload)
            assert resp.status_code == 200, (method, path, resp.status_code, resp.text)
    finally:
        _cleanup(session, merchant_id)


@pytest.mark.xfail(reason=_XFAIL_REASON, strict=True)
def test_disabled_merchant_token_is_rejected(client, session):
    """status=0(禁用)商家,旧 token 访问任何商家端读接口 -> 403。"""
    merchant_id = _make_merchant(session, status=0)
    try:
        leaked = []
        for method, path, payload in READ_ENDPOINTS:
            resp = client.request(method, path, headers=_headers(merchant_id), json=payload)
            if resp.status_code != 403:
                leaked.append((method, path, resp.status_code))
        assert not leaked, f"禁用商家的 token 未被拦截(仍可访问): {leaked}"
    finally:
        _cleanup(session, merchant_id)


@pytest.mark.xfail(reason=_XFAIL_REASON, strict=True)
def test_exited_merchant_token_is_rejected(client, session):
    """status=2(已退出)商家,旧 token 访问 /api/merchant/info -> 403。"""
    merchant_id = _make_merchant(session, status=2)
    try:
        resp = client.get("/api/merchant/info", headers=_headers(merchant_id))
        assert resp.status_code == 403, resp.text
    finally:
        _cleanup(session, merchant_id)


@pytest.mark.xfail(reason=_XFAIL_REASON, strict=True)
def test_disabled_merchant_cannot_write(client, session):
    """禁用商家的写路径必须被拒,且不得落库。"""
    merchant_id = _make_merchant(session, status=0)
    try:
        resp = client.put(
            "/api/merchant/registration",
            headers=_headers(merchant_id),
            json={"shop_name": "测试店铺"},
        )
        assert resp.status_code == 403, resp.text
        session.commit()
        written = session.execute(
            text("SELECT shop_name FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
        assert written is None, f"禁用商家的写入被落库: {written!r}"
    finally:
        _cleanup(session, merchant_id)
