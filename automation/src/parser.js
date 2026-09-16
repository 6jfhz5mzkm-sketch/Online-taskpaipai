
// 规则页解析：在页面浏览器上下文内运行 DOM 表格网格化解析
// 处理 rowspan/colspan，按表头关键字识别列，输出结构化行。
// 本文件导出可被 page.evaluate 调用的函数，以及纯函数（便于单测）。

// ---- 表格网格化：把带 rowspan/colspan 的表展开成扁平 2D 网格 ----
function expandTable(tableEl) {
  const grid = [];
  const occupied = {}; // key = row_col -> true
  const rows = tableEl.querySelectorAll('tr');
  for (let r = 0; r < rows.length; r++) {
    const cells = [...rows[r].querySelectorAll('th,td')];
    if (grid.length <= r) grid.push([]);
    let col = 0;
    for (const cell of cells) {
      // 找到本行下一个空位
      while (occupied[r + '_' + col]) col++;
      const text = (cell.innerText || cell.textContent || '').trim();
      const rowspan = Math.max(1, parseInt(cell.getAttribute('rowspan') || '1', 10));
      const colspan = Math.max(1, parseInt(cell.getAttribute('colspan') || '1', 10));
      for (let rr = r; rr < r + rowspan; rr++) {
        if (grid.length <= rr) grid.push([]);
        for (let cc = col; cc < col + colspan; cc++) {
          grid[rr][cc] = text;
          if (rr !== r || cc !== col) occupied[rr + '_' + cc] = true;
        }
      }
      occupied[r + '_' + col] = true;
      col += colspan;
    }
  }
  return grid.filter(row => row.length > 0);
}

// ---- 识别表头列索引 ----
function findHeaderIndex(grid, tableKind) {
  // 在表格前 6 行内找表头行
  for (let r = 0; r < Math.min(6, grid.length); r++) {
    const row = grid[r];
    const joined = row.join('|');
    if (tableKind === 'rule' && /运营支持服务费率|交易服务费率/.test(joined)) {
      // 返回各关键字列索引
      const idx = {
        一级类目: row.findIndex(c => /一级类目|^类目$/.test(c)),
        二级类目: row.findIndex(c => /二级类目/.test(c)),
        三级类目: row.findIndex(c => /三级类目/.test(c)),
        四级类目: row.findIndex(c => /四级类目/.test(c)),
        运营费率: row.findIndex(c => /运营支持服务费率/.test(c)),
        交易费率: row.findIndex(c => /交易服务费率/.test(c)),
      };
      // 保证金 GMV 档位列：找到含 GMV 或金额的列
      const gmvs = [];
      for (let c = 0; c < row.length; c++) {
        if (/GMV|5万|10万|30万/.test(row[c]) && !/费率|服务费/.test(row[c])) gmvs.push(c);
      }
      idx.gmvs = gmvs;
      return { rowIndex: r, ...idx };
    }
    if (tableKind === 'brand' && /品牌名称|品牌ID/.test(joined)) {
      const idx = {
        一级类目: row.findIndex(c => /一级类目/.test(c)),
        二级类目: row.findIndex(c => /二级类目/.test(c)),
        三级类目: row.findIndex(c => /三级类目/.test(c)),
        四级类目: row.findIndex(c => /四级类目/.test(c)),
        品牌名称: row.findIndex(c => /品牌名称/.test(c)),
        品牌ID: row.findIndex(c => /品牌ID/.test(c)),
        运营费率: row.findIndex(c => /运营支持服务费率/.test(c)),
        交易费率: row.findIndex(c => /交易服务费率/.test(c)),
      };
      return { rowIndex: r, ...idx };
    }
  }
  return null;
}

