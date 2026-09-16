"""API-07 保存商家经营类目回归(#PB-11)。

真源:project/docs/后端技术方案.md §5.2 API-07(POST /api/merchant/category)。
校验:1-3 个 / is_primary 唯一 / category_id 必须存在 / 重复去重;覆盖式写入 + event_log。
隔离:临时商家(make_temp_merchant)+ finally 清理 merchant_category / event_log 临时行。
"""

import json

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

PATH = "/api/merchant/category"


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _category_ids(session, limit: int = 4):
    rows = session.execute(
        text("SELECT id FROM category WHERE deleted_at IS NULL ORDER BY id LIMIT :n"), {"n": limit}
    ).scalars().all()
    assert len(rows) == limit, rows
    return [int(r) for r in rows]


def _rows(session, merchant_id: str):
    # MySQL 默认 REPEATABLE READ:测试会话若已开事务(如前面的 SELECT),快照会看不到接口刚提交的数据,
    # 故先 commit 结束当前只读事务,再读最新已提交状态。
    session.commit()
    return session.execute(
        text("SELECT category_id, is_primary FROM merchant_category WHERE merchant_id = :m ORDER BY category_id"),
        {"m": merchant_id},
    ).mappings().all()


def _events(session, merchant_id: str):
    session.commit()
    return session.execute(
        text("SELECT event_type, element, meta FROM event_log WHERE merchant_id = :m ORDER BY id"), {"m": merchant_id}
    ).mappings().all()


