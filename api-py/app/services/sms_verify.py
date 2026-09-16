"""阿里云号码认证服务(PNVS)短信认证适配层(**唯一出口**,#PB-23 / #PL-4 §3.1)。

口径(总控 2026-09-16 steer ②,字段级证据来自官方 SDK `alibabacloud_dypnsapi20170525` 2.0.0):
  · 发短信 = `SendSmsVerifyCode`(**验证码由阿里云生成与下发**,我们**不接收、不落库、不打印**明文码:
    `ReturnVerifyCode=false` 为硬性);响应取 `Model.BizId`;判据 `Code == "OK" and Success is True`。
  · 校验 = `CheckSmsVerifyCode`;判据 `Model.VerifyResult == "PASS"`(**只有 PASS 算通过**),`OutId` 透传。
  · 参数来源单一:有效期 `ValidTime = LOGIN_CODE_TTL_MINUTES * 60`(与模板 `${min}` 同源)、
    同号间隔 `Interval = LOGIN_CODE_COOLDOWN_SECONDS`(阿里云侧兜底)、长度/纯数字取 `LOGIN_CODE_LENGTH`/1。

失败一律抛 `ApiException(502, SMS_UNAVAILABLE_MESSAGE)`(文案禁含供应商名/错误码/环境变量名);
供应商的 code/message/request_id 与脱敏手机号只进日志;**绝不记录验证码、密钥、完整手机号**。
"""
import json
import logging

from alibabacloud_dypnsapi20170525 import models as pnvs_models
from alibabacloud_dypnsapi20170525.client import Client as SmsVerifyClient
from alibabacloud_tea_openapi import models as open_api_models

from app.core.config import get_settings
from app.core.exceptions import ApiException
from app.core.utils import mask_phone

logger = logging.getLogger("api")

SMS_UNAVAILABLE_MESSAGE = "短信服务暂不可用，请稍后重试"
# 系统「登录/注册」模板的验证码占位符(SDK 注释口径;最终以阿里云控制台「模板配置」页示例为准)
TEMPLATE_CODE_PLACEHOLDER = "##code##"
CODE_TYPE_NUMERIC = 1
COUNTRY_CODE_CHINA = "86"
DEFAULT_OUT_ID_PREFIX = "login"
VERIFY_RESULT_PASS = "PASS"
# PNVS 的「业务级校验未通过」错误码(实测 code=isv.ValidateFail,message="code: 400, 验证失败"):
# 属**用户输错/码过期**,必须映射为「未通过」而非 502(否则误导用户 + C8/C10 错次上限失效)
VERIFY_NOT_PASSED_CODES = frozenset({"isv.ValidateFail"})


def _build_client() -> SmsVerifyClient:
    """构造 PNVS 客户端;凭证缺失视为服务不可用(502),日志只记「缺失」不记值。"""
    settings = get_settings()
    if not settings.ALIYUN_SMS_ACCESS_KEY_ID or not settings.ALIYUN_SMS_ACCESS_KEY_SECRET:
        logger.error("短信认证凭证未配置(ALIYUN_SMS_ACCESS_KEY_ID/SECRET 缺失): 拒绝调用")
        raise ApiException(SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502)
    config = open_api_models.Config(
        access_key_id=settings.ALIYUN_SMS_ACCESS_KEY_ID,
        access_key_secret=settings.ALIYUN_SMS_ACCESS_KEY_SECRET,
        endpoint=settings.ALIYUN_SMS_ENDPOINT,
        region_id=settings.ALIYUN_SMS_REGION_ID,
        read_timeout=settings.ALIYUN_SMS_TIMEOUT_MS,
        connect_timeout=settings.ALIYUN_SMS_TIMEOUT_MS,
    )
    return SmsVerifyClient(config)