// ---- 页面上下文入口：解析所有表格 ----
export async function parsePage(page) {
  const result = await page.evaluate(() => {
    const text = (t) => (t || '').replace(/[\u3000\s]/g,'').replace(',', '');
    function expandTable(tableEl) { /* 同上 */ }
    // 内联实现（evaluate 内无法引用外部函数）
    const gridOf = (tableEl) => {
      const grid = [];
      const occupied = {};
      const rows = tableEl.querySelectorAll('tr');
      for (let r = 0; r < rows.length; r++) {
        const cells = [...rows[r].querySelectorAll('th,td')];
        if (grid.length <= r) grid.push([]);
        let col = 0;
        for (const cell of cells) {
          while (occupied[r + '_' + col]) col++;
          const t = (cell.innerText || cell.textContent || '').trim();
          const rs = Math.max(1, parseInt(cell.getAttribute('rowspan') || '1', 10));
          const cs = Math.max(1, parseInt(cell.getAttribute('colspan') || '1', 10));
          for (let rr = r; rr < r + rs; rr++) {
            if (grid.length <= rr) grid.push([]);
            for (let cc = col; cc < col + cs; cc++) {
              grid[rr][cc] = t;
              if (rr !== r || cc !== col) occupied[rr + '_' + cc] = true;
            }
          }
          occupied[r + '_' + col] = true;
          col += cs;
        }
      }
      return grid.filter(row => row.length > 0);
    };
    const tables = [...document.querySelectorAll('table')];
    const ruleTables = [];
    const brandTables = [];
    const grids = tables.map(tb => ({ el: tb, grid: gridOf(tb) }));
    for (const { grid } of grids) {
      const joinedAny = grid.slice(0,6).map(r=>r.join('|')).join('\n');
      if (/运营支持服务费率/.test(joinedAny) && /一级类目/.test(joinedAny) && !/品牌名称/.test(joinedAny)) {
        ruleTables.push(grid);
      } else if (/品牌名称/.test(joinedAny) && /品牌ID/.test(joinedAny)) {
        brandTables.push(grid);
      }
    }
    function findHeader(grid, kind) {
      for (let r = 0; r < Math.min(6, grid.length); r++) {
        const row = grid[r]; const joined = row.join('|');
        if (kind === 'rule' && /运营支持服务费率/.test(joined)) {
          const gmvs = [];
          for (let c=0;c<row.length;c++) if (/GMV|5万|10万|30万/.test(row[c]) && !/费率|服务费/.test(row[c])) gmvs.push(c);
          return { rowIndex: r,
            一级类目: row.findIndex(c=>/一级类目/.test(c)),
            二级类目: row.findIndex(c=>/二级类目/.test(c)),
            三级类目: row.findIndex(c=>/三级类目/.test(c)),
            四级类目: row.findIndex(c=>/四级类目/.test(c)),
            运营费率: row.findIndex(c=>/运营支持服务费率/.test(c)),
            交易费率: row.findIndex(c=>/交易服务费率/.test(c)),
            gmvs };
        }
        if (kind === 'brand' && /品牌名称/.test(joined)) {
          return { rowIndex: r,
            一级类目: row.findIndex(c=>/一级类目/.test(c)),
            二级类目: row.findIndex(c=>/二级类目/.test(c)),
            三级类目: row.findIndex(c=>/三级类目/.test(c)),
            四级类目: row.findIndex(c=>/四级类目/.test(c)),
            品牌名称: row.findIndex(c=>/品牌名称/.test(c)),
            品牌ID: row.findIndex(c=>/品牌ID/.test(c)),
            运营费率: row.findIndex(c=>/运营支持服务费率/.test(c)),
            交易费率: row.findIndex(c=>/交易服务费率/.test(c)) };
        }
      }
      return null;
    }
    const rate = (s) => { const m = (s||'').match(/([0-9.]+)%/); return m ? m[1] : null; };
    const money = (s) => { const v = (s||'').replace(/[^0-9.]/g,''); return v===''?null:Number(v); };

    // 解析资费一览表（位置化取值：费率=行内最后两个百分比；保证金=费率前最后 4 个数字）
    const parseRate = (x) => { const m = (x||'').match(/([0-9.]+)%/); return m ? m[1] : null; };
    const parseMoney = (x) => { const v = (x||'').replace(/[,，]/g,'').replace(/[^0-9.]/g,''); return v===''?null:Number(v); };
    const ruleRows = [];
    for (const grid of ruleTables) {
      const h = findHeader(grid, 'rule');
      if (!h) continue;
      for (let r = h.rowIndex + 1; r < grid.length; r++) {
        const row = grid[r];
        const get = (i) => (i>=0 && i<row.length ? row[i] : null);
        const lv1 = get(h.一级类目)||'', lv2 = get(h.二级类目)||'', lv3 = get(h.三级类目)||'', lv4 = get(h.四级类目)||'';
        if (!lv1 && !lv2 && !lv3 && !lv4) continue;
        // 百分比列索引
        const pctIdx = []; for (let c=0;c<row.length;c++) if (/%(?!.*%)/.test(row[c]) && /[0-9]/.test(row[c])) pctIdx.push(c);
        const opIdx = pctIdx.length>=2 ? pctIdx[pctIdx.length-2] : -1;
        const txIdx = pctIdx.length>=1 ? pctIdx[pctIdx.length-1] : -1;
        const opRate = opIdx>=0 ? parseRate(row[opIdx]) : null;
        const txRate = txIdx>=0 ? parseRate(row[txIdx]) : null;
        const allNums = [];
        for (let c=0;c<opIdx;c++){ const m=parseMoney(row[c]); if(m!==null) allNums.push({c,v:m}); }
        const picked = allNums.length>=4 ? allNums.slice(allNums.length-4) : allNums;
        const d1 = picked.length>=1 ? picked[0].v : null;
        const d2 = picked.length>=2 ? picked[1].v : null;
        const d3 = picked.length>=3 ? picked[2].v : null;
        const d4 = picked.length>=4 ? picked[3].v : null;
        ruleRows.push({ lv1, lv2, lv3, lv4,
          depLt5w: d1, dep5w10w: d2, dep10w30w: d3, depGte30w: d4,
          opRate, txRate });
      }
    }
    // 解析特殊品牌资费（品牌名称/品牌ID 按表头列，费率取行内最后两个百分比）
    const brandRows = [];
    for (const grid of brandTables) {
      const h = findHeader(grid, 'brand');
      if (!h) continue;
      for (let r = h.rowIndex + 1; r < grid.length; r++) {
        const row = grid[r];
        const get = (i) => (i>=0 && i<row.length ? row[i] : null);
        const brand = get(h.品牌名称);
        if (!brand) continue;
        const pctIdx = []; for (let c=0;c<row.length;c++) if (/%(?!.*%)/.test(row[c]) && /[0-9]/.test(row[c])) pctIdx.push(c);
        const opIdx = pctIdx.length>=2 ? pctIdx[pctIdx.length-2] : -1;
        const txIdx = pctIdx.length>=1 ? pctIdx[pctIdx.length-1] : -1;
        brandRows.push({
          lv1: get(h.一级类目)||'', lv2: get(h.二级类目)||'', lv3: get(h.三级类目)||'', lv4: get(h.四级类目)||'',
          brandName: brand, brandId: get(h.品牌ID)||'',
          opRate: opIdx>=0 ? parseRate(row[opIdx]) : null,
          txRate: txIdx>=0 ? parseRate(row[txIdx]) : null,
        });
      }
    }
    return { ruleRows, brandRows };
  });
  return result;
}
