/**
 * 退出登录 · 管理后台文案入口（唯一真源）
 *
 * @description 文案常量单点定义（开发规则 §8.1 第 1 条：同一句文案 ≥2 处出现必须抽常量）；
 *              登出动作由 store 的 logout 统一实现（清 admin_token / admin_info 并跳 /login），
 *              页面不得各写一套清理逻辑。
 *              管理后台 token 与商家端互相独立（不同 secret、不同 localStorage 键），此处只清 admin 自己的。
 *              登记：project/docs/任务管理后台开发标准.md §十一（管理后台文案唯一登记处；新增或修改文案必须同步该节）。
 */

/** 退出登录入口文案（用户区下拉菜单项） */
export const LOGOUT_ENTRY_TEXT = '退出登录';

/** 退出登录二次确认弹窗标题 */
export const LOGOUT_CONFIRM_TITLE = '退出登录';

/** 退出登录二次确认弹窗说明（不回显技术细节，只给可执行动作） */
export const LOGOUT_CONFIRM_MESSAGE = '退出后需重新登录才能继续管理后台，确认退出吗？';

/** 退出登录二次确认弹窗 · 取消按钮（不退出） */
export const LOGOUT_CONFIRM_CANCEL_TEXT = '取消';

/** 退出登录二次确认弹窗 · 确认按钮 */
export const LOGOUT_CONFIRM_OK_TEXT = '确认退出';
