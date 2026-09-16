
// 规则行 -> 二级类目(category_id) 的映射（作用域/scope 匹配）
// 现状：规则页“二级类目”的深度与数据库类目表不一致（规则里既有 top-level 名、也有二级名、还有合并组），
//       因此按“类目可归属的组”匹配：优先 parentName 组，其次自身名组（均含逗号合并组），组内再按三级类目精确/兜底匹配。
// 匹配优先级：三级类目精确含类目名 > 包含关系 > 其他三级类目 > 组内单行。
// 说明：规则存在重叠组（如 二手钟表 既在 二手奢侈品 组也在 二手钟表 组），此匹配取 parentName 组优先，
//       若有差异会在 dry-run 报告里体现，需人工复核后再 --apply。

function splitNames(s) {
  // 只按顿号/中英文逗号/空白拆分；不拆 '/'
  return (s || '').split(/[、，,\s]+/).map(x => x.trim()).filter(Boolean);
}

// 建立 scopeName（二级类目名或合并组内单个名字）-> 规则行列表
function buildScopeIndex(ruleRows) {
  const byScope = new Map();
  for (const row of ruleRows) {
    const lv2 = (row.lv2 || '').trim();
    const lv2Names = splitNames(lv2);
    const lv3 = (row.lv3 || '').trim();
    const lv3Set = (lv3 && lv3 !== '全部') ? splitNames(lv3) : [];
    for (const n of lv2Names) {
      if (!byScope.has(n)) byScope.set(n, []);
      byScope.get(n).push({ lv2, lv2Set: lv2Names, lv3, lv3Set, row });
    }
  }
  return byScope;
}

function pickWithin(rows, catName) {
  for (const it of rows) if (it.lv3Set.some(n => n === catName)) return it.row;
  for (const it of rows) if (it.lv3Set.some(n => catName.includes(n) || n.includes(catName))) return it.row;
  const fb = rows.find(it => it.lv3 === '其他三级类目' || it.lv3 === '其他');
  if (fb) return fb.row;
  if (rows.length === 1) return rows[0].row;
  return null;
}

function pickRuleRow(scopeIndex, catName, parentName) {
  for (const scope of [parentName, catName]) {
    if (!scope) continue;
    const rows = scopeIndex.get(scope);
    if (!rows || !rows.length) continue;
    const r = pickWithin(rows, catName);
    if (r) return r;
  }
  return null;
}

export function buildDesired(categories, ruleRows) {
  const pIdx = buildScopeIndex(ruleRows);
  const out = new Map();
  for (const c of categories) {
    const rule = pickRuleRow(pIdx, c.name, c.parentName);
    if (!rule) { out.set(c.catId, null); continue; }
    out.set(c.catId, {
      opRate: rule.opRate, txRate: rule.txRate,
      depLt5w: rule.depLt5w, dep5w10w: rule.dep5w10w,
      dep10w30w: rule.dep10w30w, depGte30w: rule.depGte30w,
      rule: rule,
    });
  }
  return out;
}