def _cleanup(session, merchant_id: str) -> None:
    session.execute(text("DELETE FROM merchant_category WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(text("DELETE FROM event_log WHERE merchant_id = :m"), {"m": merchant_id})
    session.commit()
    cleanup_temp_merchant(session, merchant_id)


def test_save_categories_success_and_overwrite(client, session):
    """成功路径:1 个主营 + 1 个非主营 -> 落库 2 行 + 埋点;再次提交为覆盖式(旧记录被删)。"""
    merchant_id = make_temp_merchant(session)
    try:
        first, second, third = _category_ids(session, 3)

        resp = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": first, "is_primary": True}, {"category_id": second, "is_primary": False}]},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"] == {"success": True, "count": 2}

        rows = _rows(session, merchant_id)
        assert [(r["category_id"], r["is_primary"]) for r in rows] == [(first, 1), (second, 0)]

        events = _events(session, merchant_id)
        assert len(events) == 1, events
        assert events[0]["event_type"] == "category_select"
        assert events[0]["element"] == "save_merchant_categories"
        assert json.loads(events[0]["meta"])["categoryIds"] == [first, second]

        # 覆盖式:第二次提交只保留新记录
        resp2 = client.post(
            PATH, headers=_headers(merchant_id), json={"categories": [{"category_id": third, "is_primary": True}]}
        )
        assert resp2.status_code == 201, resp2.text
        assert resp2.json()["data"]["count"] == 1
        assert [(r["category_id"], r["is_primary"]) for r in _rows(session, merchant_id)] == [(third, 1)]
        assert len(_events(session, merchant_id)) == 2
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_boundaries(client, session):
    """边界:1 个与 3 个都放行。"""
    merchant_id = make_temp_merchant(session)
    try:
        ids = _category_ids(session, 3)
        one = client.post(PATH, headers=_headers(merchant_id), json={"categories": [{"category_id": ids[0], "is_primary": True}]})
        assert one.status_code == 201 and one.json()["data"]["count"] == 1
        three = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": i, "is_primary": i == ids[0]} for i in ids]},
        )
        assert three.status_code == 201 and three.json()["data"]["count"] == 3
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_rejects_over_limit(client, session):
    """4 个不同类目 -> 400「请选择1-3个类目」,且不写库。"""
    merchant_id = make_temp_merchant(session)
    try:
        ids = _category_ids(session, 4)
        resp = client.post(
            PATH, headers=_headers(merchant_id), json={"categories": [{"category_id": i, "is_primary": i == ids[0]} for i in ids]}
        )
        assert resp.status_code == 400, resp.text
        assert resp.json() == {"code": 400, "message": "请选择1-3个类目", "data": None}
        assert _rows(session, merchant_id) == []
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_rejects_multiple_primary(client, session):
    """两个 is_primary=true -> 400「只能选择一个主营类目」。"""
    merchant_id = make_temp_merchant(session)
    try:
        first, second = _category_ids(session, 2)
        resp = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": first, "is_primary": True}, {"category_id": second, "is_primary": True}]},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == "只能选择一个主营类目"
        assert _rows(session, merchant_id) == []
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_rejects_unknown_category(client, session):
    """category_id 不存在 -> 400「类目不存在」。"""
    merchant_id = make_temp_merchant(session)
    try:
        valid = _category_ids(session, 1)[0]
        resp = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": valid, "is_primary": True}, {"category_id": 999999999, "is_primary": False}]},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json()["message"] == "类目不存在"
        assert _rows(session, merchant_id) == []
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_dedupes(client, session):
    """重复选择去重:3 项含 1 个重复 -> 落库 2 行,is_primary 取「或」。"""
    merchant_id = make_temp_merchant(session)
    try:
        first, second = _category_ids(session, 2)
        resp = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={
                "categories": [
                    {"category_id": first, "is_primary": False},
                    {"category_id": first, "is_primary": True},
                    {"category_id": second, "is_primary": False},
                ]
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["count"] == 2
        assert [(r["category_id"], r["is_primary"]) for r in _rows(session, merchant_id)] == [(first, 1), (second, 0)]
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_requires_categories_field(client, session):
    """缺 categories 字段 -> 400(必填数组)。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.post(PATH, headers=_headers(merchant_id), json={})
        assert resp.status_code == 400, resp.text
        assert resp.json()["code"] == 400
        empty = client.post(PATH, headers=_headers(merchant_id), json={"categories": []})
        assert empty.status_code == 400
        assert empty.json()["message"] == "请选择1-3个类目"
    finally:
        _cleanup(session, merchant_id)


def test_save_categories_requires_merchant_token(client):
    """无 token -> 401(商家 JWT 守卫)。"""
    resp = client.post(PATH, json={"categories": [{"category_id": 1, "is_primary": True}]})
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 401


def test_get_categories_empty_when_no_record(client, session):
    """查询侧:无记录 -> 200 + 空数组(code:0,非 404)。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.get(PATH, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"code": 0, "message": "success", "data": {"success": True, "categories": []}}
    finally:
        _cleanup(session, merchant_id)


def test_get_categories_returns_saved_with_primary_flag(client, session):
    """查询侧:保存 2 个后再查 -> 返回 2 条、is_primary 正确、主营在前。"""
    merchant_id = make_temp_merchant(session)
    try:
        first, second = _category_ids(session, 2)
        saved = client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": first, "is_primary": True}, {"category_id": second, "is_primary": False}]},
        )
        assert saved.status_code == 201, saved.text

        resp = client.get(PATH, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"] == {
            "success": True,
            "categories": [
                {"category_id": first, "is_primary": True},
                {"category_id": second, "is_primary": False},
            ],
        }
    finally:
        _cleanup(session, merchant_id)


def test_get_categories_after_overwrite_returns_new_set(client, session):
    """查询侧:覆盖式保存后 -> 只返回新集合(旧记录不再出现)。"""
    merchant_id = make_temp_merchant(session)
    try:
        first, second, third = _category_ids(session, 3)
        client.post(
            PATH,
            headers=_headers(merchant_id),
            json={"categories": [{"category_id": first, "is_primary": True}, {"category_id": second, "is_primary": False}]},
        )
        client.post(PATH, headers=_headers(merchant_id), json={"categories": [{"category_id": third, "is_primary": True}]})

        resp = client.get(PATH, headers=_headers(merchant_id))
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["categories"] == [{"category_id": third, "is_primary": True}]
    finally:
        _cleanup(session, merchant_id)


def test_get_categories_requires_merchant_token(client):
    """查询侧:无 token -> 401。"""
    resp = client.get(PATH)
    assert resp.status_code == 401, resp.text
    assert resp.json()["code"] == 401
