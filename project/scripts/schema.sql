-- ============================================================
-- 京东拍拍二手 · 商家任务体系 — 数据库 Schema
-- 版本: v1.11
-- 日期: 2026-07-20 (v1.2: 2026-08-07 对齐实库: 补充 ai_analysis_log/stage_config,
--       修正 V1 表列名与索引为实库实际结构)
--       (v1.3: 2026-09-10 merchant_task_progress 增加唯一键 uk_merchant_task (merchantId, taskId))
--       (v1.4: 2026-09-10 任务单 #DB-2: fee_config 补 uk_category (category_id) —— 恢复注释与
--       历史迁移声明的"一个类目一套资费"约束; stage_config 补 uk_stage_id (stage_id) —— 对齐
--       已有 ORM 声明并消除 alembic add_constraint 漂移)
--       (v1.6: 2026-09-11 任务单 #DB-7 第 1 部分 —— P-4 (1) 双表收敛: 删除与 stage_config 重复且
--       无任何调用依赖的 stage 段(经 api-py/backend/admin/src/project/src 全量复核 0 引用);
--       表数 24 -> 23，UNIQUE KEY 18 -> 17(移除 stage.uk_stage_id);
--       DDL 仅本地 dev 执行，备份 Temp/db7_backup_20260911_094353/。注意: 本段之后的
--       所有行号较 v1.5 上移 22 行)
--       (v1.7: 2026-09-14 任务单 #DB-12 —— P7 v1.1「全阶段加密」主线第一单: 新增 ai_entry_config(含api_key_ciphertext/api_key_fingerprint，无任何明文 key 列) 与 admin_ai_config_audit(含 old_fp/new_fp)；表数 23 -> 25，段号 25/26 顺延不重排；DDL 仅本地 dev 执行，生产待用户确认后另派)
--       (v1.8: 2026-09-16 任务单 #PL-4 / #DB-13 —— 商家手机号 + 短信验证码登录(叠加阿里云验证码 2.0 服务端校验):
--       新增 merchant_login_code(段 27;验证码只存 sha256(code_salt + code) + 每行随机盐,5 分钟失效、一次性 used_at、
--       频控与校验次数全部落库计数)、internal_notify_log(段 28;内部通知 sent/failed 留痕,可手工重放)、
--       captcha_daily_counter(段 29;验证码 2.0 每日调用计数,1 行/天天然有界 —— G-4 裁定: 不建 append-only 调用日志);
--       merchant 段补 UNIQUE KEY uk_phone(phone)(G-3 裁定: 软删商家仍占用该键);表数 25 -> 28,段号顺延不重排;
--       DDL 仅本地 dev 执行。方案: dev-docs/任务单/phone-sms-login-design.md;生产待用户确认后另派)
--       (v1.9: 2026-09-16 任务单 #DB-14 —— 短信改走阿里云 PNVS 短信认证(SendSmsVerifyCode / CheckSmsVerifyCode，
--       验证码由阿里云生成与校验): merchant_login_code 由「自建验证码存储」改为「发送/校验审计 + 频控计数」表 ——
--       删除 code_hash/code_salt/expires_at，新增 biz_id/out_id(列序 id, phone, biz_id, out_id, ip, attempts,
--       used_at, created_at 共 8 列)，attempts 注释改为「该行校验失败次数(我方兜底闸,防爆破)」，表注释同步更新；
--       表数仍 28、段号不变；DDL 仅本地 dev 执行(含按主键 id 清理 5 行旧口径联调数据，备份 Temp/db14_login_code_rows_backup_*.json)
--       (v1.10: 2026-09-16 任务单 #DB-19 / #PL-7 —— 账号绑定(1 个京麦商家ID ↔ N 个商家账号，只共享进度):
--       新增 merchant_binding_group(段 30;uk_group_active(jd_merchant_id, active_key) 保证一个 ID 只有一个活跃组)
--       与 merchant_binding_member(段 31;uk_member_active(merchant_id, active_key) 保证一个账号只在一个活跃组；
--       解绑 = active_key 置 NULL + released_at/by 留痕，不删行)；internal_notify_log(段 28) 就地补 dedupe_key
--       与 idx_event_dedupe(event_type, dedupe_key, created_at)(24h 通知去重窗口)；表数 28 -> 30，段号顺延不重排；
--       DDL 仅本地 dev 执行。方案: dev-docs/任务单/merchant-account-binding-design.md;生产待用户确认后另派)
--       (v1.10 补充, 2026-09-16, #DB-20: 注释措辞对齐（**无结构变更**，版本号仍 v1.10）—— 段 29 表/列注释由旧称
--        「验证码 2.0」改为「人机校验(图形认证服务端二次校验)」(口径来源 #PL-4 方案 v1.2 / 真源 §5.2 API-21)；
--        段 28 event_type 列注释补第二个事件 jd_duplicate_registration(#PL-7 §5.3))
--       (v1.10 补充2, 2026-09-16, #DB-21: 事件名订正 —— #DB-20 按当时口径写入的长名(34 字符)超 event_type 列宽 32,
--        会触 (1406) Data too long;总控裁决采用短名 jd_duplicate_registration(25 字符)。完整原拟名与复现记录见
--        方案 §5.3 偏差记录与 app/services/internal_notify.py:35-37;代码/真源已按短名统一,本注释同步订正。
--        **无结构变更**,版本号仍 v1.10)
--       (v1.11: 2026-09-16 任务单 #DB-23 / #PL-13 —— second_level_task(段 12) 新增任务行为语义两列:
--       actionType VARCHAR(32) NOT NULL DEFAULT 'none'(行为类型,枚举 10 值: none/advisor_qr/category_picker/
--       fee_picker/trademark_lookup/title_optimize/image_optimize/advisor_entry/data_form/data_upload)
--       与 actionParam VARCHAR(64) NULL(行为参数,仅 data_form/data_upload 使用的不透明标识),列序紧随 actionUrl;
--       存量 51 行由 DEFAULT 'none' 落位 + 13 行例外回填(方案 dev-docs/任务单/action-type-design.md §2.4);
--       DDL/回填仅本地 dev 执行,脚本 project/scripts/db23_action_type_{apply,rollback}.sql;生产待用户确认后另派)
--       (v1.11 补充, 2026-09-16, #DB-24: 段 12 的 type/completionType 列注释枚举对齐现实取值(type 6 值 / completionType 5 值,
--        含旧轴遗留 form/jump/upload 与 form_submit/file_upload,并注明行为语义以 actionType 为准)。**无结构变更**,版本号仍 v1.11;
--        后端 Literal 与 AF 下拉修正分别由 #PB-40 / #AF-21 负责)
--       (v1.5: 2026-09-10 任务单 #DB-5 批 1 —— 按实库对齐: 44 列补 NOT NULL、18 列时间精度 DATETIME(6)+CURRENT_TIMESTAMP(6)、4 张表(stage/stage_config/merchant/merchant_category)列序对齐实库、
--       24 张表显式 COLLATE=utf8mb4_0900_ai_ci(消除对服务器默认值的依赖)、10 列补注释; 逐列依据见 dev-docs/任务单/DB4-schema-db-convergence.md)
-- 段号说明: 段号 10（原 stage 表）已于 2026-09-11 由 #DB-7 删除，编号不重排（重排会使全文件行号位移），后续段号沿用原序；现最大段号 31 而实际表数 30，偏移仅此一处（段 10 是唯一跳号）。#DB-17 于本区与段 11 前各补 1 行说明；#DB-13 追加段 27/28/29、#DB-19 追加段 30/31（账号绑定两表）并同步本行计数
-- 数据库: MySQL 8.0
-- 字符集: utf8mb4
-- ============================================================

-- ============================================================
-- 1. merchant（商家）
-- 代表对象: 在拍拍二手平台开店的企业商家，系统核心主体
-- 关联: merchant_category(1:N), event_log(1:N), feishu_notification(1:N)
-- ============================================================
CREATE TABLE merchant (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  nickname VARCHAR(128) DEFAULT '' COMMENT '昵称',
  avatar VARCHAR(512) DEFAULT '' COMMENT '头像URL',
  merchant_name VARCHAR(256) DEFAULT '' COMMENT '企业名称',
  phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  feishu_open_id VARCHAR(128) DEFAULT NULL COMMENT '飞书OpenID',
  feishu_union_id VARCHAR(128) DEFAULT NULL COMMENT '飞书UnionID',
  feishu_user_id VARCHAR(64) DEFAULT NULL COMMENT '飞书UserID',
  current_stage VARCHAR(32) DEFAULT 'onboarding' COMMENT '当前阶段',
  tour_seen TINYINT NOT NULL DEFAULT 0 COMMENT '新手引导已看标记 0=未看 1=已看（账号级，方案B）',
  welcome_sent TINYINT NOT NULL DEFAULT 0 COMMENT '欢迎消息是否已发（仅首次登录发送） 0=未发 1=已发',
  jd_merchant_id VARCHAR(64) DEFAULT NULL COMMENT '京东商家ID(阶段二前登记)',
  shop_name VARCHAR(128) DEFAULT NULL COMMENT '店铺名称(阶段二前登记)',
  status TINYINT DEFAULT 1 COMMENT '0=禁用 1=正常 2=已退出',
  registered_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
  last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后活跃',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
  data_center_unlocked TINYINT DEFAULT 0 COMMENT '数据专区解锁标记 0=未 1=已(永久)',
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_id (merchant_id),
  UNIQUE KEY uk_feishu_open_id (feishu_open_id),
  UNIQUE KEY uk_phone (phone),
  KEY idx_feishu_user_id (feishu_user_id),
  KEY idx_status (status),
  KEY idx_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家表';

-- ============================================================
-- 2. category（商品类目）
-- 代表对象: 平台的商品分类体系，两级结构（一级类目 → 二级类目）
-- 关联: category(自关联 parent_id), fee_config(1:N), fee_brand_override(1:N), merchant_category(N:M中间表)
-- ============================================================
CREATE TABLE category (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  parent_id BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '父类目ID(0=一级)',
  name VARCHAR(128) NOT NULL COMMENT '类目名称',
  sort_order SMALLINT NOT NULL DEFAULT 0 COMMENT '排序',
  is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME(6) DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品类目表';

-- ============================================================
-- 3. fee_config（资费配置）
-- 代表对象: 某个二级类目的佣金费率和保证金档位
-- 关联: category(N:1), fee_brand_override(1:N, 同类目的品牌覆盖)
-- 设计说明: 一个类目只有一套基础资费，用 UNIQUE KEY 保证
-- 变更原因 (v1.4, 2026-09-10, 任务单 #DB-2 D-1):
--   本表 DDL 长期缺失唯一键，与本节注释、ORM 文档(models/fee_config.py: "一个二级类目一套基础资费")
--   及历史迁移(scripts/migrations/1700000000000-InitSchema.ts:68 曾定义 uk_category_id)均不一致;
--   缺失时读路径 app/services/fee.py:14-16 用 scalar_one_or_none() 取基础资费,
--   一旦出现重复 category_id 行即抛 MultipleResultsFound(POST 500, 与 #DB-1 uk_merchant_task 同类故障)。
--   实测 dev 库 309 行 / 309 个 distinct category_id(无重复、无孤儿、全部 is_active=1)，补键不影响存量数据。
--   存量库(本地 dev / 生产)升级语句:
--     ALTER TABLE fee_config ADD UNIQUE KEY uk_category (category_id);
--   注意: 该键按"一个类目一套资费"建模; 若后续要求费率版本化(软删除旧行 + 新增生效行)，须重新评估该键。
-- ============================================================
CREATE TABLE fee_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id BIGINT UNSIGNED NOT NULL COMMENT '关联二级类目',
  operation_rate DECIMAL(5,2) NOT NULL COMMENT '运营支持服务费率(%)',
  transaction_rate DECIMAL(5,2) NOT NULL COMMENT '交易服务费率(%)',
  deposit_gmv_lt_5w INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '保证金-GMV<5万(元)',
  deposit_gmv_5w_10w INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '保证金-GMV 5-10万(元)',
  deposit_gmv_10w_30w INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '保证金-GMV 10-30万(元)',
  deposit_gmv_gte_30w INT UNSIGNED NOT NULL DEFAULT 0 COMMENT '保证金-GMV>=30万(元)',
  is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME(6) DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_category (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='资费配置表';

-- ============================================================
-- 4. fee_brand_override（品牌资费覆盖）
-- 代表对象: 特殊资费表，部分品牌在特定类目下有不同的费率
-- 关联: category(N:1)
-- 设计说明: 保证金与基础资费一致，不重复存储，查询时 JOIN fee_config
-- ============================================================
CREATE TABLE fee_brand_override (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id BIGINT UNSIGNED NOT NULL COMMENT '关联二级类目',
  brand_name VARCHAR(128) NOT NULL COMMENT '品牌名称',
  operation_rate DECIMAL(5,2) NOT NULL COMMENT '运营支持服务费率-覆盖值(%)',
  transaction_rate DECIMAL(5,2) NOT NULL COMMENT '交易服务费率-覆盖值(%)',
  is_active TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  deleted_at DATETIME(6) DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='品牌资费覆盖表';

-- ============================================================
-- 5. merchant_category（商家经营类目）
-- 代表对象: 商家选择的经营品类，是 merchant 和 category 的多对多中间表
-- 关联: merchant(N:1), category(N:1)
-- 设计说明: 任务 T1.1.2 "选择经营品类（1-3个）" 的结果
-- ============================================================
CREATE TABLE merchant_category (
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  is_primary TINYINT NOT NULL DEFAULT 0 COMMENT '是否主营类目',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  id INT NOT NULL AUTO_INCREMENT,
  category_id INT NOT NULL COMMENT '类目ID',
  PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家经营类目表';

-- ============================================================
-- 6. event_log（埋点事件）
-- 代表对象: 一次用户行为事件的流水记录
-- 关联: merchant(N:1, 弱关联), task_key/stage_key 为字符串标记非外键
-- 设计说明: 日志表只追加不删除，定期归档，不需要 deleted_at
-- ============================================================
CREATE TABLE event_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) DEFAULT NULL COMMENT '商家ID(未登录为空)',
  event_type VARCHAR(64) NOT NULL COMMENT '事件类型',
  page_name VARCHAR(128) DEFAULT NULL COMMENT '页面名称',
  task_key VARCHAR(32) DEFAULT NULL COMMENT '关联任务(弱关联)',
  stage_key VARCHAR(32) DEFAULT NULL COMMENT '关联阶段(弱关联)',
  element VARCHAR(128) DEFAULT NULL COMMENT '交互元素标识',
  meta JSON COMMENT '扩展数据',
  ip VARCHAR(45) DEFAULT NULL COMMENT '客户端IP',
  user_agent VARCHAR(512) DEFAULT NULL COMMENT 'UA信息',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '事件时间',
  PRIMARY KEY (id),
  KEY idx_merchant_id (merchant_id),
  KEY idx_event_type (event_type),
  KEY idx_created_at (created_at),
  KEY idx_page_name (page_name),
  KEY idx_task_key (task_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='埋点事件表';

-- ============================================================
-- 7. feishu_notification（飞书通知）
-- 代表对象: 一条发给商家的飞书消息的完整生命周期记录
-- 关联: merchant(N:1)
-- 设计说明: 追踪消息从发送到被阅读的全过程，用于频率控制和打开率统计
-- ============================================================
CREATE TABLE feishu_notification (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  template_type VARCHAR(32) NOT NULL COMMENT '模板类型',
  title VARCHAR(256) NOT NULL COMMENT '消息标题',
  content TEXT NOT NULL COMMENT '消息内容',
  h5_url VARCHAR(1024) DEFAULT NULL COMMENT '跳转链接',
  status VARCHAR(16) DEFAULT 'sent' COMMENT 'sent/delivered/opened/failed',
  sent_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '发送时间',
  delivered_at DATETIME DEFAULT NULL COMMENT '送达时间',
  opened_at DATETIME DEFAULT NULL COMMENT '打开时间',
  error_msg VARCHAR(512) DEFAULT NULL COMMENT '失败原因',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  KEY idx_merchant_id (merchant_id),
  KEY idx_template_type (template_type),
  KEY idx_sent_at (sent_at),
  KEY idx_status (status),
  KEY idx_deleted_at (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='飞书通知表';

-- ============================================================
-- 8. category_requirement（类目资质要求）
-- 代表对象: 每个二级类目的入驻资质要求，与 fee_config 同级
-- 关联: category(N:1, 一个类目一套要求)
-- 设计说明: 基础资质为所有类目通用，类目专属要求按需配置
-- ============================================================
CREATE TABLE category_requirement (
    id              BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    category_id     BIGINT UNSIGNED NOT NULL COMMENT '关联二级类目',
    shop_type       VARCHAR(50) NOT NULL DEFAULT '专营店' COMMENT '店铺类型（专营店/旗舰店）',
    shop_name_rule  VARCHAR(200) DEFAULT NULL COMMENT '店铺名命名规范',
    requirements    JSON NOT NULL COMMENT '类目专属资质要求列表',
    review_focus    TEXT COMMENT '审核重点或特殊说明',
    contact_email   VARCHAR(100) DEFAULT NULL COMMENT '招商对接邮箱',
    is_active       TINYINT NOT NULL DEFAULT 1 COMMENT '是否启用',
    created_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    updated_at      DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    deleted_at      DATETIME(6) DEFAULT NULL COMMENT '软删除',
    PRIMARY KEY (id),
    UNIQUE KEY IDX_d9d61d087ba3eded1ec4086dc0 (category_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='类目资质要求表';

-- ============================================================
-- 9. admin_account（管理员账号表）
-- 代表对象: 任务管理后台的管理员账号
-- ============================================================
CREATE TABLE admin_account (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  username VARCHAR(64) NOT NULL COMMENT '登录用户名',
  passwordHash VARCHAR(256) NOT NULL COMMENT '密码哈希值',
  salt VARCHAR(64) NOT NULL COMMENT '密码盐值',
  realName VARCHAR(64) NOT NULL DEFAULT '' COMMENT '真实姓名',
  phone VARCHAR(20) DEFAULT NULL COMMENT '手机号',
  email VARCHAR(128) DEFAULT NULL COMMENT '邮箱',
  role VARCHAR(16) NOT NULL DEFAULT 'admin' COMMENT '角色(super_admin/admin/viewer)',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  lastLoginAt DATETIME DEFAULT NULL COMMENT '最后登录时间',
  lastLoginIp VARCHAR(45) DEFAULT NULL COMMENT '最后登录IP',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  deletedAt DATETIME(6) DEFAULT NULL COMMENT '软删除时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_a6a5b15c5c225de1b4ecbfef9e (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='管理员账号表';

-- ============================================================
-- （编号 10 原为 stage 表，已于 2026-09-11 由 #DB-7 删除；为避免全文件行号位移，编号不重排，后续编号沿用原序）
-- 11. first_level_task（一级任务表）
-- 代表对象: 阶段下的任务分组
-- ============================================================
CREATE TABLE first_level_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  taskId VARCHAR(32) NOT NULL COMMENT '一级任务唯一标识',
  stageId VARCHAR(32) NOT NULL COMMENT '所属阶段',
  title VARCHAR(128) NOT NULL COMMENT '一级任务标题',
  description TEXT COMMENT '一级任务描述',
  buttonText VARCHAR(64) NOT NULL DEFAULT '' COMMENT '按钮文案',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_61f121d89996f7548b239af555 (taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='一级任务表';

-- ============================================================
-- 12. second_level_task（二级任务表）
-- 代表对象: 具体可执行的任务项
-- ============================================================
CREATE TABLE second_level_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  taskId VARCHAR(32) NOT NULL COMMENT '二级任务唯一标识',
  firstLevelTaskId VARCHAR(32) NOT NULL COMMENT '所属一级任务',
  stageId VARCHAR(32) NOT NULL COMMENT '所属阶段(冗余)',
  title VARCHAR(128) NOT NULL COMMENT '二级任务标题',
  description TEXT COMMENT '二级任务描述',
  detail TEXT COMMENT '任务详情(Markdown)',
  type VARCHAR(16) NOT NULL COMMENT '任务类型/重要度(mandatory=必做/suggested=建议/guide=引导;另存旧轴遗留值 form/jump/upload——属交互形态的旧轴残留,行为语义一律以 actionType 为准,勿再新增此类值)',
  completionType VARCHAR(16) NOT NULL COMMENT '完成方式(system_check=系统校验/manual_submit=人工提交/click_read=点击阅读;另存旧轴遗留值 form_submit=表单提交/file_upload=文件上传——行为语义同样以 actionType 为准)',
  actionText VARCHAR(64) DEFAULT NULL COMMENT '操作按钮文案',
  actionUrl VARCHAR(512) DEFAULT NULL COMMENT '操作按钮链接',
  actionType VARCHAR(32) NOT NULL DEFAULT 'none' COMMENT '行为类型(按钮点击后的交互;枚举:none=无特殊行为/advisor_qr=顾问企微二维码弹窗/category_picker=任务卡内类目选择器/fee_picker=任务卡内资费选择器+定位fee锚点/trademark_lookup=商标注册号查询面板/title_optimize=AI标题优化面板/image_optimize=图片优化区块/advisor_entry=顾问入口区块/data_form=数据分析专区表单录入/data_upload=数据分析专区文件上传)',
  actionParam VARCHAR(64) DEFAULT NULL COMMENT '行为参数(不透明标识,不承载业务规则;仅 data_form/data_upload 使用:data_form 取 star/product-count/health-score,data_upload 取 trade/traffic/product;其余行为为 NULL)',
  tag VARCHAR(32) DEFAULT NULL COMMENT '标签',
  defaultCompleted TINYINT NOT NULL DEFAULT 0 COMMENT '默认已完成',
  status TINYINT NOT NULL DEFAULT 1 COMMENT '0=禁用 1=启用',
  sortOrder INT NOT NULL DEFAULT 0 COMMENT '排序',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY IDX_827dce5e14d27c57b8bc5d1cb5 (taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='二级任务表';

-- ============================================================
-- 13. merchant_task_progress（商家任务进度表）
-- 代表对象: 商家的任务完成进度
-- 关联: merchant(N:1, 弱关联 merchantId), second_level_task(N:1, 弱关联 taskId)
-- 设计说明: 一个商家对一个二级任务只能有一条进度记录，用 uk_merchant_task 保证
-- 变更原因 (v1.3, 2026-09-10, 任务单 #DB-1，依据 R-取消完成同步方案 §2.3.3):
--   本表原仅有 PRIMARY KEY(id)，同一 (merchantId, taskId) 可写入多行，导致
--   ① 读路径按 status=completed 过滤收集 taskId 时，只要存在任意一行 completed，
--      已成功取消的任务仍被判为完成；
--   ② 写路径 scalar_one_or_none() 遇重复行抛 MultipleResultsFound，POST 直接 500。
--   修复: 增加唯一键 uk_merchant_task (merchantId, taskId)；写入侧改为基于该键的 upsert。
--   存量库(本地 dev / 生产)升级语句:
--     ALTER TABLE merchant_task_progress ADD UNIQUE KEY uk_merchant_task (merchantId, taskId);
--   执行前须先清理重复行(保留 updatedAt 最新一行，updatedAt 相同时保留 id 最大者)，
--   否则 ALTER 因 1062 失败。生产库未部署，本轮只在本地 dev 库执行。
-- ============================================================
CREATE TABLE merchant_task_progress (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchantId VARCHAR(64) NOT NULL COMMENT '商家ID',
  taskId VARCHAR(32) NOT NULL COMMENT '二级任务ID',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT 'pending/in_progress/completed/expired',
  completedAt DATETIME DEFAULT NULL COMMENT '完成时间',
  createdAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updatedAt DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_task (merchantId, taskId)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家任务进度表';

-- ============================================================
-- 14. trademark_registry（商标注册号映射表）
-- 代表对象: 品牌名称与商标注册号/申请注册号的映射，支撑阶段二 T2.1.2 查询
-- 关联: 无外键，独立数据
-- 设计说明: 同一品牌可有多个注册号，(brand_name, registration_number) 唯一
-- ============================================================
CREATE TABLE trademark_registry (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  brand_name VARCHAR(128) NOT NULL COMMENT '品牌名称',
  registration_number VARCHAR(64) NOT NULL COMMENT '申请/注册号',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_brand_number (brand_name, registration_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商标注册号映射表';

-- ============================================================
-- 15. shop_star_data（店铺星级数据）
-- 代表对象: 阶段二 T2.5.1 商家上传的店铺星级及各因子得分
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_star_data (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  shop_star DECIMAL(2,1) NOT NULL COMMENT '店铺星级(1.0-5.0)',
  service_score DECIMAL(3,1) DEFAULT NULL COMMENT '客服咨询因子得分',
  logistics_score DECIMAL(3,1) DEFAULT NULL COMMENT '物流履约因子得分',
  after_sale_score DECIMAL(3,1) DEFAULT NULL COMMENT '售后服务因子得分',
  product_score DECIMAL(3,1) DEFAULT NULL COMMENT '商品体验因子得分',
  data_date DATE NOT NULL COMMENT '数据日期',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date (merchant_id, data_date),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='店铺星级数据';

-- ============================================================
-- 16. shop_trade_data（交易数据）
-- 代表对象: 阶段二 T2.5.2 商家上传的交易概况数据（商智 12 项指标）
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_trade_data (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  trade_amount DECIMAL(12,2) DEFAULT NULL COMMENT '成交金额',
  trade_orders INT UNSIGNED DEFAULT NULL COMMENT '成交单量',
  trade_customers INT UNSIGNED DEFAULT NULL COMMENT '成交客户数',
  shop_visitors INT UNSIGNED DEFAULT NULL COMMENT '店铺访客数',
  shop_page_views INT UNSIGNED DEFAULT NULL COMMENT '店铺浏览量',
  trade_items INT UNSIGNED DEFAULT NULL COMMENT '成交商品件数',
  conversion_rate DECIMAL(5,2) DEFAULT NULL COMMENT '店铺成交转化率(%)',
  customer_unit_price DECIMAL(10,2) DEFAULT NULL COMMENT '客单价',
  avg_stay_duration DECIMAL(8,2) DEFAULT NULL COMMENT '店铺平均停留时长(秒)',
  cart_customers INT UNSIGNED DEFAULT NULL COMMENT '加购客户数',
  cart_items INT UNSIGNED DEFAULT NULL COMMENT '加购商品件数',
  cart_conversion_rate DECIMAL(5,2) DEFAULT NULL COMMENT '加购转化率(%)',
  data_date DATE NOT NULL COMMENT '数据日期',
  time_range VARCHAR(16) DEFAULT NULL COMMENT '时间范围(yesterday/7d/30d)',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date_range (merchant_id, data_date, time_range),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='交易数据';

-- ============================================================
-- 17. shop_traffic_data（流量数据）
-- 代表对象: 阶段二 T2.5.3 商家上传的流量概况数据（商智指标）
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_traffic_data (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  shop_visitors INT UNSIGNED DEFAULT NULL COMMENT '店铺访客数',
  shop_page_views INT UNSIGNED DEFAULT NULL COMMENT '店铺浏览量',
  avg_stay_duration DECIMAL(8,2) DEFAULT NULL COMMENT '店铺平均停留时长(秒)',
  product_visitors INT UNSIGNED DEFAULT NULL COMMENT '商品访客数',
  product_page_views INT UNSIGNED DEFAULT NULL COMMENT '商品浏览量',
  product_avg_page_views DECIMAL(5,2) DEFAULT NULL COMMENT '商品人均浏览量',
  product_avg_stay_duration DECIMAL(8,2) DEFAULT NULL COMMENT '商品平均停留时长(秒)',
  uv_value DECIMAL(10,2) DEFAULT NULL COMMENT 'UV价值',
  customer_unit_price DECIMAL(10,2) DEFAULT NULL COMMENT '客单价',
  product_exposure_count INT UNSIGNED DEFAULT NULL COMMENT '商品曝光次数',
  product_exposure_users INT UNSIGNED DEFAULT NULL COMMENT '商品曝光人数',
  trade_customers INT UNSIGNED DEFAULT NULL COMMENT '成交客户数',
  cart_customers INT UNSIGNED DEFAULT NULL COMMENT '加购客户数',
  cart_conversion_rate DECIMAL(5,2) DEFAULT NULL COMMENT '加购转化率(%)',
  cart_amount DECIMAL(12,2) DEFAULT NULL COMMENT '加购金额',
  trade_conversion_rate DECIMAL(5,2) DEFAULT NULL COMMENT '成交转化率(%)',
  trade_items INT UNSIGNED DEFAULT NULL COMMENT '成交商品件数',
  trade_orders INT UNSIGNED DEFAULT NULL COMMENT '成交单量',
  trade_amount DECIMAL(12,2) DEFAULT NULL COMMENT '成交金额',
  data_date DATE NOT NULL COMMENT '数据日期',
  time_range VARCHAR(16) DEFAULT NULL COMMENT '时间范围(yesterday/7d/30d)',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date_range (merchant_id, data_date, time_range),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='流量数据';

-- ============================================================
-- 18. shop_product_data（商品数据）
-- 代表对象: 阶段二 T2.5.4 商家上传的商品概况数据（商智指标）
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_product_data (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  active_spu_count INT UNSIGNED DEFAULT NULL COMMENT '动销SPU数',
  spu_active_rate DECIMAL(5,2) DEFAULT NULL COMMENT 'SPU动销率(%)',
  trade_amount DECIMAL(12,2) DEFAULT NULL COMMENT '成交金额',
  trade_items INT UNSIGNED DEFAULT NULL COMMENT '成交商品件数',
  trade_orders INT UNSIGNED DEFAULT NULL COMMENT '成交单量',
  trade_customers INT UNSIGNED DEFAULT NULL COMMENT '成交客户数',
  trade_conversion_rate DECIMAL(5,2) DEFAULT NULL COMMENT '成交转化率(%)',
  customer_unit_price DECIMAL(10,2) DEFAULT NULL COMMENT '客单价',
  item_unit_price DECIMAL(10,2) DEFAULT NULL COMMENT '件单价',
  cart_spu_count INT UNSIGNED DEFAULT NULL COMMENT '加购SPU数',
  spu_cart_rate DECIMAL(5,2) DEFAULT NULL COMMENT 'SPU加购率(%)',
  cart_items INT UNSIGNED DEFAULT NULL COMMENT '加购商品件数',
  cart_customers INT UNSIGNED DEFAULT NULL COMMENT '加购客户数',
  cart_amount DECIMAL(12,2) DEFAULT NULL COMMENT '加购金额',
  visit_spu_count INT UNSIGNED DEFAULT NULL COMMENT '访问SPU数',
  product_page_views INT UNSIGNED DEFAULT NULL COMMENT '商品浏览量',
  product_visitors INT UNSIGNED DEFAULT NULL COMMENT '商品访客数',
  product_avg_page_views DECIMAL(5,2) DEFAULT NULL COMMENT '商品人均浏览量',
  product_avg_stay_duration DECIMAL(8,2) DEFAULT NULL COMMENT '商详平均停留时长(秒)',
  listed_spu_count INT UNSIGNED DEFAULT NULL COMMENT '上架SPU数',
  data_date DATE NOT NULL COMMENT '数据日期',
  time_range VARCHAR(16) DEFAULT NULL COMMENT '时间范围(yesterday/7d/30d)',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date_range (merchant_id, data_date, time_range),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品数据';

-- ============================================================
-- 19. shop_product_count（商品数量）
-- 代表对象: 阶段二 T2.5.5 商家填写的各状态商品数量
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_product_count (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  total_count INT UNSIGNED DEFAULT NULL COMMENT '全部商品数量',
  on_sale_count INT UNSIGNED DEFAULT NULL COMMENT '售卖中商品数量',
  off_sale_count INT UNSIGNED DEFAULT NULL COMMENT '已下架商品数量',
  audit_count INT UNSIGNED DEFAULT NULL COMMENT '商品审核中数量',
  data_date DATE NOT NULL COMMENT '数据日期',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date (merchant_id, data_date),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品数量';

-- ============================================================
-- 20. shop_health_score（商品信息健康分）
-- 代表对象: 阶段二 T2.5.6 商家填写的店铺信息分分布
-- 关联: merchant(1:N, 弱关联 merchant_id)
-- ============================================================
CREATE TABLE shop_health_score (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  avg_score DECIMAL(5,2) DEFAULT NULL COMMENT '店铺平均信息分',
  score_gte_90_count INT UNSIGNED DEFAULT NULL COMMENT '信息分>=90分商品数量',
  score_78_90_count INT UNSIGNED DEFAULT NULL COMMENT '信息分78-90分商品数量',
  score_60_77_count INT UNSIGNED DEFAULT NULL COMMENT '信息分60-77分商品数量',
  score_lt_60_count INT UNSIGNED DEFAULT NULL COMMENT '信息分<60分商品数量',
  data_date DATE NOT NULL COMMENT '数据日期',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_date (merchant_id, data_date),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商品信息健康分';

-- ============================================================
-- 21. merchant_stage_progress（商家阶段进度表）
-- 代表对象: 商家各阶段的解锁/完成状态，支撑阶段隔离
-- 关联: merchant(N:1, 弱关联 merchant_id)
-- 设计说明: 阶段一(onboarding)全部启用任务完成后，将 setup 行置为 unlocked
--           并记录 unlocked_at；与 merchant.current_stage 配合实现阶段二解锁
-- ============================================================
CREATE TABLE merchant_stage_progress (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  stage_id VARCHAR(32) NOT NULL COMMENT '阶段标识(onboarding=阶段一/shop_setup=阶段二解锁约定)',
  status VARCHAR(16) DEFAULT 'locked' COMMENT 'locked/unlocked/completed',
  unlocked_at DATETIME DEFAULT NULL COMMENT '解锁时间',
  completed_at DATETIME DEFAULT NULL COMMENT '完成时间',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_merchant_stage (merchant_id, stage_id),
  KEY idx_merchant_id (merchant_id),
  KEY idx_stage_id (stage_id),
  KEY idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家阶段进度表';

-- ============================================================
-- 22. ai_analysis_log（AI 经营分析调用日志）
-- 代表对象: 商家 AI 经营分析请求的调用记录（限流/审计）
-- 关联: merchant(N:1, 弱关联 merchant_id)
-- 设计说明: 仅追加不修改；KEY idx_merchant_created 支撑按商家+时间查询与清理。
--           清理建议：保留近 30 天或按商家保留最近 N 条，由运维脚本定期执行
-- ============================================================
CREATE TABLE ai_analysis_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
  type VARCHAR(32) NOT NULL DEFAULT 'analysis' COMMENT '日志类型: analysis=经营分析 / image_optimize=主图优化',
  status VARCHAR(16) NOT NULL COMMENT 'success/failed',
  error_message VARCHAR(255) DEFAULT NULL COMMENT '失败原因（通用文案，不回显密钥）',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_merchant_created (merchant_id, created_at),
  KEY idx_type_merchant_created (type, merchant_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 经营分析调用日志（限流/审计）';

-- ============================================================
-- 23. stage_config（阶段表-后端 Stage 实体映射）
-- 代表对象: 任务的阶段配置（后端 Stage 实体映射表，与 stage 表并存属既有双表问题）
-- 关联: first_level_task(N:1, 弱关联 stageId)
-- 设计说明: 与 stage 表结构一致（含 phase_num），stage_id 唯一；两表收敛为单表前保持并存
-- 变更原因 (v1.4, 2026-09-10, 任务单 #DB-2 K1，用户选方案 A):
--   ORM models/stage_config.py:14 已声明 UniqueConstraint("stage_id", name="uk_stage_id")，
--   但本表 DDL 与 dev 实库均无该键，alembic autogenerate 报全库唯一一项 add_constraint;
--   stage_id 业务上必须唯一(app/services/task.py:83 按 stage_id 归集上级任务分组)。
--   历史迁移 Phase2TaskSeed.ts:43 对新建库已带该键，本次为 schema.sql 与实库对齐补齐。
--   存量库(本地 dev / 生产)升级语句:
--     ALTER TABLE stage_config ADD UNIQUE KEY uk_stage_id (stage_id);
--   实测 dev 库 9 行 / 9 个 distinct stage_id(无重复)，补键不影响存量数据。
-- ============================================================
CREATE TABLE stage_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  title VARCHAR(128) NOT NULL COMMENT '阶段标题',
  description TEXT COMMENT '阶段描述',
  status TINYINT DEFAULT 1 COMMENT '0=禁用 1=启用',
  stage_id VARCHAR(32) NOT NULL COMMENT '阶段唯一标识',
  stage_num INT NOT NULL COMMENT '阶段序号',
  button_text VARCHAR(64) NOT NULL DEFAULT '' COMMENT '按钮文案',
  sort_order INT NOT NULL DEFAULT 0 COMMENT '排序',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  phase_num INT NOT NULL DEFAULT 1 COMMENT '所属大阶段(1=阶段一/2=阶段二)',
  PRIMARY KEY (id),
  UNIQUE KEY uk_stage_id (stage_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='阶段表(Stage实体映射)';
-- ============================================================
-- 24. feedback（商家反馈，M2 反馈闭环）
-- 代表对象: 商家提交的功能建议/使用问题/任务异常/其他；管理端筛选与回复
-- 关联: merchant(N:1, 可空), admin_account(N:1, handler_id 可空)
-- 设计说明: 用户已决策不存截图（不含 images 列）
-- ============================================================
CREATE TABLE feedback (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  merchant_id VARCHAR(64) DEFAULT NULL COMMENT '商家ID(可空)',
  content VARCHAR(1000) NOT NULL COMMENT '反馈内容',
  category VARCHAR(16) NOT NULL DEFAULT '其他' COMMENT '分类:功能建议/使用问题/任务异常/其他',
  status VARCHAR(16) NOT NULL DEFAULT 'pending' COMMENT '状态:pending/processing/resolved',
  admin_reply VARCHAR(1000) DEFAULT NULL COMMENT '管理员回复',
  handler_id BIGINT UNSIGNED DEFAULT NULL COMMENT '处理管理员ID',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '提交时间',
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (id),
  KEY idx_merchant_id (merchant_id),
  KEY idx_status (status),
  KEY idx_category (category),
  KEY idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家反馈表';

-- ============================================================
-- 25. ai_entry_config（AI 分入口配置；密钥加密存储）
-- 代表对象: AI 三入口(analysis / image_optimize / title_optimize)各自的 LLM 配置覆盖
-- 关联: 无外键；entry ∈ {analysis, image_optimize, title_optimize}
-- 设计说明: 一入口一行(uk_entry)；字段为 NULL = 该字段回落 env 同名字段；
--           密钥按用户 2026-09-14 裁决 **全阶段加密**：仅存密文(AES-256-GCM，v1:+base64(nonce‖tag‖ct))
--           与不可逆指纹(sha256(原文) 前 16 位 hex)，**不存在任何明文 key 列**；
--           加密密钥来自 env AI_CONFIG_ENC_KEY(64 位 hex)，密钥材料不落库
-- 变更原因 (v1.7, 2026-09-14, 任务单 #DB-12；方案 dev-docs/任务单/P7-AI-key分入口配置-方案.md v1.1):
--   P7 加密主线定稿后的第一单，仅落地表结构；ORM/服务层/加解密封装/接口归 #PB-21。
--   段号顺延为 25（24 = feedback；v1.6 已有 9→11 跳号历史，不重排以免全文件行号二次位移）。
-- ============================================================
CREATE TABLE ai_entry_config (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry VARCHAR(32) NOT NULL COMMENT '入口标识:analysis/image_optimize/title_optimize',
  enabled TINYINT NOT NULL DEFAULT 1 COMMENT '0=忽略本行(全量回落 env) 1=启用本行',
  api_key_ciphertext VARCHAR(512) DEFAULT NULL COMMENT 'API Key 密文(AES-256-GCM:v1:+base64(nonce‖tag‖ct);NULL=回落 env AI_API_KEY)',
  api_key_fingerprint VARCHAR(32) DEFAULT NULL COMMENT 'API Key 指纹(sha256(原文) 前16位hex;不可逆,仅用于同一性判断)',
  base_url VARCHAR(255) DEFAULT NULL COMMENT 'LLM base_url(NULL=回落 env AI_BASE_URL)',
  model VARCHAR(128) DEFAULT NULL COMMENT '模型名(NULL=回落 env AI_MODEL)',
  timeout_ms INT DEFAULT NULL COMMENT '单次请求超时 ms(NULL=回落 env 各入口超时)',
  max_tokens INT DEFAULT NULL COMMENT '单次最大输出 token(NULL=回落 env 各入口值)',
  daily_limit INT DEFAULT NULL COMMENT '每商家每日成功次数上限(0=不限;NULL=回落 env)',
  updated_by VARCHAR(64) DEFAULT NULL COMMENT '最近修改者 username(留痕)',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (id),
  UNIQUE KEY uk_entry (entry)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 分入口配置(密钥加密存储,缺省字段回落 env)';

-- ============================================================
-- 26. admin_ai_config_audit（AI 配置修改审计）
-- 代表对象: 管理端每次修改 AI 配置的一条审计记录
-- 关联: admin_account(N:1, 弱关联 admin_id)；entry 弱关联 ai_entry_config.entry
-- 设计说明: 密钥类字段只留掩码(old/new_display)、长度(old/new_len)与指纹(old/new_fp)，
--           **绝不落密钥原文与密文**(用户 2026-09-14 裁决)；非密钥字段记原值新旧以追责。
-- ============================================================
CREATE TABLE admin_ai_config_audit (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  entry VARCHAR(32) NOT NULL COMMENT '被修改入口',
  field VARCHAR(32) NOT NULL COMMENT '被修改字段:api_key/base_url/model/timeout_ms/max_tokens/daily_limit/enabled',
  action VARCHAR(16) NOT NULL COMMENT 'update/clear/create',
  old_display VARCHAR(255) DEFAULT NULL COMMENT '旧值展示:密钥=掩码;非密钥=原值;NULL 表示原为回落 env',
  new_display VARCHAR(255) DEFAULT NULL COMMENT '新值展示:同 old_display;NULL 表示清除回落 env',
  old_len INT DEFAULT NULL COMMENT '旧密钥长度(仅 api_key 字段;不落密钥原文与密文)',
  new_len INT DEFAULT NULL COMMENT '新密钥长度(仅 api_key 字段;不落密钥原文与密文)',
  old_fp VARCHAR(32) DEFAULT NULL COMMENT '旧密钥指纹(sha256(原文) 前 16 位 hex;不可逆;仅 api_key 字段)',
  new_fp VARCHAR(32) DEFAULT NULL COMMENT '新密钥指纹(同上)',
  admin_id BIGINT UNSIGNED NOT NULL COMMENT '操作管理员 id',
  admin_username VARCHAR(64) NOT NULL COMMENT '操作管理员用户名(冗余留痕,防账号改名后失联)',
  ip VARCHAR(45) DEFAULT NULL COMMENT '来源 IP(app/core/utils 取真实 IP)',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '修改时间',
  PRIMARY KEY (id),
  KEY idx_entry_created (entry, created_at),
  KEY idx_admin_created (admin_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='AI 配置修改审计(密钥只留掩码/长度/指纹)';

-- ============================================================
-- 27. merchant_login_code（商家登录短信验证码发送/校验审计；频控计数）
-- 代表对象: 一次「发送验证码」请求及其后续校验的留痕(审计 + 频控计数)
-- 关联: merchant(N:1, 弱关联 phone；无外键)
-- 设计说明: 短信改走阿里云 PNVS 短信认证(SendSmsVerifyCode / CheckSmsVerifyCode)，验证码由阿里云生成与校验
--           (ReturnVerifyCode=false，我方不接收明文码) → 本表不再存验证码哈希/盐/失效时间，
--           只作发送与校验审计 + 频控计数(C1~C6 用 COUNT，C8 用 attempts，C10 用校验请求计数)；
--           biz_id/out_id 用于对账与幂等；留存 7 天，由运维 cron 按 created_at 清理(日增有界)
-- 变更原因 (v1.9, 2026-09-16, 任务单 #DB-14: 短信改走 PNVS 短信认证 —— 删除自建方案列 code_hash/code_salt/
--           expires_at，新增 biz_id/out_id，attempts 语义改为「该行校验失败次数(我方兜底闸,防爆破)」；
--           共 8 列；表数与段号不变；v1.8 原文见 git 历史与 #DB-13 交付)
-- ============================================================
CREATE TABLE merchant_login_code (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  phone VARCHAR(20) NOT NULL COMMENT '手机号(11 位国内号;明文存储,日志必须脱敏)',
  biz_id VARCHAR(64) DEFAULT NULL COMMENT '阿里云 SendSmsVerifyCode 返回的业务ID(对账用)',
  out_id VARCHAR(64) DEFAULT NULL COMMENT '我方生成并透传的外部ID(幂等/对账)',
  ip VARCHAR(45) DEFAULT NULL COMMENT '请求来源 IP(app/core/utils 真实 IP,默认不信任 XFF)',
  attempts INT NOT NULL DEFAULT 0 COMMENT '该行校验失败次数(我方兜底闸,防爆破)',
  used_at DATETIME(6) DEFAULT NULL COMMENT '使用/作废时间(NULL=仍可用;非空=已用或已作废)',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '发送时间',
  PRIMARY KEY (id),
  KEY idx_phone_created (phone, created_at),
  KEY idx_ip_created (ip, created_at),
  KEY idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='商家登录短信验证码发送/校验审计与频控计数(PNVS 短信认证;不再存哈希)';

-- ============================================================
-- 28. internal_notify_log（内部通知发送记录；可观测、可手工重试）
-- 代表对象: 一条内部 IM 通知(如「新商家注册」)的发送结果
-- 关联: merchant(N:1, 弱关联 merchant_id；无外键)
-- 设计说明: 与面向商家的 feishu_notification 分表(后者是商家维度 + template_type 枚举 + 48h 频控，
--           塞内部通知会污染商家通知语义)；V1 不做自动重试(自动重试需常驻 worker → 无界运行面)，
--           仅保留手工重放入口；error_message 不含密钥与完整手机号
--           去重键 dedupe_key 取值口径: merchant_registered = merchant_id；jd 重复登记 = 'jd:<jd_merchant_id>'；
--           去重查询 idx_event_dedupe(event_type, dedupe_key, created_at) 走 24h 窗口(status='sent')
-- 变更原因 (v1.8, 2026-09-16, 任务单 #PL-4 / #DB-13；方案 dev-docs/任务单/phone-sms-login-design.md §七)
--           (v1.10, 2026-09-16, 任务单 #DB-19 / #PL-7: 就地补 dedupe_key 列与 idx_event_dedupe 索引，
--            支撑『京麦商家ID重复登记』通知的 24h 去重；既有 merchant_registered 幂等判据不变)
-- ============================================================
CREATE TABLE internal_notify_log (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  channel VARCHAR(32) NOT NULL COMMENT '通道:feishu_im',
  event_type VARCHAR(32) NOT NULL COMMENT '业务事件:merchant_registered/jd_duplicate_registration(列宽 32,超长名触 1406)',
  merchant_id VARCHAR(64) DEFAULT NULL COMMENT '触发事件的商家(无外键,弱关联)',
  target_type VARCHAR(16) NOT NULL COMMENT '接收方类型:open_id/user_id/email/chat_id',
  target VARCHAR(128) NOT NULL COMMENT '接收方标识(receive_id;不落密钥材料)',
  status VARCHAR(16) NOT NULL COMMENT 'sent/failed',
  error_message VARCHAR(255) DEFAULT NULL COMMENT '失败原因(不含密钥与完整手机号)',
  dedupe_key VARCHAR(128) DEFAULT NULL COMMENT '去重键:merchant_registered=merchant_id;jd 重复登记=jd:<jd_merchant_id>',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '发送时间',
  PRIMARY KEY (id),
  KEY idx_event_created (event_type, created_at),
  KEY idx_merchant (merchant_id),
  KEY idx_event_dedupe (event_type, dedupe_key, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='内部通知发送记录(可观测/可手工重试)';

-- ============================================================
-- 29. captcha_daily_counter（人机校验：阿里云图形认证服务端二次校验每日调用计数；成本闸 C7）
-- 代表对象: 某自然日的人机校验（阿里云图形认证 · 官方 HTTP 服务端二次校验）调用次数（全站）
-- 关联: 无(独立计数表，横向不关联业务表)
-- 设计说明: G-4 裁定：**不建** append-only 的 login_captcha_call_log，改为按天聚合的计数表；
--           靠 INSERT ... ON DUPLICATE KEY UPDATE used = used + 1 原子自增；1 行/天、天然有界、无需清理任务；
--           达 LOGIN_CAPTCHA_DAILY_MAX(默认 3000) 即 503 + 告警(80% 时 warning)
-- 变更原因 (v1.8, 2026-09-16, 任务单 #PL-4 / #DB-13；方案 dev-docs/任务单/phone-sms-login-design.md §五 C7 + §十四 G-4)
-- ============================================================
CREATE TABLE captcha_daily_counter (
  day DATE NOT NULL COMMENT '统计自然日(Asia/Shanghai;主键,1 行/天)',
  used INT NOT NULL DEFAULT 0 COMMENT '当日人机校验(图形认证服务端二次校验)调用次数(成本闸 C7 计数)',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  updated_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6) COMMENT '更新时间',
  PRIMARY KEY (day)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='人机校验(图形认证服务端二次校验)每日调用计数(成本闸;1 行/天,天然有界)';

-- ============================================================
-- 30. merchant_binding_group（账号绑定组：1 个京麦商家ID ↔ N 个商家账号；只共享进度）
-- 代表对象: 一个被运营确认「同一店铺」的账号集合
-- 关联: merchant_binding_member(N:1)；jd_merchant_id 弱关联 merchant.jd_merchant_id(无外键)
-- 设计说明: 「一个 jd_merchant_id 只能有一个活跃组」由 uk_group_active(jd_merchant_id, active_key) 保证：
--           活跃组 active_key=1；组关闭时置 NULL(MySQL 唯一索引允许多个 NULL) → 可保留多条历史组行。
--           维护规则: 活跃组必须 >= 2 名活跃成员；解绑后剩 < 2 名时同一事务关闭组(active_key→NULL + closed_at/by)。
--           绑定关系只由管理后台运营手工创建；merchant.jd_merchant_id 仍表示「账号自己登记的事实」，解绑不清空。
-- 变更原因 (v1.10, 2026-09-16, 任务单 #DB-19 / #PL-7；方案 dev-docs/任务单/merchant-account-binding-design.md §4.2)
-- ============================================================
CREATE TABLE merchant_binding_group (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  jd_merchant_id VARCHAR(64) NOT NULL COMMENT '京麦商家ID(组键;取自发起绑定的商家登记值)',
  active_key TINYINT DEFAULT 1 COMMENT '活跃标记:1=活跃;NULL=已关闭(允许多 NULL,保留历史)',
  created_by VARCHAR(64) NOT NULL COMMENT '创建人(管理员 username;运营手工绑定)',
  created_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '创建时间',
  closed_at DATETIME(6) DEFAULT NULL COMMENT '关闭时间(活跃成员 < 2 时)',
  closed_by VARCHAR(64) DEFAULT NULL COMMENT '关闭操作人(username)',
  PRIMARY KEY (id),
  UNIQUE KEY uk_group_active (jd_merchant_id, active_key),
  KEY idx_jd_merchant_id (jd_merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='账号绑定组(同店账号;只共享进度)';

-- ============================================================
-- 31. merchant_binding_member（绑定组成员：账号 ↔ 组；解绑=行保留 + active_key 置 NULL）
-- 代表对象: 一条「账号属于某个绑定组」的关系(含解绑后的历史行)
-- 关联: merchant_binding_group(N:1)；merchant_id 弱关联 merchant.merchant_id(无外键)
-- 设计说明: 「一个账号只能在一个活跃组」由 uk_member_active(merchant_id, active_key) 保证；
--           解绑不删行: active_key 置 NULL + released_at/released_by 留痕(该行即审计)；
--           进度共享为**读取期并集**，本表不复制/不改写任何进度行；解绑后各自回落到「只看自己」。
-- 变更原因 (v1.10, 2026-09-16, 任务单 #DB-19 / #PL-7；方案 dev-docs/任务单/merchant-account-binding-design.md §4.2)
-- ============================================================
CREATE TABLE merchant_binding_member (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  group_id BIGINT UNSIGNED NOT NULL COMMENT '所属绑定组(merchant_binding_group.id)',
  merchant_id VARCHAR(64) NOT NULL COMMENT '商家账号ID(merchant.merchant_id)',
  active_key TINYINT DEFAULT 1 COMMENT '活跃标记:1=在组;NULL=已解绑(允许多 NULL,保留历史)',
  bound_by VARCHAR(64) NOT NULL COMMENT '绑定操作人(管理员 username)',
  bound_at DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) COMMENT '绑定时间',
  released_at DATETIME(6) DEFAULT NULL COMMENT '解绑时间',
  released_by VARCHAR(64) DEFAULT NULL COMMENT '解绑操作人(username)',
  PRIMARY KEY (id),
  UNIQUE KEY uk_member_active (merchant_id, active_key),
  KEY idx_group_active (group_id, active_key),
  KEY idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci COMMENT='绑定组成员(解绑保留行,active_key 置 NULL)';
