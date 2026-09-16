
// 生成更新报告（markdown 文本），会随飞书消息一并送达/落盘
import { config } from './config.js';

export function buildReport(ctx) {
  const now = new Date();
  const ts = now.toISOString().replace('T', ' ').slice(0, 19);
  const lines = [];
  lines.push('# 拍拍二手资费标准月度同步报告');
  lines.push('');
  lines.push('- 生成时间：' + ts);
  lines.push('- 规则来源：' + config.rule.url);
  lines.push('- 页面标题：' + (ctx.title || '未知'));
  lines.push('- 生效时间：' + (ctx.effectiveAt || '未知'));
  lines.push('- 运行模式：' + (config.run.apply ? '写入(apply，更新前已备份)' : '仅比对(dry-run)'));
  lines.push('- 类目总数：' + ctx.result.total);
  lines.push('- 已同步(无变更)：' + ctx.result.unchangedCount);
  lines.push('- 需要更新：' + ctx.result.changedCount);
  lines.push('- 新增：' + ctx.result.addedCount + '，未匹配：' + ctx.result.unmatchedCount);
  if (ctx.backup) lines.push('- 备份文件：' + ctx.backup.file);
  if (ctx.mode === 'apply' && ctx.applied) lines.push('- 本次写入：更新 ' + ctx.applied.updated + '，新增 ' + ctx.applied.added);
  lines.push('');
  if (ctx.result.changedCount > 0) {
    lines.push('## 需更新类目');
    for (const d of ctx.result.diffs) {
      lines.push('');
      lines.push('### ' + d.name + '（' + d.parent + '，category_id=' + d.catId + '）');
      for (const ch of d.changes) {
        lines.push('- ' + ch.field + '：' + ch.from + ' → ' + ch.to);
      }
    }
  } else {
    lines.push('## 比对结果');
    lines.push('未发现资费调整。');
  }
  if (ctx.result.addedCount > 0) {
    lines.push('');
    lines.push('## 新增类目（库中缺失）');
    for (const a of ctx.result.added) {
      lines.push('- ' + a.name + '(' + a.parent + ') => ' + a.opRate + '% / ' + a.txRate + '%');
    }
  }
  if (ctx.result.unmatchedCount > 0) {
    lines.push('');
    lines.push('## ⚠️ 未匹配到规则（需人工确认映射）');
    for (const u of ctx.result.unmatched) {
      lines.push('- ' + u.name + '(' + u.parent + ') #' + u.catId);
    }
  }
  return lines.join('\n');
}

export function buildNotifyText(ctx) {
  const mode = config.run.apply ? '已自动更新' : 'dry-run（未写库）';
  const head = '📊 拍拍资费月度同步 ' + (ctx.result.changedCount > 0 ? '⚠️ 有调整' : '✅ 无调整');
  const body = [
    head,
    '生效时间：' + (ctx.effectiveAt || '未知'),
    '需要更新类目：' + ctx.result.changedCount + ' 个',
    '新增：' + ctx.result.addedCount + ' 个，未匹配：' + ctx.result.unmatchedCount + ' 个',
    '运行模式：' + mode,
  ];
  if (ctx.backup) body.push('备份文件：' + ctx.backup.file);
  if (ctx.mode === 'apply' && ctx.applied) body.push('本次写入：更新 ' + ctx.applied.updated + '，新增 ' + ctx.applied.added);
  if (ctx.result.changedCount > 0) {
    // 只列前 20 条
    const top = ctx.result.diffs.slice(0, 20).map(d => d.name + '(' + d.parent + ')：' + d.changes.map(c => c.field + ' ' + c.from + '→' + c.to).join('，')).join('\n');
    body.push('\n明细：\n' + top);
  } else {
    body.push('\n各二级类目资费与库内一致，无需更新。');
  }
  return body.join('\n');
}
