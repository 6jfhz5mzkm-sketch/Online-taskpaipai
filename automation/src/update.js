
// 依据比对结果更新 fee_config（仅 --apply 时调用，事务内执行）
// 注意：diff 只含“变更字段”，因此必须先取当前行，把变更字段合并后再整行 UPDATE，
// 避免把未变更字段写成 NULL。
import { getPool } from './db.js';

// autoAdd：新增类目是否自动入库。默认 false —— 按 SOP「新增类目以用户确认是否招商为准」，
// 新增类目仅报告、不强插库；确需自动新增时设环境变量 FEE_SYNC_AUTO_ADD=1。
const AUTO_ADD = process.env.FEE_SYNC_AUTO_ADD === '1';

export async function applyChanges(result) {
  if (result.changedCount === 0 && (result.addedCount === 0 || !AUTO_ADD)) {
    return { updated: 0, added: 0 };
  }
  const pool = getPool();
  const conn = await pool.getConnection();
  let updated = 0, added = 0;
  try {
    await conn.beginTransaction();
    for (const d of result.diffs) {
      // 取当前行
      const [rows] = await conn.query(
        `SELECT operation_rate, transaction_rate,
                deposit_gmv_lt_5w, deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w
         FROM fee_config WHERE category_id = ? AND is_active = 1`,
        [d.catId],
      );
      const cur = rows[0];
      if (!cur) continue;
      const merged = { ...cur };
      for (const c of d.changes) merged[c.field] = c.to;
      await conn.query(
        `UPDATE fee_config SET
           operation_rate = ?, transaction_rate = ?,
           deposit_gmv_lt_5w = ?, deposit_gmv_5w_10w = ?,
           deposit_gmv_10w_30w = ?, deposit_gmv_gte_30w = ?
         WHERE category_id = ? AND is_active = 1`,
        [merged.operation_rate, merged.transaction_rate,
         merged.deposit_gmv_lt_5w, merged.deposit_gmv_5w_10w,
         merged.deposit_gmv_10w_30w, merged.deposit_gmv_gte_30w,
         d.catId],
      );
      updated++;
    }
    if (AUTO_ADD) for (const a of result.added) {
      await conn.query(
        `INSERT INTO fee_config
           (category_id, operation_rate, transaction_rate,
            deposit_gmv_lt_5w, deposit_gmv_5w_10w, deposit_gmv_10w_30w, deposit_gmv_gte_30w, is_active)
         VALUES (?, ?, ?, ?, ?, ?, ?, 1)
         ON DUPLICATE KEY UPDATE
           operation_rate = VALUES(operation_rate), transaction_rate = VALUES(transaction_rate),
           deposit_gmv_lt_5w = VALUES(deposit_gmv_lt_5w), deposit_gmv_5w_10w = VALUES(deposit_gmv_5w_10w),
           deposit_gmv_10w_30w = VALUES(deposit_gmv_10w_30w), deposit_gmv_gte_30w = VALUES(deposit_gmv_gte_30w)`,
        [a.catId, a.opRate, a.txRate, a.depLt5w, a.dep5w10w, a.dep10w30w, a.depGte30w],
      );
      added++;
    }
    await conn.commit();
  } catch (e) {
    await conn.rollback();
    throw e;
  } finally {
    conn.release();
  }
  return { updated, added };
}
