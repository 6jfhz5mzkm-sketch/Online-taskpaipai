
// 抓取内容校验 + 与上次基线差异熔断
// 目的：抓不到 / 解析异常 / 与历史差异过大时，中止更新并通知，避免把错误数据写库。

const num = (v) => { const n = Number(v); return Number.isFinite(n) ? n : null; };

// 过滤出真正的“数据行”（含费率或保证金的），去掉表头/空行
export function cleanRows(ruleRows) {
  if (!Array.isArray(ruleRows)) return [];
  return ruleRows.filter(r => num(r.opRate) != null || num(r.depLt5w) != null || num(r.depGte30w) != null);
}

// 费率/保证金指纹：用于比较两行是否一致
function feeSig(r) {
  return [r.opRate, r.txRate, r.depLt5w, r.dep5w10w, r.dep10w30w, r.depGte30w].map(v => v == null ? '' : String(v)).join('|');
}
// 行身份：一级|二级|三级|四级 作为类目作用域
function rowKey(r) { return [r.lv1, r.lv2, r.lv3, r.lv4].map(v => (v || '').trim()).join('|'); }

const THRESHOLDS = {
  minRows: Number(process.env.FEE_SYNC_MIN_ROWS || 20),           // 有效数据行下限，低于此视为抓取失败
  rowChangePct: Number(process.env.FEE_SYNC_ROW_CHANGE_LIMIT || 0.3), // 行数变化比例上限
  feeChangePct: Number(process.env.FEE_SYNC_FEE_CHANGE_LIMIT || 0.3), // 费率变更比例上限
  maxRate: Number(process.env.FEE_SYNC_MAX_RATE || 30),           // 运营费率合理上限(%)
  maxTxRate: Number(process.env.FEE_SYNC_MAX_TX_RATE || 10),      // 交易费率合理上限(%)
};

// 1) 抓取结果结构校验
export function validateScrape(ruleRows, brandRows) {
  const rows = cleanRows(ruleRows);
  if (rows.length < THRESHOLDS.minRows) {
    return { ok: false, reason: '抓取结果有效规则行过少：' + rows.length + ' 条（阈值 ' + THRESHOLDS.minRows + '）' };
  }
  for (const r of rows) {
    const op = num(r.opRate);
    const tx = num(r.txRate);
    if (op == null || op < 0 || op > THRESHOLDS.maxRate) return { ok: false, reason: '异常运营费率 ' + r.opRate + '（类目 ' + (r.lv3 || r.lv2) + '）' };
    if (tx == null || tx < 0 || tx > THRESHOLDS.maxTxRate) return { ok: false, reason: '异常交易费率 ' + r.txRate + '（类目 ' + (r.lv3 || r.lv2) + '）' };
    if (num(r.depLt5w) == null && num(r.depGte30w) == null) return { ok: false, reason: '缺少保证金档位（类目 ' + (r.lv3 || r.lv2) + '）' };
    if (!(r.lv2 || '').includes('类目') && !r.lv2 && !r.lv3) return { ok: false, reason: '类目名称缺失（疑似解析错位）' };
  }
  return { ok: true, rows };
}

// 2) 与上次基线差异熔断：按 作用域 对齐比较
// prev/new: 均为 cleanRows 后的数据行数组
export function compareSnapshots(prev, next) {
  if (!prev || !prev.length) return { ok: true, reason: '无基线，跳过差异校验', changed: 0, total: next.length, ratio: 0 };
  const pMap = new Map(prev.map(r => [rowKey(r), feeSig(r)]));
  const nMap = new Map(next.map(r => [rowKey(r), feeSig(r)]));
  let unchanged = 0, changed = 0;
  const total = new Set([...pMap.keys(), ...nMap.keys()]).size || 1;
  for (const [k, sig] of pMap) {
    if (nMap.has(k) && nMap.get(k) === sig) unchanged++; else changed++;
  }
  let newRows = 0;
  for (const [k] of nMap) if (!pMap.has(k)) newRows++;
  const changed2 = changed + newRows;
  const rowChange = Math.abs(next.length - prev.length) / Math.max(1, prev.length);
  const feeRatio = changed2 / total;
  const ok = rowChange <= THRESHOLDS.rowChangePct && feeRatio <= THRESHOLDS.feeChangePct;
  return {
    ok,
    changed: changed2,
    total,
    ratio: feeRatio,
    rowChangePct: rowChange,
    reason: ok ? '' :
      '与上次基线差异过大：类目费变更 ' + changed2 + '/' + total + '（' + (feeRatio * 100).toFixed(1) + '%），行数 ' + prev.length + '→' + next.length + '（' + (rowChange * 100).toFixed(1) + '%）' +
      '，超过阈值(费率 ' + (THRESHOLDS.feeChangePct * 100).toFixed(0) + '%，行数 ' + (THRESHOLDS.rowChangePct * 100).toFixed(0) + '%)。请人工核对规则页。',
  };
}

export { THRESHOLDS };
