/**
 * 账号级新手引导标记接口（阶段一/二/数据专区共用）
 * @description GET /api/tour/seen 查询是否已看（data.seen）；POST /api/tour/seen 标记已看；
 *              POST /api/tour/seen/reset 重置（重新观看引导用）。
 */
import request from './request';

/** 查询引导是否已看（seen: true 已看 / false 未看） */
export const fetchTourSeen = () =>
  request.get<{ seen: boolean }>('/api/tour/seen').then((res) => res.data);

/** 标记引导已看（完成/跳过时调用） */
export const markTourSeen = () =>
  request.post<{ ok?: boolean }>('/api/tour/seen', {}).then((res) => res.data);

/** 重置引导已看（重新观看引导入口调用） */
export const resetTourSeen = () =>
  request.post<{ ok?: boolean }>('/api/tour/seen/reset', {}).then((res) => res.data);
