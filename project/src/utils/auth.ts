/**
 * 登录态与登出（商家端唯一入口）
 *
 * @description 登录态 storage 键的唯一声明处，以及「清登录态 + 回登录页」的唯一实现。
 *              两条使用路径共用本模块，禁止任何页面各写一套清理逻辑：
 *                ① 用户主动退出：pages/index/index.vue 的「退出登录」确认后调用 logout()；
 *                ② 会话过期：api/request.ts 收到 401 时调用 clearAuthStorage() + redirectToLogin()。
 *              登录态写入方仍为 pages/login/index.vue（token / merchant 两个键）。
 *
 * @ownership 用户可见文案（退出登录相关）归 #F-19 的 project/src/constants/auth.ts，本模块只被其导入方使用；
 *            清理函数当前仅本模块一份（#F-19 交付的 constants/auth.ts 只含文案常量）。
 *            **待总控收口**：若 #F-19 后续在 constants/auth.ts 内补登出清理函数，须二选一保留单份
 *            （把本模块函数迁入 constants/auth.ts，或 constants/auth.ts 改为导入本模块），不得并存两套。
 */

/** 登录态 storage 键（写入方：pages/login/index.vue；读取方：utils/merchant.ts、api/request.ts 请求头） */
export const AUTH_STORAGE_KEYS = ['token', 'merchant'];

/** 清空本地登录态（只清存储，不跳转；调用方决定后续动作） */
export const clearAuthStorage = (): void => {
  AUTH_STORAGE_KEYS.forEach((key) => uni.removeStorageSync(key));
};

/** 回到登录页（已在登录页时不重复跳转，避免自跳循环） */
export const redirectToLogin = (): void => {
  const pages = getCurrentPages();
  const currentRoute = pages[pages.length - 1]?.route || '';
  if (currentRoute === 'pages/login/index') return;
  uni.reLaunch({ url: '/pages/login/index' });
};

/** 退出登录：清登录态并回登录页（用户主动退出与会话过期共用同一套清理） */
export const logout = (): void => {
  clearAuthStorage();
  redirectToLogin();
};
