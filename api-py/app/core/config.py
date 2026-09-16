"""全局配置。

读取顺序:pydantic-settings 默认读 api-py/ 下 .env(未提交),再叠加真实环境变量;
未提供时使用开发默认值(与 NestJS data-source.ts 默认一致)。
"""
from functools import lru_cache
from pathlib import Path
from typing import List
from urllib.parse import quote_plus

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 项目根(api-py/):config.py 位于 app/core/ -> 上溯两级 app/, 三级 api-py/
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置。所有字段均有开发默认值,生产通过 .env 覆盖。"""

    # ---- 应用 ----
    APP_NAME: str = "商家成长任务体系 API"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    # `api` 命名空间的日志级别(#PB-23-R5;默认 INFO,生产可设 WARNING 降噪)。见 app/main.py::_configure_logging
    LOG_LEVEL: str = "INFO"
    # 登录模式:mock=本地开发(固定 mock_merchant_001)/real=真实飞书 OAuth(生产强制,mock 会致未登录越权,见 SEC-01)
    LOGIN_MODE: str = "mock"

    # ---- 服务 ----
    HOST: str = "127.0.0.1"
    PORT: int = 3000
    API_PREFIX: str = "/api"          # 与 NestJS 全局前缀一致(/health 除外)
    API_DOCS_URL: str = "/docs"
    API_REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"
    # ---- 可信代理(SEC-02):默认 False=不信任客户端可控的 X-Forwarded-For,IP 取 TCP 对端;仅当部署在可信反向代理(nginx)后且其正确设置 XFF 时才置 True + 填 TRUSTED_PROXIES ----
    TRUST_PROXY: bool = False
    TRUSTED_PROXIES: List[str] = []

    # ---- CORS ----
    CORS_ORIGINS: List[str] = ["*"]

    # ---- 数据库(与 NestJS data-source 默认一致) ----
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASS: str = "root123"
    DB_NAME: str = "merchant_task"
    DB_ECHO: bool = False

    # ---- JWT(商家 token + 管理后台 token,两个不同 secret) ----
    JWT_SECRET: str = "dev-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_IN: int = 7 * 24 * 3600     # 秒
    ADMIN_JWT_SECRET: str = "admin-secret-key-change-in-production"
    ADMIN_JWT_ALGORITHM: str = "HS256"
    ADMIN_JWT_EXPIRES_IN: int = 7 * 24 * 3600  # 秒
    # ---- 管理端登录失败锁定(进程内内存态,见 app/services/auth.py;多 worker/重启后失效) ----
    ADMIN_LOGIN_MAX_ATTEMPTS: int = 5        # 连续失败达此次数即锁定
    ADMIN_LOGIN_LOCK_MINUTES: int = 30       # 锁定时长(分钟)
    ADMIN_LOGIN_RATE_MAX: int = 10             # 登录请求限流:窗口内允许次数(每 IP、每用户名各一份预算)
    ADMIN_LOGIN_RATE_WINDOW_SECONDS: int = 60  # 登录请求限流窗口(秒)

    # ---- 商家手机号 + 短信验证码登录(#PB-23 / 任务单 #PL-4;频控矩阵 C1~C10 见设计 §五) ----
    # 凭证:RAM 子账号最小权限(仅短信发送 + 验证码校验);生产只写服务器 api-py/.env(600),不入 git
    ALIYUN_SMS_ACCESS_KEY_ID: str = ""
    ALIYUN_SMS_ACCESS_KEY_SECRET: str = ""
    ALIYUN_SMS_SIGN_NAME: str = "恒创联众科技"        # 短信签名(阿里云赠送)
    ALIYUN_SMS_TEMPLATE_CODE: str = "100001"          # 登录/注册模板(含 ${code} 与 ${min})
    # 号码认证服务(PNVS)接入点 —— `SendSmsVerifyCode`/`CheckSmsVerifyCode` 属于 PNVS,
    # **必须**是 dypnsapi;写成 dysmsapi(短信服务产品)会 InvalidAction.NotFound → 统一 502(#PB-23-R4 真机根因)
    ALIYUN_SMS_ENDPOINT: str = "dypnsapi.aliyuncs.com"
    ALIYUN_SMS_REGION_ID: str = "cn-hangzhou"
    ALIYUN_SMS_TIMEOUT_MS: int = 5000                 # 单次短信调用超时(上界,失败即 502)
    # 图形认证(人机校验,#PB-23-R2 官方口径):服务端二次校验走 app/services/captcha.py 单一接缝,未配置即 fail-closed
    CAPTCHA_APP_ID: str = ""                          # 手形认证方案 appId(控制台「图形认证方案管理」生成)
    CAPTCHA_APP_KEY: str = ""                         # appKey(**密钥**:只进 .env(600),禁止日志/接口回显)
    CAPTCHA_API_SERVER: str = "https://captcha.alicaptcha.com"
    CAPTCHA_TIMEOUT_MS: int = 3000                    # 二次校验调用超时(默认 3s,超时一律视为不通过)
    # 验证码本身与频控矩阵(C1~C10)
    LOGIN_CODE_TTL_MINUTES: int = 5                   # C9 有效期;同时作为短信模板 ${min} 的取值(单一真源)
    LOGIN_CODE_LENGTH: int = 6                        # 验证码位数(响应回 code_length)
    LOGIN_CODE_MAX_ATTEMPTS: int = 5                  # C8 单码校验失败上限
    LOGIN_CODE_COOLDOWN_SECONDS: int = 60             # C1 同手机号冷却
    LOGIN_CODE_PHONE_HOURLY_MAX: int = 5              # C2
    LOGIN_CODE_PHONE_DAILY_MAX: int = 10              # C3
    LOGIN_CODE_IP_HOURLY_MAX: int = 20                # C4
    LOGIN_CODE_IP_DAILY_MAX: int = 60                 # C5
    LOGIN_CODE_GLOBAL_DAILY_MAX: int = 1000           # C6(80% 告警)
    LOGIN_CAPTCHA_DAILY_MAX: int = 3000               # C7 人机校验成本闸(captcha_daily_counter 原子自增)
    LOGIN_CODE_VERIFY_WINDOW_MINUTES: int = 15        # C10 校验尝试窗口
    LOGIN_CODE_VERIFY_WINDOW_MAX: int = 10            # C10 窗口内失败尝试上限
    # 内部通知(新商家注册 / 京麦ID重复登记 → 内部 IM 通道;失败绝不阻塞业务)
    INTERNAL_NOTIFY_ENABLED: bool = True
    INTERNAL_NOTIFY_RECEIVE_ID_TYPE: str = "open_id"
    # 接收方 ID(**只由 .env / 环境变量注入**):源码内不得硬编码真实 open_id 等 PII(#PB-37 A)。
    # 留空 = 未配置 → 内部通知**显式跳过** + 记日志(app/services/internal_notify.py::_notify_skip_reason),
    # 既不拒启动、也不影响业务返回(沿用「通知失败不阻塞」旁路纪律);该值**不参与**启动期 fail-fast 校验。
    INTERNAL_NOTIFY_RECEIVE_ID: str = ""
    INTERNAL_NOTIFY_TIMEOUT_MS: int = 5000


    # ---- AI(统一凭证,生产由部署注入) ----
    AI_API_KEY: str = ""
    AI_BASE_URL: str = "https://note3-prev-api.askdiandian.com/v1"
    AI_MODEL: str = "dots3-note-prev"
    # AI 后台配置(ai_entry_config)的加密密钥(AES-256-GCM;64 位 hex)。**刻意不纳入启动期强校验**:
    # 缺失/非法只影响「后台保存密钥」与「已有密文能否解开」,按降级口径回落 env
    # (P7 v1.1 §3.5.4),与「不做启动期 fail-fast / 不做启动期 DB 探测」两条禁令一致。
    AI_CONFIG_ENC_KEY: str = ""
    # 轮换窗口期的旧密钥槽位(可选):解密按 主密钥 -> 前一密钥 顺序尝试
    AI_CONFIG_ENC_KEY_PREVIOUS: str = ""
    AI_TIMEOUT_MS: int = 120000
    AI_DAILY_LIMIT: int = 3
    IMAGE_OPT_MAX_TOKENS: int = 8000
    IMAGE_OPT_TIMEOUT_MS: int = 120000
    AI_IMAGE_OPT_DAILY_LIMIT: int = 5
    IMAGE_OPT_MAX_CONCURRENCY: int = 10
    TITLE_OPT_MAX_TOKENS: int = 4000
    TITLE_OPT_TIMEOUT_MS: int = 120000
    AI_TITLE_OPT_DAILY_LIMIT: int = 5
    TITLE_OPT_MAX_CONCURRENCY: int = 10

    # ---- 飞书 ----
    FEISHU_APP_ID: str = ""
    FEISHU_APP_SECRET: str = ""

    # ---- H5 ----
    H5_BASE_URL: str = "http://127.0.0.1:5173"

    # ---- 静态资源(单文件) ----
    # 商家顾问企微二维码:相对 api-py 根目录的路径;缺失时 GET /api/static/advisor-qr.jpg 返回结构化 404
    ADVISOR_QR_FILE: str = "static/advisor-qr.jpg"

    @field_validator("LOGIN_MODE")
    @classmethod
    def _check_login_mode(cls, v: str) -> str:
        if v not in ("mock", "real"):
            raise ValueError("LOGIN_MODE 只能是 mock 或 real")
        return v

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def database_url(self) -> str:
        """SQLAlchemy MySQL 连接串(utf8mb4,密码做 URL 转义)。"""
        return (
            f"mysql+pymysql://{self.DB_USER}:{quote_plus(self.DB_PASS)}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    """单例取配置,避免 import 时实例化触发 pydantic-settings 弃用告警。"""
    return Settings()


# ---- 启动期配置校验(dev-docs/部署上线前必做清单.md 6b / SEC-06) ----

# 公开发布过的 dev 兜底密钥:非 dev 环境命中即拒绝启动(公开值可用于离线自签任意 token)
DEV_FALLBACK_SECRETS = frozenset({
    "dev-secret-key-change-in-production",
    "admin-secret-key-change-in-production",
})
DEV_FALLBACK_DB_PASS = "root123"
MIN_SECRET_LENGTH = 32
# 与 app/services/feishu.py 的 fail-fast 占位判定保持一致
FEISHU_SECRET_PLACEHOLDERS = frozenset({"", "placeholder", "your_feishu_app_secret"})


class ConfigurationError(RuntimeError):
    """启动期配置校验失败(reasons 为逐条可读原因)。"""

    def __init__(self, reasons: List[str]):
        self.reasons = reasons
        super().__init__("启动期配置校验失败: " + "; ".join(reasons))


def is_dev_environment(s: Settings) -> bool:
    """dev 环境 = LOGIN_MODE=mock 且 DEBUG=True(本地开发/测试);其余一律按生产口径强校验。"""
    return s.LOGIN_MODE == "mock" and s.DEBUG


def validate_startup_settings(s: Settings) -> None:
    """启动期 fail-fast:非 dev 环境下生产密钥必须是显式注入的强值,否则拒绝启动。

    动机(SEC-06/OCR-S1):配置带公开发布的 dev 兜底值且无启动校验时,漏注入 .env 会静默以
    公开密钥启动,任何人可离线自签商家/管理员 token。
    dev/mock 环境不做强校验,保证本地开发与测试照常可跑。
    """
    if is_dev_environment(s):
        return
    reasons: List[str] = []
    for name, secret in (("JWT_SECRET", s.JWT_SECRET), ("ADMIN_JWT_SECRET", s.ADMIN_JWT_SECRET)):
        if secret in DEV_FALLBACK_SECRETS:
            reasons.append(f"{name} 仍为公开 dev 兜底值,必须注入生产密钥")
        elif len(secret) < MIN_SECRET_LENGTH:
            reasons.append(f"{name} 长度不足 {MIN_SECRET_LENGTH}(当前 {len(secret)}),必须注入强随机值")
    if s.JWT_SECRET == s.ADMIN_JWT_SECRET:
        reasons.append("JWT_SECRET 与 ADMIN_JWT_SECRET 不能相同(商家 token 与后台 token 必须隔离)")
    if s.DB_PASS == DEV_FALLBACK_DB_PASS:
        reasons.append(f"DB_PASS 仍为公开 dev 兜底值 {DEV_FALLBACK_DB_PASS},必须注入生产密码")
    if s.LOGIN_MODE == "mock":
        # SEC-01/Q8:mock 登录固定 mock_merchant_001,生产环境等于"未登录即可拿商家 token",非 dev 一律拒绝
        reasons.append("LOGIN_MODE=mock 仅允许本地开发(LOGIN_MODE=mock + DEBUG=True),非 dev 环境必须 LOGIN_MODE=real")
    elif not s.FEISHU_APP_ID or s.FEISHU_APP_SECRET.strip() in FEISHU_SECRET_PLACEHOLDERS:
        reasons.append("FEISHU_APP_ID/FEISHU_APP_SECRET 缺失或为占位值,LOGIN_MODE=real 无法完成登录")
    if reasons:
        raise ConfigurationError(reasons)
