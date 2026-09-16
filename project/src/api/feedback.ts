/**
 * 商家反馈接口（商家端任务中心页「意见反馈」浮窗）
 * @description POST /api/feedback 提交反馈（商家 JWT；content 必填非空，category 可选；不采集联系方式）
 */
import request from './request';

export interface FeedbackPayload {
  /** 反馈内容（必填，非空） */
  content: string;
  /** 反馈分类（可选：功能建议/问题反馈/其他） */
  category?: string;
}

/** 提交商家反馈 */
export const submitFeedback = (payload: FeedbackPayload) =>
  request.post<{ ok?: boolean }>('/api/feedback', payload).then((res) => res.data);
