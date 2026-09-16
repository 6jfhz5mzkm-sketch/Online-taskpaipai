#!/usr/bin/env node
/**
 * 飞书 Wiki 页面数据拉取脚本
 * 用于读取 Wiki 页面中嵌入的多维表格数据
 */

const APP_ID = process.env.FEISHU_APP_ID;
const APP_SECRET = process.env.FEISHU_APP_SECRET;
if (!APP_ID || !APP_SECRET) {
  console.error('缺少环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET（飞书自建应用凭证）。');
  console.error('请在本地环境中配置后再运行，例如：FEISHU_APP_ID=cli_xxx FEISHU_APP_SECRET=xxx node scripts/xxx.js …');
  process.exit(1);
}
const BASE_URL = 'https://open.feishu.cn/open-apis';

async function getTenantToken() {
  const res = await fetch(`${BASE_URL}/auth/v3/tenant_access_token/internal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ app_id: APP_ID, app_secret: APP_SECRET }),
  });
  const data = await res.json();
  if (data.code !== 0) throw new Error(`token failed: ${data.msg}`);
  return data.tenant_access_token;
}

async function getWikiNode(token, nodeToken) {
  const res = await fetch(`${BASE_URL}/wiki/v2/spaces/get_node?token=${nodeToken}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (data.code !== 0) throw new Error(`wiki node failed: ${data.msg}`);
  return data.data.node;
}

async function listBitableTables(token, appToken) {
  const res = await fetch(`${BASE_URL}/bitable/v1/apps/${appToken}/tables`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  if (data.code !== 0) throw new Error(`list tables failed: ${data.msg}`);
  return data.data.items;
}

async function readBitableRecords(token, appToken, tableId) {
  let allRecords = [];
  let pageToken = undefined;
  let page = 1;
  do {
    const url = new URL(`${BASE_URL}/bitable/v1/apps/${appToken}/tables/${tableId}/records`);
    url.searchParams.set('page_size', '500');
    if (pageToken) url.searchParams.set('page_token', pageToken);
    const res = await fetch(url.toString(), {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json();
    if (data.code !== 0) throw new Error(`read records failed: ${data.msg}`);
    const records = data.data.items || [];
    allRecords = allRecords.concat(records);
    pageToken = data.data.has_more ? data.data.page_token : undefined;
    console.error(`  page ${page}: ${records.length} records`);
    page++;
  } while (pageToken);
  return allRecords;
}

function flattenRecords(records) {
  return records.map((r) => {
    const row = { _record_id: r.record_id };
    for (const [key, value] of Object.entries(r.fields)) {
      if (Array.isArray(value)) {
        row[key] = value.map((v) => {
          if (typeof v === 'string') return v;
          if (v && v.text) return v.text;
          if (v && v.name) return v.name;
          return JSON.stringify(v);
        }).join(', ');
      } else if (value && typeof value === 'object') {
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

async function main() {
  const [,, command, ...args] = process.argv;
  if (!command) {
    console.log(`Usage:
  node scripts/feishu-wiki.js info <wiki_node_token>
  node scripts/feishu-wiki.js tables <wiki_node_token>
  node scripts/feishu-wiki.js read <wiki_node_token> <table_id>
  node scripts/feishu-wiki.js export <wiki_node_token> <table_id> [output.json]`);
    process.exit(1);
  }

  console.error('Getting access token...');
  const token = await getTenantToken();
  console.error('OK token obtained\n');

  if (command === 'info') {
    const [nodeToken] = args;
    if (!nodeToken) { console.error('Need wiki_node_token'); process.exit(1); }
    console.error(`Getting wiki node: ${nodeToken}...`);
    const node = await getWikiNode(token, nodeToken);
    console.log(JSON.stringify(node, null, 2));
    console.error(`\nType: ${node.obj_type}, Title: ${node.title}`);
    console.error(`space_id: ${node.space_id}`);
    console.error(`obj_token: ${node.obj_token}`);
  }

  if (command === 'tables') {
    const [nodeToken] = args;
    if (!nodeToken) { console.error('Need wiki_node_token'); process.exit(1); }
    console.error(`Getting wiki node info...`);
    const node = await getWikiNode(token, nodeToken);
    console.error(`Node: ${node.title} (type: ${node.obj_type})`);
    if (node.obj_type === 'bitable') {
      const appToken = node.obj_token;
      console.error(`\nListing bitable tables...`);
      const tables = await listBitableTables(token, appToken);
      console.log(JSON.stringify(tables, null, 2));
      console.error(`\nTotal: ${tables.length} tables`);
    } else {
      console.error(`\nNot a bitable, type: ${node.obj_type}`);
    }
  }

  if (command === 'read' || command === 'export') {
    const [nodeToken, tableId, outputFile] = args;
    if (!nodeToken || !tableId) { console.error('Need wiki_node_token and table_id'); process.exit(1); }
    console.error(`Getting wiki node info...`);
    const node = await getWikiNode(token, nodeToken);
    const appToken = node.obj_token;
    console.error(`bitable app_token: ${appToken}`);
    console.error(`\nReading table ${tableId}...`);
    const records = await readBitableRecords(token, appToken, tableId);
    const flat = flattenRecords(records);
    console.error(`\nTotal: ${flat.length} records\n`);
    const output = JSON.stringify(flat, null, 2);
    if (command === 'export' && outputFile) {
      require('fs').writeFileSync(outputFile, output, 'utf-8');
      console.error(`Exported to ${outputFile}`);
    } else {
      console.log(output);
    }
  }
}

main().catch((err) => {
  console.error('Error:', err.message);
  process.exit(1);
});