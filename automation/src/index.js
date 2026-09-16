
// 入口：月度资费同步 —— 抓取 -> 校验/熔断 -> 映射 -> 比对 -> 备份 -> (可选)更新 -> 报告 -> 通知
// 用法：
//   node src/index.js              # dry-run：只比对+通知，不写库
//   node src/index.js --apply      # 有调整时先备份，再写库（备份失败/校验失败/差异过大则中止）
//   node src/index.js --fixture x  # 用本地 ruleRows JSON 做离线比对（调试/验证）
//   node src/index.js --backup-only# 只做一次数据库备份
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import path from 'path';
import { config } from './config.js';
import { q } from './db.js';
import { scrapePage } from './scrape.js';
import { cleanRows, validateScrape, compareSnapshots } from './validation.js';
import { buildDesired } from './mapping.js';
import { compareFeeConfigs } from './compare.js';
import { buildReport, buildNotifyText } from './report.js';
import { applyChanges } from './update.js';
import { backupDatabase, BACKUP_DIR } from './backup.js';
import { notifyAdmin } from './notify.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const BASE_PATH = path.join(ROOT, 'reports', 'fee-snapshot-baseline.json');

async function main() {
  const argv = process.argv.slice(2);
  const apply = argv.includes('--apply');
  const backupOnly = argv.includes('--backup-only');
  const fixtureIdx = argv.indexOf('--fixture');
  const fixture = fixtureIdx >= 0 ? argv[fixtureIdx + 1] : null;
  config.run.apply = apply;

  if (backupOnly) {
    const bkp = await backupDatabase();
    console.log('[fee-sync] 数据库备份完成:', bkp.file);
    return { backup: bkp.file };
  }

  console.log('[fee-sync] 开始，模式:', apply ? 'apply(更新前会先备份并校验)' : 'dry-run');

  // 1) 取规则数据
  let ruleRows = [];
  let brandRows = [];
  let effectiveAt = '';
  let title = '';
  if (fixture) {
    const data = JSON.parse(readFileSync(fixture, 'utf8'));
    ruleRows = data.ruleRows || data;
    brandRows = data.brandRows || [];
    effectiveAt = data.effectiveAt || '';
    title = data.title || 'fixture';
    console.log('[fee-sync] 使用本地 fixture, ruleRows:', ruleRows.length);
  } else {
    const s = await scrapePage();
    ruleRows = s.ruleRows; brandRows = s.brandRows; effectiveAt = s.effectiveAt; title = s.title;
    console.log('[fee-sync] 已抓取: ruleRows=', ruleRows.length, 'brandRows=', brandRows.length, '生效=', effectiveAt);
    mkdirSync(path.join(ROOT, 'reports'), { recursive: true });
    writeFileSync(path.join(ROOT, 'reports', 'fee-rule-raw-' + stamp() + '.json'),
      JSON.stringify({ effectiveAt, title, ruleRows, brandRows }, null, 2), 'utf8');
  }

  // 2) 清洗 + 抓取内容校验（结构/费率/档位/类目名）
  const cleanRuleRows = cleanRows(ruleRows);
  const v = validateScrape(cleanRuleRows, brandRows);
  if (!v.ok) throw new Error('抓取内容校验失败：' + v.reason);
  console.log('[fee-sync] 抓取校验通过：有效规则行', cleanRuleRows.length);

  // 3) 与上次成功基线差异熔断（防止错误/异常快照触发大量更新）
  let baseline = null;
  try { baseline = JSON.parse(readFileSync(BASE_PATH, 'utf8')); } catch {}
  const diff = compareSnapshots(baseline?.ruleRows, cleanRuleRows);
  if (!diff.ok) throw new Error('差异熔断：' + diff.reason);
  if (baseline?.ruleRows) console.log('[fee-sync] 基线差异：变更', diff.changed, '/' + diff.total, '(' + (diff.ratio * 100).toFixed(1) + '%)');

  // 4) 取类目与当前库资费
  const categories = await q(`
    SELECT c.id AS catId, c.name AS name, p.name AS parentName
    FROM category c LEFT JOIN category p ON p.id = c.parent_id
    WHERE c.parent_id <> 0 AND c.is_active = 1 ORDER BY c.id`);
  const feeRows = await q(`SELECT category_id, operation_rate, transaction_rate,
      deposit_gmv_lt_5w, deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w, is_active
    FROM fee_config`);

  // 5) 映射 + 比对
  const desired = buildDesired(categories, cleanRuleRows);
  const result = compareFeeConfigs(categories, feeRows, desired);
  console.log('[fee-sync] 比对: 共', result.total, '| 无变更', result.unchangedCount,
    '| 需更新', result.changedCount, '| 新增', result.addedCount, '| 未匹配', result.unmatchedCount);

  // 6) 写库（apply：先备份，失败则中止；成功后再更新基线）
  let applied = { updated: 0, added: 0 };
  let backup = null;
  if (apply) {
    backup = await backupDatabase();
    console.log('[fee-sync] 已备份:', backup.file);
    applied = await applyChanges(result);
    console.log('[fee-sync] 已写入: update', applied.updated, '新增', applied.added);
    writeFileSync(BASE_PATH, JSON.stringify({ ruleRows: cleanRuleRows, effectiveAt, title, savedAt: new Date().toISOString() }, null, 2), 'utf8');
  }

  // 7) 生成报告并落盘
  const ctx = { result, title, effectiveAt, backup, applied, mode: apply ? 'apply' : 'dry-run', backupDir: BACKUP_DIR };
  const report = buildReport(ctx);
  mkdirSync(path.join(ROOT, 'reports'), { recursive: true });
  const repPath = path.join(ROOT, 'reports', 'fee-sync-report-' + stamp() + '.md');
  writeFileSync(repPath, report, 'utf8');
  console.log('[fee-sync] 报告已写入:', repPath);

  // 8) 通知（无论有无调整都发）
  const text = buildNotifyText(ctx) + '\n\n完整报告：' + repPath;
  const note = await notifyAdmin(text, { template: 'fee_sync', title: '拍拍资费月度同步' + (result.changedCount>0?'⚠️':'✅') });
  console.log('[fee-sync] 通知结果:', JSON.stringify(note));

  return { changedCount: result.changedCount, addedCount: result.addedCount, unmatchedCount: result.unmatchedCount, applied, backup, repPath };
}

function stamp() { return new Date().toISOString().replace(/[-:T]/g, '').slice(0, 14); }

main().then(out => {
  process.exit(0);
}).catch(err => {
  console.error('[fee-sync] 失败:', err);
  try { notifyAdmin('❌ 拍拍资费月度同步中止：' + err.message, { template: 'fee_sync_failed', title: '拍拍资费同步中止' }); } catch {}
  process.exitCode = 1;
});
