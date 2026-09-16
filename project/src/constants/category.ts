/**
 * 经营类目（阶段二入口）用户可见文案（唯一真源）
 *
 * @description 弹窗标题/说明/按钮等文案单点定义（开发规则 §8.1 第 1 条：同一句文案 ≥2 处必须抽常量）。
 *              登记：project/docs/开发规则.md §8.2（新增或修改文案必须同步该表）。
 *              注：保存成功提示与数量越界错误文案的真源是后端接口契约
 *              （project/docs/后端技术方案.md §5.2 API-07「成功文案」/「异常情况」行），
 *              本文件不重复定义，由组件按真源引用。
 */

/** 弹窗标题 = 侧栏常驻入口文案（同一句文案，单点定义） */
export const CATEGORY_PICKER_TITLE = '选择经营类目';

/** 弹窗说明（首次进入引导的用途与规则） */
export const CATEGORY_DIALOG_INTRO = '首次进入需要先选择经营类目：最多 3 个，并指定 1 个主类目；保存后可在左侧入口随时修改。';

/** 弹窗提示（跳过语义：仅本次跳过，不写库） */
export const CATEGORY_DIALOG_HINT = '本次可先跳过；跳过不会保存，下次进入会再次提示。';

/** 弹窗次要按钮：跳过（仅关闭弹窗，不写库、不报错、不写永久标记） */
export const CATEGORY_SKIP_TEXT = '跳过';

/** 弹窗主按钮：保存经营类目 */
export const CATEGORY_SAVE_TEXT = '保存经营类目';

/** 弹窗主按钮保存中态 */
export const CATEGORY_SAVING_TEXT = '保存中…';

/** 一级类目（parent_id=0）选择器占位：未选择时展示 */
export const CATEGORY_TOP_PLACEHOLDER = '请选择一级类目';

/** 二级类目（parent_id<>0）选择器占位：未选择时展示（#F-25-R1 改为 dropdown 多选） */
export const CATEGORY_SUB_PLACEHOLDER = '请选择二级类目';

/**
 * 类目数量越界提示（真源：project/docs/后端技术方案.md §5.2 API-07 异常情况行「请选择1-3个类目」）
 * @description 多选勾第 4 个时前端前置拦截提示；措辞与后端 400 文案保持一致，不另造。
 */
export const CATEGORY_COUNT_ERROR_TEXT = '请选择1-3个类目';
