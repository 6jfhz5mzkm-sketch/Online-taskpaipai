-- ============================================================
-- #DB-23 second_level_task 新增任务行为语义字段 actionType / actionParam —— 应用脚本(apply)
-- 方案: dev-docs/任务单/action-type-design.md(§2.1 枚举 / §2.3 DDL / §2.4 回填)
-- 变更面: second_level_task 增两列(列序紧随 actionUrl)+ 存量 51 行回填(默认 none + 13 行例外)
-- 库名: **不写死**,执行方显式指定(dev = merchant_task;生产须先过 dev-docs/部署规则.md 确认闸)
-- 幂等: 加列用 information_schema 存在性检查前置(MySQL 8 无 ADD COLUMN IF NOT EXISTS);回填全部带 <> / <=> 守卫
-- 顺序: ①改前快照 SELECT ②预检 ③幂等加列 ④回填(默认已由 DEFAULT 落位 + 13 行例外) ⑤改后校验
-- 回滚: 见 project/scripts/db23_action_type_rollback.sql
-- ============================================================

-- ① 改前快照 SELECT(执行前先跑,把 51 行结果留档;此处只用稳定列,故脚本可重复执行)
SELECT id, taskId, title, status, firstLevelTaskId, stageId, sortOrder, actionUrl FROM second_level_task ORDER BY id;

-- ② 预检(列存在性 + 行数;@cols_ok: 0=两列都不存在(正常首次执行) 2=都已存在(已应用,将 SKIP))
SELECT COUNT(*) AS total_rows_should_be_51 FROM second_level_task;
SET @cols_ok := (SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'second_level_task' AND COLUMN_NAME IN ('actionType','actionParam'));
SELECT @cols_ok AS action_cols_present_should_be_0_or_2;

-- ③ 幂等加列(存在则 SKIP;仅存在一列则报警待人工介入)
SET @ddl_add := IF(@cols_ok = 0, 'ALTER TABLE second_level_task ADD COLUMN actionType VARCHAR(32) NOT NULL DEFAULT ''none'' COMMENT ''行为类型(按钮点击后的交互;枚举:none=无特殊行为/advisor_qr=顾问企微二维码弹窗/category_picker=任务卡内类目选择器/fee_picker=任务卡内资费选择器+定位fee锚点/trademark_lookup=商标注册号查询面板/title_optimize=AI标题优化面板/image_optimize=图片优化区块/advisor_entry=顾问入口区块/data_form=数据分析专区表单录入/data_upload=数据分析专区文件上传)'' AFTER actionUrl, ADD COLUMN actionParam VARCHAR(64) DEFAULT NULL COMMENT ''行为参数(不透明标识,不承载业务规则;仅 data_form/data_upload 使用:data_form 取 star/product-count/health-score,data_upload 取 trade/traffic/product;其余行为为 NULL)'' AFTER actionType', IF(@cols_ok = 2, 'SELECT ''SKIP: actionType/actionParam 均已存在'' AS info', 'SELECT ''PARTIAL: 仅存在一列,请人工确认后再执行'' AS info'));
PREPARE stmt_add FROM @ddl_add;
EXECUTE stmt_add;
DEALLOCATE PREPARE stmt_add;

-- ④ 回填: 默认值由 ADD COLUMN 的 DEFAULT 'none' 落全部 51 行(含 2 行 status=0,不按 status 过滤);以下 13 行例外均幂等
UPDATE second_level_task SET actionType='category_picker'  WHERE taskId='T1.1.2' AND NOT (actionType <=> 'category_picker');
UPDATE second_level_task SET actionType='fee_picker'       WHERE taskId='T1.1.3' AND NOT (actionType <=> 'fee_picker');
UPDATE second_level_task SET actionType='advisor_qr'       WHERE taskId='T1.3.8' AND NOT (actionType <=> 'advisor_qr');
UPDATE second_level_task SET actionType='trademark_lookup' WHERE taskId='T2.1.2' AND NOT (actionType <=> 'trademark_lookup');
UPDATE second_level_task SET actionType='advisor_entry'    WHERE taskId='T2.1.4' AND NOT (actionType <=> 'advisor_entry');
UPDATE second_level_task SET actionType='title_optimize'   WHERE taskId='T2.3.1' AND NOT (actionType <=> 'title_optimize');
UPDATE second_level_task SET actionType='image_optimize'   WHERE taskId='T2.3.2' AND NOT (actionType <=> 'image_optimize');
UPDATE second_level_task SET actionType='data_form',   actionParam='star'          WHERE taskId='T2.5.1' AND NOT (actionType <=> 'data_form'   AND actionParam <=> 'star');
UPDATE second_level_task SET actionType='data_form',   actionParam='product-count' WHERE taskId='T2.5.5' AND NOT (actionType <=> 'data_form'   AND actionParam <=> 'product-count');
UPDATE second_level_task SET actionType='data_form',   actionParam='health-score'  WHERE taskId='T2.5.6' AND NOT (actionType <=> 'data_form'   AND actionParam <=> 'health-score');
UPDATE second_level_task SET actionType='data_upload', actionParam='trade'         WHERE taskId='T2.5.2' AND NOT (actionType <=> 'data_upload' AND actionParam <=> 'trade');
UPDATE second_level_task SET actionType='data_upload', actionParam='traffic'       WHERE taskId='T2.5.3' AND NOT (actionType <=> 'data_upload' AND actionParam <=> 'traffic');
UPDATE second_level_task SET actionType='data_upload', actionParam='product'       WHERE taskId='T2.5.4' AND NOT (actionType <=> 'data_upload' AND actionParam <=> 'product');

-- ⑤ 改后校验: 期望 —— 枚举值 10 个(GROUP BY actionType = 10 组)/ 合计 51 行 / 例外行 13 / 带参数行 6;
--    注: GROUP BY actionType, actionParam 会得到 14 组(6 行 data_* 各带不同参数),这是参数维度的正常展开,不是 10。
SELECT actionType, actionParam, COUNT(*) AS rows_cnt FROM second_level_task GROUP BY actionType, actionParam ORDER BY actionType, actionParam;
SELECT COUNT(*) AS groups_by_action_type_should_be_10 FROM (SELECT 1 FROM second_level_task GROUP BY actionType) x;
SELECT COUNT(DISTINCT actionType) AS distinct_action_type_should_be_10 FROM second_level_task;
SELECT COUNT(*) AS groups_by_type_param_should_be_14 FROM (SELECT 1 FROM second_level_task GROUP BY actionType, actionParam) x;
SELECT COUNT(*) AS total_rows_should_be_51 FROM second_level_task;
SELECT COUNT(*) AS exception_rows_should_be_13 FROM second_level_task WHERE actionType <> 'none';
SELECT COUNT(*) AS param_rows_should_be_6 FROM second_level_task WHERE actionParam IS NOT NULL;
SELECT COUNT(*) AS invalid_enum_should_be_0 FROM second_level_task WHERE actionType NOT IN ('none','advisor_qr','category_picker','fee_picker','trademark_lookup','title_optimize','image_optimize','advisor_entry','data_form','data_upload');
SELECT COUNT(*) AS invalid_param_should_be_0 FROM second_level_task WHERE (actionType='data_form' AND (actionParam IS NULL OR actionParam NOT IN ('star','product-count','health-score'))) OR (actionType='data_upload' AND (actionParam IS NULL OR actionParam NOT IN ('trade','traffic','product'))) OR (actionType NOT IN ('data_form','data_upload') AND actionParam IS NOT NULL);
SELECT taskId, actionType, actionParam FROM second_level_task WHERE actionType <> 'none' ORDER BY actionType, taskId;