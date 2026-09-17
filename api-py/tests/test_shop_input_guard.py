"""店铺数据输入守卫回归(P0 数据完整性)。

口径:
- dataDate 走 parse_data_date 显式归一(唯一 owner):可识别的多种格式(YYYY/M/D、YYYY.M.D、
  YYYYMMDD、区间 `起~止` 取结束日)先归一为规范 YYYY-MM-DD 再落库;
  **仅白名单外「无法确定是哪一个真实日期」的形态才 400**,不得让脏值打到 DATE 列(避免 500 或脏数据);
- 负数/超大数值应被拒绝或跳过,不得落库,也不得把接口打成 500。

注:Excel 路径 parse_number/_to_num 不校验符号与上界,而目标列是 INT UNSIGNED / DECIMAL 定长。
    本文件把这些口径固化为回归,失败即代表缺口存在。

隔离:临时商家(make_temp_merchant)+ finally 经 cleanup_temp_merchant 清理(覆盖范围 =
     scripts/merchant_scope.py 的动态发现,不写死表数)。
"""

import io
from decimal import Decimal

from sqlalchemy import text

from app.core.security import create_merchant_token
from tests.conftest import cleanup_temp_merchant, make_temp_merchant

EXCEL_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DECIMAL_12_2_MAX = Decimal("9999999999.99")


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def _make_excel(rows) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio.read()


def _upload(client, merchant_id, rows, time_range="7d"):
    return client.post(
        "/api/shop/trade",
        headers=_headers(merchant_id),
        files={"file": ("trade.xlsx", _make_excel(rows), EXCEL_MIME)},
        data={"timeRange": time_range},
    )


# ---------- 正常路径:值必须正确落库 ----------

def test_valid_star_row_persists_exact_values(client, session):
    """合法日期 + 合法分值 -> 201,且 DB 内数值/日期与提交一致。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.post(
            "/api/shop/star",
            headers=_headers(merchant_id),
            json={"shopStar": 4.5, "serviceScore": 9.1, "dataDate": "2026-08-05"},
        )
        assert resp.status_code == 201, resp.text
        session.commit()
        row = session.execute(
            text("SELECT shop_star, service_score, data_date FROM shop_star_data WHERE merchant_id = :m"),
            {"m": merchant_id},
        ).mappings().first()
        assert row is not None, "合法数据未落库"
        assert row["shop_star"] == Decimal("4.5")
        assert row["service_score"] == Decimal("9.1")
        assert str(row["data_date"]) == "2026-08-05"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_same_merchant_date_is_idempotent(client, session):
    """同 (merchant_id, data_date) 重复上传 -> 覆盖而非新增(唯一键 uk_merchant_date)。"""
    merchant_id = make_temp_merchant(session)
    try:
        for star in (4.5, 3.0):
            resp = client.post(
                "/api/shop/star",
                headers=_headers(merchant_id),
                json={"shopStar": star, "dataDate": "2026-08-05"},
            )
            assert resp.status_code == 201, resp.text
        session.commit()
        rows = session.execute(
            text("SELECT shop_star FROM shop_star_data WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalars().all()
        assert len(rows) == 1, f"幂等失败,出现 {len(rows)} 行"
        assert rows[0] == Decimal("3.0"), f"覆盖值不正确: {rows[0]}"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_valid_excel_row_persists_exact_values(client, session):
    """合法 Excel -> 201 count=1,成交单量为整数、金额按 DECIMAL(12,2) 落库。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = _upload(client, merchant_id, [
            ["时间", "成交金额", "成交单量"],
            ["2026-08-05", "12345.6", "5"],
        ])
        assert resp.status_code == 201, resp.text
        assert resp.json()["data"]["count"] == 1
        session.commit()
        row = session.execute(
            text("SELECT trade_amount, trade_orders, time_range FROM shop_trade_data WHERE merchant_id = :m"),
            {"m": merchant_id},
        ).mappings().first()
        assert row is not None
        assert row["trade_amount"] == Decimal("12345.60")
        assert row["trade_orders"] == 5
        # #PB-24-2:time_range 由**文件日期跨度**推导(不再取表单参数);该文件只有一个日期 -> 单日桶
        assert row["time_range"] == "yesterday"
    finally:
        cleanup_temp_merchant(session, merchant_id)


# ---------- 边界/非法:日期归一(唯一 owner = app.services.shop.parse_data_date) ----------

