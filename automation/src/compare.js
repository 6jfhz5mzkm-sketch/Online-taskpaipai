
// 比对：desired(规则抓取) vs current(数据库 fee_config)
// 返回结构化差异，供报告/更新/通知使用
const eps = 1e-6;
function num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }
function rateEq(a, b) {
  const x = num(a), y = num(b);
  if (x == null || y == null) return a === b;
  return Math.abs(x - y) < eps;
}
function intEq(a, b) { return num(a) === num(b); }

export function compareFeeConfigs(categories, currentRows, desired) {
  // currentRows: fee_config 行 (含 category_id, rate 等)
  // desired: Map<catId, {...}>
  const currentById = new Map();
  for (const row of currentRows) {
    if (Number(row.is_active ?? 1) === 1) currentById.set(Number(row.category_id), row);
  }
  const diffs = [];       // 需要更新的类目
  const unchanged = [];   // 与库一致的类目
  const unmatched = [];   // 规则无对应行的类目（库里有但规则没匹配到）
  const added = [];       // 规则有但库里没有的类目

  for (const c of categories) {
    const catId = Num(c.catId ?? c.category_id);
    const d = desired.get(catId);
    const cur = currentById.get(catId);
    if (!d) {
      // 规则没匹配到该二级类目 -> 需要人工确认映射
      if (cur) unmatched.push({ catId, name: c.name, parent: c.parentName, reason: 'no_rule_match' });
      continue;
    }
    if (!cur) {
      added.push({ catId, name: c.name, parent: c.parentName, ...d });
      continue;
    }
    const fields = {
      operation_rate: rateEq(cur.operation_rate, d.opRate) ? null : { from: cur.operation_rate, to: d.opRate },
      transaction_rate: rateEq(cur.transaction_rate, d.txRate) ? null : { from: cur.transaction_rate, to: d.txRate },
      deposit_gmv_lt_5w: intEq(cur.deposit_gmv_lt_5w, d.depLt5w) ? null : { from: cur.deposit_gmv_lt_5w, to: d.depLt5w },
      deposit_gmv_5w_10w: intEq(cur.deposit_gmv_5w_10w, d.dep5w10w) ? null : { from: cur.deposit_gmv_5w_10w, to: d.dep5w10w },
      deposit_gmv_10w_30w: intEq(cur.deposit_gmv_10w_30w, d.dep10w30w) ? null : { from: cur.deposit_gmv_10w_30w, to: d.dep10w30w },
      deposit_gmv_gte_30w: intEq(cur.deposit_gmv_gte_30w, d.depGte30w) ? null : { from: cur.deposit_gmv_gte_30w, to: d.depGte30w },
    };
    const changedFields = Object.entries(fields).filter(([,v]) => v).map(([k,v]) => ({ field: k, ...v }));
    if (changedFields.length === 0) {
      unchanged.push({ catId, name: c.name, parent: c.parentName });
    } else {
      diffs.push({ catId, name: c.name, parent: c.parentName, changes: changedFields });
    }
  }

  return { total: categories.length, unchanged, diffs, unmatched, added,
           changedCount: diffs.length, unchangedCount: unchanged.length,
           unmatchedCount: unmatched.length, addedCount: added.length };
}

function Num(v){ return Number(v); }