def send_verify_code(phone: str, out_id: str) -> str:
    """调用 `SendSmsVerifyCode` 下发验证码,返回阿里云 `BizId`(用于落库可观测;不含验证码本身)。

    `ReturnVerifyCode=false` 是**硬性口径**:响应里的 `Model.VerifyCode` 我们一律不读、不落库、不打印。
    """
    settings = get_settings()
    client = _build_client()
    request = pnvs_models.SendSmsVerifyCodeRequest(
        phone_number=phone,
        sign_name=settings.ALIYUN_SMS_SIGN_NAME,
        template_code=settings.ALIYUN_SMS_TEMPLATE_CODE,
        template_param=json.dumps({"code": TEMPLATE_CODE_PLACEHOLDER, "min": settings.LOGIN_CODE_TTL_MINUTES},
                                  ensure_ascii=False),
        code_length=settings.LOGIN_CODE_LENGTH,
        code_type=CODE_TYPE_NUMERIC,
        country_code=COUNTRY_CODE_CHINA,
        valid_time=settings.LOGIN_CODE_TTL_MINUTES * 60,
        interval=settings.LOGIN_CODE_COOLDOWN_SECONDS,
        return_verify_code=False,
        duplicate_policy=1,          # 最新覆盖:同号新码生效,旧码由阿里云侧失效
        out_id=out_id,
    )
    try:
        resp = client.send_sms_verify_code(request)
    except Exception as e:  # noqa: BLE001 - 供应商异常统一按「服务不可用」映射
        # #PB-23-R4:SDK 异常自带诊断信息(如 ClientException.code=404「Specified api is not found」),
        # 必须落日志 —— 之前只记类名,导致「endpoint 配错」的真机排查多花时间。
        # 只记 code/message/request_id,**不**记 exc_info(SDK 异常里可能带请求体)、不记密钥/完整手机号/验证码。
        logger.error(
            f"短信认证下发异常: phone={mask_phone(phone)} error={type(e).__name__} "
            f"code={getattr(e, 'code', None)} message={getattr(e, 'message', None)!r} "
            f"request_id={getattr(e, 'request_id', None)}")
        raise ApiException(SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502) from e
    body = getattr(resp, "body", None)
    ok = getattr(body, "success", None) is True and getattr(body, "code", None) == "OK"
    if not ok:
        logger.error(
            "短信认证下发失败: "
            f"phone={mask_phone(phone)} code={getattr(body, 'code', None)} "
            f"message={getattr(body, 'message', None)!r} request_id={getattr(body, 'request_id', None)}")
        raise ApiException(SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502)
    model = getattr(body, "model", None)
    biz_id = getattr(model, "biz_id", None) or ""
    logger.info(f"短信认证已下发: phone={mask_phone(phone)} biz_id={biz_id} out_id={out_id}")
    return biz_id


def check_verify_code(phone: str, code: str, out_id: str) -> bool:
    """调用 `CheckSmsVerifyCode` 校验;返回是否 **PASS**(`UNKNOWN`/其它一律 False)。

    供应商不可用 / 凭证缺失 → 抛 502(fail-closed:绝不放行登录)。

    **「校验未通过」是业务级结果,不是服务故障**(#PB-23-R4 真机探针实测):输错码时 SDK 以
    `ClientException(code='isv.ValidateFail', message='code: 400, 验证失败')` **抛出**,而非返回
    `model.verify_result='UNKNOWN'`。若把它当成 502,用户会看到「短信服务暂不可用」(误导),
    且上层 C8(单码错次)/C10(窗口错次)永远不会计数 ⇒ 防爆破失效。故在此映射为「未通过」(return False)。
    """
    client = _build_client()
    request = pnvs_models.CheckSmsVerifyCodeRequest(
        phone_number=phone,
        verify_code=(code or "").strip(),
        country_code=COUNTRY_CODE_CHINA,
        out_id=out_id,
    )
    try:
        resp = client.check_sms_verify_code(request)
    except Exception as e:  # noqa: BLE001 - 先判业务级「未通过」,其余按「服务不可用」映射(不放行)
        error_code = getattr(e, "code", None)
        if error_code in VERIFY_NOT_PASSED_CODES:
            logger.info(
                f"短信认证校验未通过(业务级): phone={mask_phone(phone)} code={error_code} "
                f"request_id={getattr(e, 'request_id', None)}")
            return False
        # 同下发分支(#PB-23-R4):可诊断信息必须落日志,但不记 exc_info/密钥/完整手机号/验证码
        logger.error(
            f"短信认证校验异常: phone={mask_phone(phone)} error={type(e).__name__} "
            f"code={getattr(e, 'code', None)} message={getattr(e, 'message', None)!r} "
            f"request_id={getattr(e, 'request_id', None)}")
        raise ApiException(SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502) from e
    body = getattr(resp, "body", None)
    model = getattr(body, "model", None)
    result = getattr(model, "verify_result", None)
    passed = result == VERIFY_RESULT_PASS
    logger.info(
        f"短信认证校验结果: phone={mask_phone(phone)} verify_result={result} "
        f"code={getattr(body, 'code', None)} message={getattr(body, 'message', None)!r}")
    if not passed and getattr(body, "success", None) is not True:
        logger.error(f"短信认证校验调用失败(非业务失败): phone={mask_phone(phone)} code={getattr(body, 'code', None)}")
        raise ApiException(SMS_UNAVAILABLE_MESSAGE, code=502, status_code=502)
    return passed