def test_data_date_that_cannot_be_normalized_is_rejected(client, session):
    """不可归一的日期必须 400,且不得落库、不得 500。

    契约(用户裁决「日期接受多种格式并显式归一」+ #PB-24-1 落地):只有「无法确定是哪一个
    真实日期」的形态才拒绝 —— 月日顺序不可判定 / 两位年份 / 缺日 / 非真实日历日 / 空值。
    """
    merchant_id = make_temp_merchant(session)
    try:
        for bad in ("not-a-date", "2026-02-30", "", "05/08/2026", "26-08-05", "2026-8"):
            resp = client.post(
                "/api/shop/star",
                headers=_headers(merchant_id),
                json={"shopStar": 4.5, "dataDate": bad},
            )
            assert resp.status_code != 500, f"不可归一日期 {bad!r} 打成 500: {resp.text}"
            assert resp.status_code == 400, f"不可归一日期 {bad!r} 未被拒: {resp.status_code} {resp.text}"
        session.commit()
        n = session.execute(
            text("SELECT COUNT(*) FROM shop_star_data WHERE merchant_id = :m"), {"m": merchant_id}
        ).scalar()
        assert n == 0, f"不可归一日期写入了 {n} 行"
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_normalizable_data_date_persists_canonical_form(client, session):
    """可归一的多种日期格式必须 201,且库内 data_date 为规范 YYYY-MM-DD(区间取结束日)。"""
    merchant_id = make_temp_merchant(session)
    cases = (
        ("2026/8/5", "2026-08-05"),
        ("2026.8.5", "2026-08-05"),
        ("20260805", "2026-08-05"),
        ("2026-09-14~2026-09-14", "2026-09-14"),
    )
    try:
        for raw, expected in cases:
            resp = client.post(
                "/api/shop/star",
                headers=_headers(merchant_id),
                json={"shopStar": 4.5, "dataDate": raw},
            )
            assert resp.status_code == 201, f"可归一日期 {raw!r} 未被接受: {resp.status_code} {resp.text}"
            session.commit()
            stored = session.execute(
                text("SELECT data_date FROM shop_star_data WHERE merchant_id = :m AND data_date = :d"),
                {"m": merchant_id, "d": expected},
            ).scalar()
            assert stored is not None, f"日期 {raw!r} 未归一到 {expected}(库内无该 data_date 行)"
            assert str(stored) == expected, f"日期 {raw!r} 归一结果不符: {stored!r} != {expected!r}"
    finally:
        cleanup_temp_merchant(session, merchant_id)


# ---------- 边界/非法:负数与超大值 ----------

def test_excel_negative_count_is_rejected_or_skipped(client, session):
    """Excel 负数计数:不得落库为负,也不得打成 500(列是 INT UNSIGNED)。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = _upload(client, merchant_id, [
            ["时间", "成交单量"],
            ["2026-08-05", -5],
        ])
        assert resp.status_code != 500, f"Excel 负数打成 500: {resp.text}"
        session.commit()
        row = session.execute(
            text("SELECT trade_orders FROM shop_trade_data WHERE merchant_id = :m"), {"m": merchant_id}
        ).mappings().first()
        assert row is None or row["trade_orders"] is None or row["trade_orders"] >= 0, (
            f"负数落库: {row}"
        )
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_excel_oversize_decimal_is_rejected_or_clamped_safely(client, session):
    """Excel 超大金额(超 DECIMAL(12,2)):不得 500,落库值不得超过列上界。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = _upload(client, merchant_id, [
            ["时间", "成交金额"],
            ["2026-08-05", 99999999999],
        ])
        assert resp.status_code != 500, f"Excel 超大值打成 500: {resp.text}"
        session.commit()
        row = session.execute(
            text("SELECT trade_amount FROM shop_trade_data WHERE merchant_id = :m"), {"m": merchant_id}
        ).mappings().first()
        if row is not None and row["trade_amount"] is not None:
            assert Decimal(row["trade_amount"]) <= DECIMAL_12_2_MAX, f"超界值落库: {row}"
    finally:
        cleanup_temp_merchant(session, merchant_id)


# ---------- 异常/非法:格式与门禁 ----------

def test_excel_legacy_xls_mime_is_rejected(client, session):
    """旧版 .xls MIME -> 400 且提示另存为 .xlsx。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.post(
            "/api/shop/trade",
            headers=_headers(merchant_id),
            files={"file": ("trade.xls", _make_excel([["时间", "成交单量"], ["2026-08-05", "1"]]),
                            "application/vnd.ms-excel")},
            data={"timeRange": "7d"},
        )
        assert resp.status_code == 400, resp.text
        assert "xlsx" in resp.json()["message"]
    finally:
        cleanup_temp_merchant(session, merchant_id)


def test_shop_summary_requires_phase2_unlock(client, session):
    """阶段二未解锁的商家读 summary -> 403。"""
    # #T-20-R3:统一走 conftest 助手(此前自写 INSERT + 只删 merchant,漏其余作用域表)
    merchant_id = make_temp_merchant(session, current_stage="onboarding")
    try:
        resp = client.get("/api/shop/summary?time_range=7d", headers=_headers(merchant_id))
        assert resp.status_code == 403, resp.text
        assert resp.json()["code"] == 403
    finally:
        cleanup_temp_merchant(session, merchant_id)
