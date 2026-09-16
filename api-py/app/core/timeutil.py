"""时间序列化:对齐 NestJS(MySQL DATETIME 解释为服务器本地时区 → JS Date → toISOString → UTC ISO-8601 ms + Z)。

本地开发库/服务器时区为 UTC+8(北京);NestJS 将 DATETIME 按本地时区解释后转 UTC。
此处按同样规则:naive datetime 视为 UTC+8,转 UTC 后输出 "YYYY-MM-DDTHH:MM:SS.mmmZ"。
"""
from datetime import datetime, timedelta, timezone

_LOCAL_TZ = timezone(timedelta(hours=8))  # 服务器本地时区(北京 UTC+8)


def to_iso_utc(dt: datetime | None) -> str | None:
    """把 naive datetime(服务器本地时区)按 UTC+8 解释,转 UTC,输出 ms+Z 的 ISO 串。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_LOCAL_TZ)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
