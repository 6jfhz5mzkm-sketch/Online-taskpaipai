"""埋点统计服务(对齐 backend event.service.stats:管理端统计,≤90 天)。

统计 SQL 复刻 NestJS dataSource.query;响应结构与字节完全一致。
"""
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session

from app.core.exceptions import ApiException

MAX_SPAN_MS = 90 * 86400000


def _count_event(db: Session, event_type: str, start_at: str, end_at: str) -> int:
    r = db.execute(
        text("SELECT COUNT(*) AS c FROM event_log WHERE event_type = :e AND created_at BETWEEN :a AND :b"),
        {"e": event_type, "a": start_at, "b": end_at},
    ).mappings().first()
    return int(r["c"] or 0)


def _count_events(db: Session, types: List[str], start_at: str, end_at: str) -> int:
    r = db.execute(
        text(
            "SELECT COUNT(*) AS c FROM event_log WHERE event_type IN :types AND created_at BETWEEN :a AND :b"
        ).bindparams(bindparam("types", expanding=True)),
        {"types": tuple(types), "a": start_at, "b": end_at},
    ).mappings().first()
    return int(r["c"] or 0)


def _count_uv(db: Session, event_type: str, start_at: str, end_at: str) -> int:
    r = db.execute(
        text(
            "SELECT COUNT(DISTINCT COALESCE(NULLIF(merchant_id, ''), CONCAT(ip, '|', user_agent))) AS c "
            "FROM event_log WHERE event_type = :e AND created_at BETWEEN :a AND :b"
        ),
        {"e": event_type, "a": start_at, "b": end_at},
    ).mappings().first()
    return int(r["c"] or 0)


def _trend_rows(db: Session, event_type: str, start_at: str, end_at: str, group_by: str) -> List[Dict[str, Any]]:
    date_expr = (
        "DATE_FORMAT(DATE_SUB(created_at, INTERVAL WEEKDAY(created_at) DAY), '%Y-%m-%d')"
        if group_by == "week"
        else "DATE_FORMAT(created_at, '%Y-%m-%d')"
    )
    rows = db.execute(
        text(
            f"SELECT {date_expr} AS d, COUNT(*) AS pv, "
            "COUNT(DISTINCT COALESCE(NULLIF(merchant_id, ''), CONCAT(ip, '|', user_agent))) AS uv "
            "FROM event_log WHERE event_type = :e AND created_at BETWEEN :a AND :b GROUP BY d ORDER BY d"
        ),
        {"e": event_type, "a": start_at, "b": end_at},
    ).mappings().all()
    return [{"date": str(r["d"])[:10], "pv": int(r["pv"] or 0), "uv": int(r["uv"] or 0)} for r in rows]


def _page_rows(db: Session, event_type: str, start_at: str, end_at: str) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT page_name AS pn, COUNT(*) AS pv, "
            "COUNT(DISTINCT COALESCE(NULLIF(merchant_id, ''), CONCAT(ip, '|', user_agent))) AS uv "
            "FROM event_log WHERE event_type = :e AND page_name IS NOT NULL AND created_at BETWEEN :a AND :b "
            "GROUP BY pn ORDER BY pv DESC LIMIT 20"
        ),
        {"e": event_type, "a": start_at, "b": end_at},
    ).mappings().all()
    return [{"page_name": r["pn"], "pv": int(r["pv"] or 0), "uv": int(r["uv"] or 0)} for r in rows]


def _task_rows(db: Session, start_at: str, end_at: str) -> List[Dict[str, Any]]:
    rows = db.execute(
        text(
            "SELECT task_key AS tk, SUM(event_type = 'task_complete') AS complete_count, "
            "SUM(event_type = 'task_expand') AS expand_count "
            "FROM event_log WHERE event_type IN ('task_complete', 'task_expand') AND task_key IS NOT NULL "
            "AND created_at BETWEEN :a AND :b GROUP BY tk ORDER BY complete_count DESC LIMIT 50"
        ),
        {"a": start_at, "b": end_at},
    ).mappings().all()
    return [{"task_key": r["tk"], "complete_count": int(r["complete_count"] or 0), "expand_count": int(r["expand_count"] or 0)} for r in rows]


def stats(db: Session, start_date: str, end_date: str, event_type: str | None = None, group_by: str = "day") -> Dict[str, Any]:
    try:
        span_days = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days
    except ValueError:
        raise ApiException("日期格式不合法", code=400, status_code=400)
    if span_days < 0 or span_days > 90:
        raise ApiException("查询范围不能超过90天", code=400, status_code=400)

    start_at = f"{start_date} 00:00:00"
    end_at = f"{end_date} 23:59:59"
    event_src = event_type or "page_view"

    pv = _count_event(db, event_src, start_at, end_at)
    uv = _count_uv(db, event_src, start_at, end_at)
    task_complete_count = _count_event(db, "task_complete", start_at, end_at)
    task_denominator = _count_events(db, ["task_view", "task_expand", "task_complete"], start_at, end_at)
    task_complete_rate = round((task_complete_count / task_denominator) * 100, 2) if task_denominator > 0 else 0

    trend = _trend_rows(db, event_src, start_at, end_at, group_by)
    page_distribution = _page_rows(db, event_src, start_at, end_at)
    task_stats = _task_rows(db, start_at, end_at)

    return {
        "date_range": {"start_date": start_date, "end_date": end_date},
        "summary": {
            "pv": pv,
            "uv": uv,
            "task_complete_count": task_complete_count,
            "task_complete_rate": task_complete_rate,
        },
        "trend": trend,
        "page_distribution": page_distribution,
        "task_stats": task_stats,
    }
