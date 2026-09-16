"""Excel 上传 MIME 与用户提示一致性回归(B7)。

背景:修复前 EXCEL_MIME 声明了 application/vnd.ms-excel(旧 .xls), MIME 校验通过后 openpyxl
必然解析失败(openpyxl 只支持 OOXML/.xlsx),用户看到的是"仅支持 .xlsx/.xls"却总是失败 ——
"提示支持但必然失败"的路径。
修复后:移除该 MIME 声明,提示明确要求 .xlsx(选择理由:真正支持 .xls 需引入 xlrd 等新依赖,
按任务边界不新增依赖)。

隔离:临时商家(阶段二解锁)。
"""

from app.core.security import create_merchant_token
from app.services.shop import EXCEL_MIME

from tests.conftest import cleanup_temp_merchant, make_temp_merchant

_XLS_MIME = "application/vnd.ms-excel"
_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _headers(merchant_id: str) -> dict:
    return {"Authorization": f"Bearer {create_merchant_token(merchant_id)}"}


def test_excel_mime_declaration_has_no_legacy_xls():
    """声明与能力一致:.xlsx 在列,.xls 不在列。"""
    assert _XLSX_MIME in EXCEL_MIME
    assert _XLS_MIME not in EXCEL_MIME


def test_legacy_xls_mime_rejected_with_actionable_message(client, session):
    """.xls(旧格式)被明确拒绝,提示指向 .xlsx。"""
    merchant_id = make_temp_merchant(session)
    try:
        resp = client.post(
            "/api/shop/trade",
            headers=_headers(merchant_id),
            files={"file": ("trade.xls", b"\xd0\xcf\x11\xe0fake-ole2-content", _XLS_MIME)},
            data={"timeRange": "7d"},
        )
        assert resp.status_code == 400, resp.text
        body = resp.json()
        assert body["code"] == 400
        assert ".xlsx" in body["message"], body["message"]
    finally:
        cleanup_temp_merchant(session, merchant_id)
