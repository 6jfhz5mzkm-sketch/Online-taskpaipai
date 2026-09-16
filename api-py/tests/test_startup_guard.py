"""启动期配置 fail-fast 回归(部署上线前必做清单 6b / SEC-06)。

背景:修复前 config.py 带公开发布的 dev 兜底密钥且无启动期校验,生产式环境
(LOGIN_MODE=real + DEBUG=False + dev 密钥 + DB_PASS=root123)仍能正常启动,任何人可用公开
密钥离线自签商家/管理员 token。

覆盖:dev/mock 不阻断;非 dev(LOGIN_MODE=real 或 DEBUG=False)下 dev 兜底密钥、长度不足、
两 secret 相同、DB_PASS=root123、real 模式飞书凭证缺失/占位 均拒绝启动;合法生产配置通过。
真实启动路径用子进程验证(不依赖 sleep/临时 flag)。
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.config import ConfigurationError, Settings, validate_startup_settings

ROOT = Path(__file__).resolve().parents[1]
_STRONG_A = "a" * 64
_STRONG_B = "b" * 64
_DEV_MERCHANT_SECRET = "dev-secret-key-change-in-production"
_DEV_ADMIN_SECRET = "admin-secret-key-change-in-production"

_STARTUP_PROBE = (
    "import os, sys\n"
    "sys.path.insert(0, os.getcwd())\n"
    "from fastapi.testclient import TestClient\n"
    "from app.main import app\n"
    "with TestClient(app):\n"
    "    print('STARTED')\n"
)


def _settings(**overrides) -> Settings:
    """构造配置(不读 .env,避免本地文件干扰)。"""
    base = dict(
        LOGIN_MODE="real",
        DEBUG=False,
        JWT_SECRET=_STRONG_A,
        ADMIN_JWT_SECRET=_STRONG_B,
        DB_PASS="strong-db-pass",
        FEISHU_APP_ID="cli_real_app",
        FEISHU_APP_SECRET="real-feishu-secret",
    )
    base.update(overrides)
    return Settings(_env_file=None, **base)


def _run_startup(env_overrides: dict) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # 子进程 stderr 含中文校验原因,固定 UTF-8 避免 Windows GBK 解码失败
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", _STARTUP_PROBE], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )


# ---------- 判定逻辑 ----------

def test_dev_environment_is_not_blocked():
    """dev/mock(LOGIN_MODE=mock + DEBUG=True)带 dev 兜底密钥也照常启动。"""
    validate_startup_settings(_settings(
        LOGIN_MODE="mock", DEBUG=True, JWT_SECRET=_DEV_MERCHANT_SECRET,
        ADMIN_JWT_SECRET=_DEV_ADMIN_SECRET, DB_PASS="root123",
        FEISHU_APP_ID="", FEISHU_APP_SECRET=""))


def test_dev_fallback_secret_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(JWT_SECRET=_DEV_MERCHANT_SECRET))
    assert "JWT_SECRET" in str(exc.value)


def test_admin_dev_fallback_secret_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(ADMIN_JWT_SECRET=_DEV_ADMIN_SECRET))
    assert "ADMIN_JWT_SECRET" in str(exc.value)


def test_short_secret_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(ADMIN_JWT_SECRET="short-secret"))
    assert "ADMIN_JWT_SECRET" in str(exc.value)


def test_equal_secrets_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(ADMIN_JWT_SECRET=_STRONG_A))
    assert "不能相同" in str(exc.value)


def test_root_db_pass_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(DB_PASS="root123"))
    assert "DB_PASS" in str(exc.value)


def test_debug_false_mock_is_still_enforced():
    """LOGIN_MODE=mock 但 DEBUG=False 同属非 dev:公开 dev 密钥一样拒绝。"""
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(LOGIN_MODE="mock", DEBUG=False, JWT_SECRET=_DEV_MERCHANT_SECRET))
    assert "JWT_SECRET" in str(exc.value)


def test_real_mode_feishu_placeholder_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(FEISHU_APP_SECRET="your_feishu_app_secret"))
    assert "FEISHU_APP_SECRET" in str(exc.value)


def test_real_mode_missing_feishu_app_id_rejected():
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(FEISHU_APP_ID=""))
    assert "FEISHU_APP_ID" in str(exc.value)


def test_valid_production_settings_pass():
    validate_startup_settings(_settings())


# ---------- 真实启动路径(子进程) ----------

def test_subprocess_dev_mock_starts():
    result = _run_startup({"LOGIN_MODE": "mock", "DEBUG": "True"})
    assert result.returncode == 0, result.stderr
    assert "STARTED" in result.stdout


def test_subprocess_real_with_dev_fallback_refused():
    result = _run_startup({
        "LOGIN_MODE": "real", "DEBUG": "False",
        "JWT_SECRET": _DEV_MERCHANT_SECRET, "ADMIN_JWT_SECRET": _DEV_ADMIN_SECRET,
        "DB_PASS": "root123", "FEISHU_APP_ID": "", "FEISHU_APP_SECRET": "",
    })
    assert result.returncode != 0
    assert "STARTED" not in result.stdout
    assert "JWT_SECRET" in (result.stderr + result.stdout)


def test_subprocess_root_db_pass_refused():
    result = _run_startup({
        "LOGIN_MODE": "real", "DEBUG": "False",
        "JWT_SECRET": _STRONG_A, "ADMIN_JWT_SECRET": _STRONG_B,
        "DB_PASS": "root123", "FEISHU_APP_ID": "cli_real_app", "FEISHU_APP_SECRET": "real-feishu-secret",
    })
    assert result.returncode != 0
    assert "DB_PASS" in (result.stderr + result.stdout)


def test_subprocess_equal_secrets_refused():
    result = _run_startup({
        "LOGIN_MODE": "real", "DEBUG": "False",
        "JWT_SECRET": _STRONG_A, "ADMIN_JWT_SECRET": _STRONG_A,
        "DB_PASS": "strong-db-pass", "FEISHU_APP_ID": "cli_real_app", "FEISHU_APP_SECRET": "real-feishu-secret",
    })
    assert result.returncode != 0
    assert "不能相同" in (result.stderr + result.stdout)


# ---------- Q8:非 dev 禁 mock(密钥合规也必须拒绝) ----------

def test_non_dev_mock_login_mode_rejected():
    """非 dev(DEBUG=False)下 LOGIN_MODE=mock 一律拒绝,即使密钥全部合规。"""
    with pytest.raises(ConfigurationError) as exc:
        validate_startup_settings(_settings(LOGIN_MODE="mock", DEBUG=False))
    assert "LOGIN_MODE=mock" in str(exc.value)


def test_subprocess_non_dev_mock_refused():
    result = _run_startup({
        "LOGIN_MODE": "mock", "DEBUG": "False",
        "JWT_SECRET": _STRONG_A, "ADMIN_JWT_SECRET": _STRONG_B,
        "DB_PASS": "strong-db-pass", "FEISHU_APP_ID": "cli_real_app", "FEISHU_APP_SECRET": "real-feishu-secret",
    })
    assert result.returncode != 0
    assert "STARTED" not in result.stdout
    assert "LOGIN_MODE=mock" in (result.stderr + result.stdout)
