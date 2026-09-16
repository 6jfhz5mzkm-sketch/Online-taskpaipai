/**
 * 商家登记信息（京麦商家ID / 店铺名称）用户可见文案（唯一真源）
 *
 * @description 这两个字段同时被「经营类目弹窗」（顶部输入区）与「商家信息登记弹窗」使用，
 *              故单点定义在此（开发规则 §8.1 第 1 条：同一句文案 ≥2 处必须抽常量）。
 *              数据真源：merchant.jd_merchant_id / merchant.shop_name
 *              （project/scripts/schema.sql:40-41）；接口真源：PUT/GET /api/merchant/registration
 *              （api-py/app/api/v1/merchant.py:41 / :75）。
 *              登记：project/docs/开发规则.md §8.2（新增或修改文案必须同步该表）。
 */

/** 字段标签：京麦商家ID */
export const JD_MERCHANT_ID_LABEL = '京麦商家ID';

/** 字段标签：店铺名称 */
export const SHOP_NAME_LABEL = '店铺名称';

/** 输入占位：京麦商家ID（提示只允许数字） */
export const JD_MERCHANT_ID_PLACEHOLDER = '请输入京麦商家ID（仅数字）';

/** 输入占位：店铺名称（提示只允许汉字） */
export const SHOP_NAME_PLACEHOLDER = '请输入店铺名称（仅汉字）';

/** 格式错误提示：京麦商家ID 含非数字字符 */
export const JD_MERCHANT_ID_INVALID_TEXT = '京麦商家ID仅支持数字';

/** 格式错误提示：店铺名称含非汉字字符 */
export const SHOP_NAME_INVALID_TEXT = '店铺名称仅支持汉字';

/** 京麦商家ID 长度上界（与 merchant.jd_merchant_id VARCHAR(64) 及接口 max_length 一致） */
export const JD_MERCHANT_ID_MAX_LENGTH = 64;

/** 店铺名称长度上界（与 merchant.shop_name VARCHAR(128) 及接口 max_length 一致） */
export const SHOP_NAME_MAX_LENGTH = 128;
