-- ============================================================
-- #DB-16 生产变更脚本（生产 rollback）—— 回退 「T2.5.5」的 actionUrl
-- 状态: 待上线批次,**只产出、未执行**;受 dev-docs/部署规则.md 生产部署确认闸约束
-- 配套: DB16-second-level-task-action-url-prod-apply.sql
-- 回退目标值来自开发库备份(2026-09-15, sha256 1353dfc8888c230886c2f3ed3f94b69124052550efa3f71a066e761cb4fc8f35)。
-- ⚠️ 若生产库该行 actionUrl 现值与开发库备份值不同,一律以**生产执行前的实机备份值**为准回退,
--    不要机械照抄下面的字符串。
-- 库名: 本脚本**不写死库名**,执行时由执行方显式指定生产库(生产库为 merchant_task_prod)
-- ============================================================

-- ① 回退前记录当前值(留档)
SELECT taskId, actionText, actionUrl FROM second_level_task WHERE taskId = 'T2.5.5';

-- ② 回退(预期 affected rows = 1)
UPDATE second_level_task
SET actionUrl = 'https://wares-jdm.jd.com/ware/wareList'
WHERE taskId = 'T2.5.5';

-- ③ 校验: actionUrl 回到旧值
SELECT taskId, actionText, actionUrl FROM second_level_task WHERE taskId = 'T2.5.5';
