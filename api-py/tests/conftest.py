"""pytest 公共夹具。

隔离策略(不污染生产数据):
- 测试通过 FastAPI TestClient 打到本地开发 MySQL(merchant_task),与开发环境一致;
- 只读接口(类目/阶段/无 token 400 等)只读真实种子数据,零写入;
- 写路径(管理员登录、店铺 Excel 上传)使用**临时实体**(随机后缀的临时管理员/临时商家),
  在测试 finally 中删除,测试结束后不留任何旁路数据;
- 商家登录(LOGIN_MODE=mock)固定 mock_merchant_001,该商家为专用 mock 测试商家,登录仅幂等更新 last_active_at。

日志:临时实体统一以 _test_ 前缀 + uuid 短后缀命名,便于识别与兜底清理。
"""

import itertools
import os
import uuid

# 必须在导入 app 前设置:登录模式固定 mock(商家登录走 mock 降级,不触发真实飞书 OAuth)
os.environ["LOGIN_MODE"] = "mock"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.engine import SessionLocal
from app.core.security import hash_password
from app.db.models.admin_account import AdminAccount
from app.db.models.merchant import Merchant

MOCK_MERCHANT_ID = "mock_merchant_001"
TEST_ADMIN_PASSWORD = "Test@12345"

# 兜底清理:上一轮异常退出遗留的临时前缀行
_TEST_PREFIXES = ("_test_",)


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture(autouse=True)
def reset_process_local_auth_state():
    """隔离进程内认证状态(登录请求限流 + 登录失败锁定),每个用例前后各清空一次。

    这两处状态是进程内内存态(见 app/services/auth.py),TestClient 的客户端 IP 固定为
    "testclient",若不清理会跨用例累计,造成「与执行顺序相关」的假失败。
    清理只作用于测试进程的内存计数,不改变生产行为;用例内部的状态累积仍照常生效。
    """
    from app.services.auth import reset_process_local_auth_state as _reset

    _reset()
    yield
    _reset()


# 登录防护用例的客户端 IP 分配器(每个用例一个唯一 IP,见 login_client)
_LOGIN_CLIENT_IP_COUNTER = itertools.count(1)


@pytest.fixture()
def login_client():
    """登录防护用例专用客户端:每个用例独占一个客户端 IP,自带干净的限流预算。

    登录请求限流的 ip 预算(ADMIN_LOGIN_RATE_MAX 次 / ADMIN_LOGIN_RATE_WINDOW_SECONDS 秒)
    按 ip:<client_ip> 记账;若所有用例共用默认的 "testclient",任一用例多打几次请求就会吃掉
    后面用例的预算,使「第 N 次请求」的语义随全局调用次数漂移(表现为与执行顺序相关的假失败,
    或被「限流文案」顶掉真实断言)。本夹具按调用次序分配唯一 IP。
    用户名维度的失败计数仍由 autouse 的 reset_process_local_auth_state 清空。
    """
    n = next(_LOGIN_CLIENT_IP_COUNTER)
    client_address = (f"10.72.{n // 250}.{n % 250 + 1}", 50000)
    with TestClient(app, client=client_address) as c:
        yield c


@pytest.fixture()
def client():
    """FastAPI TestClient(使用真实 get_db -> 本地 dev MySQL merchant_task)。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def session():
    """独立会话,用于临时实体插入与清理(写路径)。"""
    s = SessionLocal()
    yield s
    s.close()


def make_temp_admin(session, username=None, password=TEST_ADMIN_PASSWORD):
    """插入临时管理员,返回 username/password(登录测试用,finally 需 cleanup_temp_admin)。"""
    username = username or "_test_admin_" + _suffix()
    enc, salt = hash_password(password)
    session.add(AdminAccount(username=username, passwordHash=enc, salt=salt, realName="测试管理员", role="admin", status=1))
    session.commit()
    return username, password


def cleanup_temp_admin(session, username):
    session.execute(
        __import__("sqlalchemy").text("DELETE FROM admin_account WHERE username = :u"),
        {"u": username},
    )
    session.commit()


def make_temp_merchant(session, merchant_id=None, current_stage="shop_setup", status=1):
    """插入临时商家(默认 shop_setup=阶段二解锁,供 Excel 上传),返回 merchant_id。

    阶段/状态可覆盖(#PB-24 管理端列表筛选用例需要 onboarding 与 status=0/2 的样本);
    默认值保持不变,既有调用方零影响。
    """
    merchant_id = merchant_id or "_test_shop_" + _suffix()
    session.add(Merchant(
        merchant_id=merchant_id, nickname="测试商家", current_stage=current_stage, status=status
    ))
    session.commit()
    return merchant_id


def cleanup_temp_merchant(session, merchant_id):
    """删除临时商家及其全部派生数据(6 张 shop_* 表 + 2 张进度表,幂等)。

    进度表必须一并清理:update_progress 经 derive_phase2_unlock 会写
    merchant_stage_progress(onboarding/shop_setup)与 merchant_task_progress,
    只删 merchant 会留下孤儿进度行污染真实库(实测残留 14 行)。
    """
    t = __import__("sqlalchemy").text
    for table in ("shop_star_data", "shop_trade_data", "shop_traffic_data", "shop_product_data",
                  "shop_product_count", "shop_health_score"):
        session.execute(t("DELETE FROM " + table + " WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(t("DELETE FROM merchant_stage_progress WHERE merchant_id = :m"), {"m": merchant_id})
    session.execute(t("DELETE FROM merchant_task_progress WHERE merchantId = :m"), {"m": merchant_id})
    session.execute(t("DELETE FROM merchant WHERE merchant_id = :m"), {"m": merchant_id})
    session.commit()
