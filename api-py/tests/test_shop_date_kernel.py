"""日期解析唯一 owner(parse_data_date)白名单/黑名单/范围回归(#PB-24-1)。

口径真源:dev-docs/任务单/PB24-日期与数值校验方案.md §8(§8.4 白名单 W1–W7 与区间取结束日;§8.1 `-`=NULL)。
本文件**纯函数、不连库**:只断言解析结果与结构化 reason 枚举;失败策略(表单 400 / Excel 跳过该行)
由 §8 的调用方用例与接口验收覆盖(见 #PB-24-1 验收 14/15)。
"""

from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from app.services.shop import (
    DATE_PARSE_REASONS,
    MAX_DATA_DATE_TOLERANCE_DAYS,
    MIN_DATA_DATE,
    NO_DATA_MARKERS,
    DataDateParseError,
    parse_data_date,
)


def _reason(value):
    """驱动一次解析并返回结构化 reason(顺便断言确实抛了 DataDateParseError)。"""
    with pytest.raises(DataDateParseError) as excinfo:
        parse_data_date(value)
    return excinfo.value.reason


# ---------- 白名单 W1–W7:每个形态至少一个正例 ----------

def test_w1_excel_date_cells_are_normalized():
    assert parse_data_date(datetime(2026, 9, 14, 13, 45)) == "2026-09-14"
    assert parse_data_date(date(2026, 9, 14)) == "2026-09-14"


@pytest.mark.parametrize("raw,expected", [
    ("2026-09-14", "2026-09-14"),      # W2
    ("2026-9-8", "2026-09-08"),        # W2 非补零
    ("2026/09/14", "2026-09-14"),      # W3
    ("2026/9/8", "2026-09-08"),        # W3 非补零
    ("2026.09.14", "2026-09-14"),      # W4
])
def test_w2_w3_w4_separated_forms(raw, expected):
    assert parse_data_date(raw) == expected


@pytest.mark.parametrize("raw", ["20260914", 20260914, 20260914.0])
def test_w5_compact_eight_digits(raw):
    assert parse_data_date(raw) == "2026-09-14"


@pytest.mark.parametrize("raw", [
    "2026-09-14 13:45:00",
    "2026-09-14T13:45:00",
    "2026-09-14T13:45:00.000Z",
    "2026/9/8 13:45",
])
def test_w6_time_suffix_takes_date_part(raw):
    assert parse_data_date(raw) in ("2026-09-14", "2026-09-08")


def test_w6_does_not_accept_time_suffix_on_compact_form():
    """W5 必须恰好 8 位:`20260805 13:45:00` 不接受(与方案 §4.1.1/§8.4 口径一致)。"""
    assert _reason("20260805 13:45:00") == "unparseable_date"


def test_w7_range_takes_end_date():
    """区间 `起~止` 取【结束日】(数据截止日;用户 2026-09-15 裁决)。"""
    assert parse_data_date("2026-09-14~2026-09-14") == "2026-09-14"   # 当日导出:首尾相同
    assert parse_data_date("2026-09-08~2026-09-14") == "2026-09-14"   # 近 7 天导出
    assert parse_data_date("2026-09-08 ~ 2026-09-14") == "2026-09-14"  # 允许空格
    assert parse_data_date("2026/9/8~2026.09.14") == "2026-09-14"     # 两端可各用白名单形态


def test_w7_range_requires_both_ends_valid():
    assert _reason("abc~2026-09-14") == "unparseable_date"
    assert _reason("2026-09-08~") == "missing_date"
    assert _reason("a~b~c") == "unparseable_date"    # 多段 `~` 不接受


# ---------- 黑名单 B1–B10:每个 reason 至少一个反例(断言枚举值) ----------

