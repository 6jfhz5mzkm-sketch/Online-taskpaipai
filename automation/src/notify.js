
// 飞书通知：应用消息发给指定 open_id（与 FeishuService 同款 API 流程）
// 步骤：1) 取 tenant_access_token  2) 发送文本消息
import { config } from './config.js';
import { q } from './db.js';

export async function getTenantAccessToken() {
  const { appId, appSecret, apiBase } = config.feishu;
  if (!appId || !appSecret) throw new Error('缺少 FEISHU_APP_ID / FEISHU_APP_SECRET');
  const resp = await fetch(apiBase + '/open-apis/auth/v3/tenant_access_token/internal', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
    body: JSON.stringify({ app_id: appId, app_secret: appSecret }),
  });
  const data = await resp.json();
  if (data.code !== 0) throw new Error('获取飞书 token 失败: ' + JSON.stringify(data));
  return data.tenant_access_token;
}

export async function sendTextMessage(openId, text) {
  const { appId, apiBase } = config.feishu;
  const token = await getTenantAccessToken();
  const resp = await fetch(apiBase + '/open-apis/im/v1/messages?receive_id_type=open_id', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      Authorization: 'Bearer ' + token,
    },
    body: JSON.stringify({
      receive_id: openId,
      msg_type: 'text',
      content: JSON.stringify({ text }),
    }),
  });
  const data = await resp.json();
  return data;
}

// 记录到 feishu_notification（可审计），失败不阻断
export async function logNotification({ merchantId = 'system', templateType, title, content, status = 'sent', errorMsg = null }) {
  try {
    await q(
      `INSERT INTO feishu_notification
         (merchant_id, template_type, title, content, status, sent_at, error_msg)
       VALUES (?, ?, ?, ?, ?, NOW(), ?)`,
      [merchantId, templateType, title, content, status, errorMsg]
    );
  } catch (e) {
    console.error('[notify] 记录通知失败:', e.message);
  }
}

// 统一入口：发送文本并落库
export async function notifyAdmin(text, meta) {
  const openId = config.feishu.adminOpenId;
  if (!openId) {
    console.warn('[notify] 未配置 FEISHU_ADMIN_OPEN_ID，跳过推送');
    await logNotification({ templateType: meta?.template || 'fee_sync', title: meta?.title || '资费同步', content: text, status: 'failed', errorMsg: '未配置 FEISHU_ADMIN_OPEN_ID' });
    return { sent: false, reason: 'no open_id' };
  }
  try {
    const data = await sendTextMessage(openId, text);
    const ok = data.code === 0;
    await logNotification({ templateType: meta?.template || 'fee_sync', title: meta?.title || '资费同步', content: text, status: ok ? 'sent' : 'failed', errorMsg: ok ? null : JSON.stringify(data) });
    return { sent: ok, detail: data };
  } catch (e) {
    await logNotification({ templateType: meta?.template || 'fee_sync', title: meta?.title || '资费同步', content: text, status: 'failed', errorMsg: e.message });
    return { sent: false, error: e.message };
  }
}
