#!/usr/bin/env node
/**
 * 飞书多维表格数据拉取脚本
 * 
 * 用法：
 *   node scripts/feishu-bitable.js list-tables <app_token>
 *   node scripts/feishu-bitable.js read <app_token> <table_id>
 *   node scripts/feishu-bitable.js export <app_token> <table_id> [output.json]
 * 环境变量（缺失即报错退出，无内置默认值）：
 *   FEISHU_APP_ID       飞书应用 App ID
 *   FEISHU_APP_SECRET   飞书应用 App Secret（仅本地配置，禁止写入仓库）
 */

/** 飞书应用凭证：必须来自环境变量，禁止硬编码（AGENTS.md §十） */
const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
if (!APP_ID || !APP_SECRET) {
  console.error('缺少飞书应用凭证：需在本地环境配置 FEISHU_APP_ID 与 FEISHU_APP_SECRET 后重试。');
  console.error('用法示例：FEISHU_APP_ID=<app_id> FEISHU_APP_SECRET=<app_secret> node scripts/feishu-bitable.js list-tables <app_token>');
  process.exit(1);
}
const BASE_URL = 'https://open.feishu.cn/open-apis';

// ============================================================
// 1. 获取 tenant_access_token
// ============================================================
async function getTenantToken() {
  const res = await fetch(`${BASE_URL}/auth/v3/tenant_access_token/internal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET }),
  });
  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`获取 token 失败: ${data.msg}`);
  }
  return data.tenant_access_token;
}

// ============================================================
// 2. 列出多维表格中的所有数据表
// ============================================================
async function listTables(token, appToken) {
  const res = await fetch(`${BASE_URL}/bitable/v1/apps/${appToken}/tables`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`列出数据表失败: ${data.msg}`);
  }
  return data.data.items;
}

// ============================================================
// 3. 读取数据表记录（自动分页）
// ============================================================
async function readRecords(token, appToken, tableId) {
  let allRecords = [];
  let pageToken = undefined;
  let page = 1;

  do {
    const url = new URL(`${BASE_URL}/bitable/v1/apps/${appToken}/tables/${tableId}/records`);
    url.searchParams.set('page_size', '500');
    if (pageToken) {
      url.searchParams.set('page_token', pageToken);
    }

    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();

    if (data.code !== 0) {
      throw new Error(`读取记录失败: ${data.msg}`);
    }

    const records = data.data.items || [];
    allRecords = allRecords.concat(records);
    pageToken = data.data.has_more ? data.data.page_token : undefined;
    console.error(`  第 ${page} 页: ${records.length} 条`);
    page++;
  } while (pageToken);

  return allRecords;
}

// ============================================================
// 4. 格式化记录为扁平对象
// ============================================================
function flattenRecords(records) {
  return records.map((r) => {
    const row = { _record_id: r.record_id };
    for (const [key, value] of Object.entries(r.fields)) {
      // 飞书多维表格的字段值可能是各种类型，这里统一提取文本
      if (Array.isArray(value)) {
        // 多选 / 文本数组
        row[key] = value
          .map((v) => {
            if (typeof v === 'string') return v;
            if (v && v.text) return v.text;
            if (v && v.name) return v.name;
            return JSON.stringify(v);
          })
          .join(', ');
      } else if (value && typeof value === 'object') {
        // 单选 / 日期 / 人员等
        if (value.text) row[key] = value.text;
        else if (value.name) row[key] = value.name;
        else if (value.value) row[key] = value.value;
        else row[key] = JSON.stringify(value);
      } else {
        row[key] = value;
      }
    }
    return row;
  });
}

// ============================================================
// 主流程
// ============================================================
async function main() {
  const [,, command, appToken, tableId, outputFile] = process.argv;

  if (!command || !appToken) {
    console.log(`
用法：
  node scripts/feishu-bitable.js list-tables <app_token>
  node scripts/feishu-bitable.js read <app_token> <table_id>
  node scripts/feishu-bitable.js export <app_token> <table_id> [output.json]

获取 app_token 和 table_id：
  打开多维表格，URL 格式为：
  https://xxx.feishu.cn/base/<app_token>?table=<table_id>
  其中 app_token 是 base/ 后面的部分，table_id 是 ?table= 后面的值
`);
    process.exit(1);
  }

  console.error('正在获取飞书 access token...');
  const token = await getTenantToken();
  console.error('? token 获取成功\n');

  if (command === 'list-tables') {
    console.error(`正在列出 ${appToken} 下的数据表...`);
    const tables = await listTables(token, appToken);
    console.log(JSON.stringify(tables, null, 2));
    console.error(`\n? 共 ${tables.length} 张数据表`);
  }

  if (command === 'read' || command === 'export') {
    if (!tableId) {
      console.error('错误: read/export 需要 table_id 参数');
      process.exit(1);
    }
    console.error(`正在读取 ${appToken} / ${tableId} ...`);
    const records = await readRecords(token, appToken, tableId);
    const flat = flattenRecords(records);
    console.error(`\n? 共 ${flat.length} 条记录\n`);

    const output = JSON.stringify(flat, null, 2);

    if (command === 'export' && outputFile) {
      const fs = require('fs');
      fs.writeFileSync(outputFile, output, 'utf-8');
      console.error(`? 已导出到 ${outputFile}`);
    } else {
      console.log(output);
    }
  }
}

main().catch((err) => {
  console.error('错误:', err.message);
  process.exit(1);
});