@pytest.mark.parametrize("raw,reason", [
    ("05/08/2026", "ambiguous_date_format"),           # B1 月在前
    ("05-08-2026", "ambiguous_date_format"),
    ("5/8/2026", "ambiguous_date_format"),
    ("26-08-05", "two_digit_year"),                    # B2 两位年份
    ("26/08/05", "two_digit_year"),
    ("26.08.05", "two_digit_year"),
    ("8/5", "missing_year"),                           # B3 无年份
    ("08-05", "missing_year"),
    ("2026-8", "incomplete_date"),                     # B4 缺日
    ("2026/08", "incomplete_date"),
    ("2026-02-30", "invalid_calendar_date"),           # B5 非真实日期
    ("2026-13-45", "invalid_calendar_date"),
    (45000, "date_serial_number_not_supported"),       # B6 Excel 序列号(数值单元格)
    (45000.5, "date_serial_number_not_supported"),
    ("45000", "date_serial_number_not_supported"),     # B6 文本序列号
    ("2026年8月5日", "unparseable_date"),               # B7 中文形态(不纳入白名单)
    ("2026-08-05abc", "unparseable_date"),             # B10 其它
    ("1999-12-31", "date_out_of_range"),               # B9 范围外(下限)
])
def test_blacklist_reasons(raw, reason):
    assert _reason(raw) == reason


@pytest.mark.parametrize("raw", ["", "   ", None, "-", "—", "–", "−", "－", "--", "/", "\\", "N/A", "NA", "n/a"])
def test_missing_date_reason_for_empty_and_no_data_markers(raw):
    """空 / 全空白 / 无数据标记(日期列)-> missing_date(调用方按坏行处理,绝不兜底成今天)。"""
    assert _reason(raw) == "missing_date"


def test_reason_enum_is_closed_and_unique():
    assert len(DATE_PARSE_REASONS) == len(set(DATE_PARSE_REASONS))
    assert set(DATE_PARSE_REASONS) == {
        "missing_date", "ambiguous_date_format", "two_digit_year", "missing_year", "incomplete_date",
        "invalid_calendar_date", "date_serial_number_not_supported", "date_out_of_range", "unparseable_date",
    }


# ---------- 范围:下限 2000-01-01;上限 服务器当天 + 1 天(时区容差) ----------

def test_min_data_date_constant():
    assert MIN_DATA_DATE == date(2000, 1, 1)
    assert MAX_DATA_DATE_TOLERANCE_DAYS == 1


def test_date_range_boundaries():
    today = date.today()
    assert parse_data_date("2000-01-01") == "2000-01-01"                                  # 下限含
    assert _reason("1999-12-31") == "date_out_of_range"                                    # 下限外
    upper = today + timedelta(days=MAX_DATA_DATE_TOLERANCE_DAYS)
    assert parse_data_date(upper.isoformat()) == upper.isoformat()                         # 上限含(+1 天容差)
    over = today + timedelta(days=MAX_DATA_DATE_TOLERANCE_DAYS + 1)
    assert _reason(over.isoformat()) == "date_out_of_range"                                # 上限外


def test_no_data_markers_are_explicit_whitelist():
    """`-` 等无数据标记是白名单式常量;未列出的形态仍按坏值(不吞真脏值)。"""
    assert "-" in NO_DATA_MARKERS and "N/A" in NO_DATA_MARKERS
    assert _reason("无数据") == "unparseable_date"


# ---------- 源码级回归:禁止「静默写今天」的兜底复活 ----------

def test_source_has_no_implicit_today_fallback():
    """#PB-24-1 删除了 `or datetime.now()` 兜底与 `str(val).strip()[:10]` 的隐式截断,禁止复活。"""
    source = (Path(__file__).resolve().parents[1] / "app" / "services" / "shop.py").read_text(encoding="utf-8")
    assert "or datetime.now()" not in source
    assert "str(val).strip()[:10]" not in source
    assert "data_date_span(val)" in source             # 日期仍走唯一 owner(#PB-24-2 起 Excel 侧取跨度产物,不重复解析)
    assert "time_range_from_span(" in source           # time_range 由文件日期跨度推导(不再取表单参数)
