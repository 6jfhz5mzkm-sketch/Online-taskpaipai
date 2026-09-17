"""数据编码巡检纯函数回归(#PB-15)。

被测:api-py/scripts/check_data_encoding.py 的 detect_mojibake / decode_back / has_cjk /
is_sensitive_column / _quote_identifier(纯函数,不连库)。
覆盖:CP1252 形态、latin1 形态、正常中文不误判、URL 查询串不误判、敏感列识别与标识符拒绝拼接。

关于样例构造:#DB-10 §13 文档里写的 `è¶…çº§ç®¡ç†å‘˜` 是**渲染有损**的样例 —— 真实数据在
「理」的 UTF-8 字节 `E7 90 86` 处含 **0x90**,而 0x90 在 CP1252 中未定义,文档回显时把该
控制字符 U+0090 丢了,因此该字面串本身不是合法的双重编码形态(见下方断言)。用例改用
`_cp1252_mojibake()` 构造等价形态,以覆盖真实数据必然走的「latin1 序值回退」分支。
"""

import importlib.util
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_data_encoding.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("check_data_encoding", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


encoding = _load_script_module()

DB10_DECODED = "超级管理员"
# #DB-10 文档中的样例(渲染有损:缺失 U+0090),保留用于「不得据此误判」的回归
DB10_DOC_LITERAL = "è¶…çº§ç®¡ç†å‘˜"


def _cp1252_mojibake(text: str) -> str:
    """构造「UTF-8 字节被按 CP1252 解释后再存为 UTF-8」的形态。

    0x81/0x8D/0x8F/0x90/0x9D 在 CP1252 未定义 → 按 latin1 序值回退为对应控制字符
    (这正是生产数据的真实形态,也是只用 latin1 规则会漏检、只用 CP1252 规则会报错的位置)。
    """
    out = []
    for byte in text.encode("utf-8"):
        try:
            out.append(bytes([byte]).decode("cp1252"))
        except UnicodeDecodeError:
            out.append(chr(byte))
    return "".join(out)


def test_cp1252_form_detected():
    """CP1252 形态:必须命中;且该形态是「CP1252 特有映射 + latin1 序值回退」的混合体。"""
    sample = _cp1252_mojibake(DB10_DECODED)
    assert sample != DB10_DECODED
    # CP1252 特有映射的证据:… (U+2026, 来自 0x85) 与 ‘ (U+2018, 来自 0x91)
    assert "\u2026" in [hex(ord(c)) for c in sample] or any(ord(c) == 0x2026 for c in sample)
    assert any(ord(c) == 0x2018 for c in sample)
    # latin1 无法整体编回(…超出 latin1) → 只用 latin1 规则必然漏检
    with pytest.raises(UnicodeEncodeError):
        sample.encode("latin1")
    assert encoding.detect_mojibake(sample) == DB10_DECODED

    assert encoding.detect_mojibake(_cp1252_mojibake("我已了解")) == "我已了解"


def test_doc_literal_is_lossy_and_not_a_valid_mojibake():
    """#DB-10 文档样本文档渲染丢失了 U+0090 控制字符,该字面串不构成合法双重编码形态。"""
    assert encoding.detect_mojibake(DB10_DOC_LITERAL) is None


def test_latin1_form_detected_via_fallback():
    """latin1 形态(UTF-8 字节整体按 latin1 解释):同样命中。"""
    latin1_form = DB10_DECODED.encode("utf-8").decode("latin1")
    assert latin1_form != _cp1252_mojibake(DB10_DECODED)
    assert encoding.detect_mojibake(latin1_form) == DB10_DECODED


@pytest.mark.parametrize("normal", [DB10_DECODED, "我已了解", "测试商家", "正常中文", "嗯"])
def test_normal_chinese_not_flagged(normal):
    """正常中文不得误判。"""
    assert encoding.detect_mojibake(normal) is None


@pytest.mark.parametrize("url", [
    "https://example.com/a?b=c",
    "https://example.com/a?b=c&d=%20",
    "https://shop.jd.com/apply?code=123&from=task",
    "https://example.com/search?q=%E4%B8%AD%E6%96%87",
    "https://example.com/活动?from=task1",
])
def test_url_with_query_not_flagged(url):
    """含 ? 的 URL 查询串(含中文路径)不得误判 —— #DB-10 明确 second_level_task.actionUrl 的 '?' 属正常值。"""
    assert encoding.detect_mojibake(url) is None


@pytest.mark.parametrize("plain", ["", None, "admin@example.com", "<PHONE>", "mandatory", "2026-09-14"])
def test_non_text_or_ascii_not_flagged(plain):
    """空值/None/纯 ASCII 不得误判。"""
    assert encoding.detect_mojibake(plain) is None


def test_non_cjk_decode_result_not_flagged():
    """可编回但解码结果不含 CJK(如 é 的 CP1252 形态)不计入候选。"""
    assert encoding.decode_back("Ã©") == "é"
    assert encoding.detect_mojibake("Ã©") is None
    assert encoding.has_cjk("é") is False


def test_has_cjk_boundary():
    """CJK 边界:U+4E00 与 U+9FFF 算,紧邻两侧不算。"""
    assert encoding.has_cjk(DB10_DECODED) is True
    assert encoding.has_cjk(chr(0x4E00)) is True
    assert encoding.has_cjk(chr(0x9FFF)) is True
    assert encoding.has_cjk(chr(0x4DFF)) is False
    assert encoding.has_cjk(chr(0xA000)) is False
    assert encoding.has_cjk("A1") is False


@pytest.mark.parametrize("column,sensitive", [
    ("passwordHash", True), ("salt", True), ("access_token", True), ("refreshToken", True),
    ("app_secret", True), ("realName", False), ("content", False), ("actionUrl", False),
])
def test_sensitive_column_detection(column, sensitive):
    """敏感列识别:命中即只报计数,不回显值。"""
    assert encoding.is_sensitive_column(column) is sensitive


@pytest.mark.parametrize("hit_rows,report_only,expected", [
    (0, False, 0),   # 无命中 -> 通过
    (3, False, 1),   # 有命中 -> 门禁失败
    (3, True, 0),    # --report-only 恒 0
    (0, True, 0),
])
def test_gate_exit_code(hit_rows, report_only, expected):
    """退出码契约:0 无命中 / 1 有命中 / --report-only 恒 0。"""
    assert encoding.gate_exit_code(hit_rows, report_only) == expected


def test_env_error_exit_code_constant():
    """环境/输入错误用独立退出码 2(与 check_schema.py 同风格)。"""
    assert (encoding.EXIT_OK, encoding.EXIT_HITS, encoding.EXIT_ENV) == (0, 1, 2)


def test_identifier_quoting_rejects_backtick():
    """标识符拼接只接受 information_schema 里的正常名字,含反引号一律拒绝。"""
    assert encoding._quote_identifier("merchant") == "`merchant`"
    with pytest.raises(encoding.SchemaUnreadable):
        encoding._quote_identifier("bad`name")
