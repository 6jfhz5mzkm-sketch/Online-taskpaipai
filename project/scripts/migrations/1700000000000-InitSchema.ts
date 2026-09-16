import { MigrationInterface, QueryRunner } from 'typeorm';

export class InitSchema1700000000000 implements MigrationInterface {
  name = 'InitSchema1700000000000';

  async up(queryRunner: QueryRunner): Promise<void> {
    // 1. merchant
    await queryRunner.query(`
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
        status TINYINT DEFAULT 1 COMMENT '0=禁用 1=正常 2=已退出',
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
        last_active_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后活跃',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
        PRIMARY KEY (id),
        UNIQUE KEY uk_merchant_id (merchant_id),
        UNIQUE KEY uk_feishu_open_id (feishu_open_id),
        KEY idx_feishu_user_id (feishu_user_id),
        KEY idx_status (status),
        KEY idx_deleted_at (deleted_at)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商家表'
    `);

    // 2. category
    await queryRunner.query(`
      CREATE TABLE category (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        parent_id BIGINT UNSIGNED DEFAULT 0 COMMENT '父类目ID(0=一级)',
        name VARCHAR(128) NOT NULL COMMENT '类目名称',
        sort_order SMALLINT DEFAULT 0 COMMENT '排序',
        is_active TINYINT DEFAULT 1 COMMENT '是否启用',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
        PRIMARY KEY (id),
        KEY idx_parent_level (parent_id),
        KEY idx_deleted_at (deleted_at)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商品类目表'
    `);

    // 3. fee_config
    await queryRunner.query(`
      CREATE TABLE fee_config (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        category_id BIGINT UNSIGNED NOT NULL COMMENT '关联二级类目',
        operation_rate DECIMAL(5,2) NOT NULL COMMENT '运营支持服务费率(%)',
        transaction_rate DECIMAL(5,2) NOT NULL COMMENT '交易服务费率(%)',
        deposit_gmv_lt_5w INT UNSIGNED DEFAULT 0 COMMENT '保证金-GMV<5万(元)',
        deposit_gmv_5w_10w INT UNSIGNED DEFAULT 0 COMMENT '保证金-GMV 5-10万(元)',
        deposit_gmv_10w_30w INT UNSIGNED DEFAULT 0 COMMENT '保证金-GMV 10-30万(元)',
        deposit_gmv_gte_30w INT UNSIGNED DEFAULT 0 COMMENT '保证金-GMV>=30万(元)',
        is_active TINYINT DEFAULT 1 COMMENT '是否启用',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
        PRIMARY KEY (id),
        UNIQUE KEY uk_category_id (category_id),
        KEY idx_deleted_at (deleted_at),
        CONSTRAINT fk_fee_config_category
          FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='资费配置表'
    `);

    // 4. fee_brand_override
    await queryRunner.query(`
      CREATE TABLE fee_brand_override (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        category_id BIGINT UNSIGNED NOT NULL COMMENT '关联二级类目',
        brand_name VARCHAR(128) NOT NULL COMMENT '品牌名称',
        operation_rate DECIMAL(5,2) NOT NULL COMMENT '运营支持服务费率-覆盖值(%)',
        transaction_rate DECIMAL(5,2) NOT NULL COMMENT '交易服务费率-覆盖值(%)',
        is_active TINYINT DEFAULT 1 COMMENT '是否启用',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
        PRIMARY KEY (id),
        KEY idx_brand_name (brand_name),
        UNIQUE KEY uk_category_brand (category_id, brand_name),
        KEY idx_deleted_at (deleted_at),
        CONSTRAINT fk_fee_brand_category
          FOREIGN KEY (category_id) REFERENCES category (id) ON DELETE CASCADE
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='品牌资费覆盖表'
    `);

    // 5. merchant_category
    await queryRunner.query(`
      CREATE TABLE merchant_category (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        merchant_id VARCHAR(64) NOT NULL COMMENT '商家ID',
        category_id BIGINT UNSIGNED NOT NULL COMMENT '类目ID',
        is_primary TINYINT DEFAULT 0 COMMENT '是否主营类目',
        selected_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '选择时间',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        deleted_at DATETIME DEFAULT NULL COMMENT '软删除时间',
        PRIMARY KEY (id),
        UNIQUE KEY uk_merchant_category (merchant_id, category_id),
        KEY idx_merchant_id (merchant_id),
        KEY idx_deleted_at (deleted_at)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商家经营类目表'
    `);

    // 6. event_log
    await queryRunner.query(`
      CREATE TABLE event_log (
        id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
        merchant_id VARCHAR(64) DEFAULT NULL COMMENT '商家ID(未登录为空)',
        event_type VARCHAR(64) NOT NULL COMMENT '事件类型',
        page_name VARCHAR(128) DEFAULT NULL COMMENT '页面名称',
        task_key VARCHAR(32) DEFAULT NULL COMMENT '关联任务(弱关联)',
        stage_key VARCHAR(32) DEFAULT NULL COMMENT '关联阶段(弱关联)',
        element VARCHAR(128) DEFAULT NULL COMMENT '交互元素标识',
        meta JSON DEFAULT '{}' COMMENT '扩展数据',
        ip VARCHAR(45) DEFAULT NULL COMMENT '客户端IP',
        user_agent VARCHAR(512) DEFAULT NULL COMMENT 'UA信息',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '事件时间',
        PRIMARY KEY (id),
        KEY idx_merchant_id (merchant_id),
        KEY idx_event_type (event_type),
        KEY idx_created_at (created_at),
        KEY idx_page_name (page_name),
        KEY idx_task_key (task_key)
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='埋点事件表'
    `);

    // 7. feishu_notification
    await queryRunner.query(`
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
      ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='飞书通知表'
    `);
  }

  async down(queryRunner: QueryRunner): Promise<void> {
    await queryRunner.query('DROP TABLE IF EXISTS feishu_notification');
    await queryRunner.query('DROP TABLE IF EXISTS event_log');
    await queryRunner.query('DROP TABLE IF EXISTS merchant_category');
    await queryRunner.query('DROP TABLE IF EXISTS fee_brand_override');
    await queryRunner.query('DROP TABLE IF EXISTS fee_config');
    await queryRunner.query('DROP TABLE IF EXISTS category');
    await queryRunner.query('DROP TABLE IF EXISTS merchant');
  }
}
