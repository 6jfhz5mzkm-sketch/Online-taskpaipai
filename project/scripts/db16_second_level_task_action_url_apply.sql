-- ============================================================
-- #DB-16 生产变更脚本（生产 apply）—— 「T2.5.5 填写商品数量」跳转链接修正
-- 状态: 待上线批次,**只产出、未执行**;受 dev-docs/部署规则.md 生产部署确认闸约束
--        —— 未获用户本轮明确确认之前,禁止在生产执行本脚本
-- 变更面: second_level_task.actionUrl,唯一一条 DML,只改 actionUrl 一列、只影响 1 行
-- 定位方式: taskId = 'T2.5.5'(该列有 UNIQUE KEY IDX_827dce5e14d27c57b8bc5d1cb5,行数必为 1)
-- 库名: 本脚本**不写死库名**,执行时由执行方显式指定生产库(生产库为 merchant_task_prod)
-- 开发库验证: 2026-09-15 已在 merchant_task 执行同一语句,rowcount = 1,校验通过
-- 执行顺序: ①备份留档 ②预检 ③apply ④校验 ⑤异常则用配套 rollback 脚本
-- ============================================================

-- ① 备份(执行前把本 SELECT 输出留档: 路径 + 字节数 + sha256)
SELECT taskId, actionText, actionUrl FROM second_level_task WHERE taskId = 'T2.5.5';

-- ② 预检: 必须返回 1(否则立即中止)
SELECT COUNT(*) AS should_be_1 FROM second_level_task WHERE taskId = 'T2.5.5';

-- ③ 执行(预期 affected rows = 1)
UPDATE second_level_task
SET actionUrl = 'https://wares-jdm.jd.com/ware/wareList?activeTab=OnsaleWare&businessModel=0'
WHERE taskId = 'T2.5.5';

-- ④ 校验: actionUrl 必须等于新值;actionText 必须仍为 '去京麦商品列表'(未被改动)
SELECT taskId, actionText, actionUrl FROM second_level_task WHERE taskId = 'T2.5.5';
