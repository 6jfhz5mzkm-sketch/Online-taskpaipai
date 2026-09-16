"""文档端点生产收口回归:DEBUG=True 可访问;DEBUG=False(生产)关闭 /docs /redoc /openapi.json。

对齐 NestJS backend/src/main.ts:47(仅非生产环境注册 Swagger)。
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_PROD_PROBE = (
    "import os, sys\n"
    "sys.path.insert(0, os.getcwd())\n"
    "from fastapi.testclient import TestClient\n"
    "from app.main import app\n"
    "with TestClient(app) as c:\n"
    "    print('STARTED')\n"
    "    print('docs=' + str(c.get('/docs').status_code))\n"
    "    print('redoc=' + str(c.get('/redoc').status_code))\n"
    "    print('openapi=' + str(c.get('/openapi.json').status_code))\n"
    "    print('health=' + str(c.get('/health').status_code))\n"
)


def test_docs_available_in_dev(client):
    """dev(DEBUG=True):三个文档端点保持可访问。"""
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert client.get("/openapi.json").status_code == 200


def test_docs_disabled_when_debug_false(monkeypatch):
    """DEBUG=False:不注册文档端点(404),健康检查不受影响。"""
    from fastapi.testclient import TestClient

    from app import main as main_module

    monkeypatch.setattr(main_module.settings, "DEBUG", False)
    prod_app = main_module.create_app()
    c = TestClient(prod_app)
    assert c.get("/docs").status_code == 404
    assert c.get("/redoc").status_code == 404
    assert c.get("/openapi.json").status_code == 404
    assert c.get("/health").status_code == 200


def test_docs_state_codes_in_production_subprocess():
    """真实生产环境(DEBUG=False + 合法密钥)下的状态码实测。"""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"   # 子进程输出固定 UTF-8,避免 Windows GBK 解码失败
    env.update({
        "LOGIN_MODE": "real", "DEBUG": "False",
        "JWT_SECRET": "a" * 64, "ADMIN_JWT_SECRET": "b" * 64,
        "DB_PASS": "strong-db-pass",
        "FEISHU_APP_ID": "cli_real_app", "FEISHU_APP_SECRET": "real-feishu-secret",
    })
    result = subprocess.run(
        [sys.executable, "-c", _PROD_PROBE], cwd=ROOT, env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    )
    assert result.returncode == 0, result.stderr
    assert "STARTED" in result.stdout
    assert "docs=404" in result.stdout
    assert "redoc=404" in result.stdout
    assert "openapi=404" in result.stdout
    assert "health=200" in result.stdout
