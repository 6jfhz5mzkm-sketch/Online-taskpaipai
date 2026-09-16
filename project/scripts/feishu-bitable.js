#!/usr/bin/env node
/**
 * άȡű
 * 
 * ÷
 *   node scripts/feishu-bitable.js list-tables <app_token>
 *   node scripts/feishu-bitable.js read <app_token> <table_id>
 *   node scripts/feishu-bitable.js export <app_token> <table_id> [output.json]
 */

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
if (!APP_ID || !APP_SECRET) {
  console.error('缺少环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET（飞书自建应用凭证）。');
  console.error('请在本地环境中配置后再运行，例如：FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx node scripts/xxx.js …');
  process.exit(1);
}
const BASE_URL = 'https://open.feishu.cn/open-apis';

// ============================================================
// 1. ȡ tenant_access_token
// ============================================================
async function getTenantToken() {
  const res = await fetch(`${BASE_URL}/auth/v3/tenant_access_token/internal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET }),
  });
  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`ȡ token ʧ: ${data.msg}`);
  }
  return data.tenant_access_token;
}

// ============================================================
// 2. гάеݱ
// ============================================================
async function listTables(token, appToken) {
  const res = await fetch(`${BASE_URL}/bitable/v1/apps/${appToken}/tables`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (data.code !== 0) {
    throw new Error(`гݱʧ: ${data.msg}`);
  }
  return data.data.items;
}

// ============================================================
// 3. ȡݱ¼Զҳ
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
      throw new Error(`ȡ¼ʧ: ${data.msg}`);
    }

    const records = data.data.items || [];
    allRecords = allRecords.concat(records);
    pageToken = data.data.has_more ? data.data.page_token : undefined;
    console.error(`   ${page} ҳ: ${records.length} `);
    page++;
  } while (pageToken);

  return allRecords;
}

// ============================================================
// 4. ʽ¼Ϊƽ
// ============================================================
function flattenRecords(records) {
  return records.map((r) => {
    const row = { _record_id: r.record_id };
    for (const [key, value] of Object.entries(r.fields)) {
      // άֵֶǸͣͳһȡı
      if (Array.isArray(value)) {
        // ѡ / ı
        row[key] = value
          .map((v) => {
            if (typeof v === 'string') return v;
            if (v && v.text) return v.text;
            if (v && v.name) return v.name;
            return JSON.stringify(v);
          })
          .join(', ');
      } else if (value && typeof value === 'object') {
        // ѡ /  / Ա
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
// 
// ============================================================
async function main() {
  const [,, command, appToken, tableId, outputFile] = process.argv;

  if (!command || !appToken) {
    console.log(`
÷
  node scripts/feishu-bitable.js list-tables <app_token>
  node scripts/feishu-bitable.js read <app_token> <table_id>
  node scripts/feishu-bitable.js export <app_token> <table_id> [output.json]

ȡ app_token  table_id
  򿪶άURL ʽΪ
  https://xxx.feishu.cn/base/<app_token>?table=<table_id>
   app_token  base/ Ĳ֣table_id  ?table= ֵ
`);
    process.exit(1);
  }

  console.error('ڻȡ access token...');
  const token = await getTenantToken();
  console.error('? token ȡɹ\n');

  if (command === 'list-tables') {
    console.error(`г ${appToken} µݱ...`);
    const tables = await listTables(token, appToken);
    console.log(JSON.stringify(tables, null, 2));
    console.error(`\n?  ${tables.length} ݱ`);
  }

  if (command === 'read' || command === 'export') {
    if (!tableId) {
      console.error(': read/export Ҫ table_id ');
      process.exit(1);
    }
    console.error(`ڶȡ ${appToken} / ${tableId} ...`);
    const records = await readRecords(token, appToken, tableId);
    const flat = flattenRecords(records);
    console.error(`\n?  ${flat.length} ¼\n`);

    const output = JSON.stringify(flat, null, 2);

    if (command === 'export' && outputFile) {
      const fs = require('fs');
      fs.writeFileSync(outputFile, output, 'utf-8');
      console.error(`? ѵ ${outputFile}`);
    } else {
      console.log(output);
    }
  }
}

main().catch((err) => {
  console.error(':', err.message);
  process.exit(1);
});