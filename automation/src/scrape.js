
// 规则页抓取：Playwright 无头浏览器渲染后解析 DOM 表格
// 说明：页面为微前端 SPA，初始 HTML 无正文，必须真实渲染。
import { chromium } from 'playwright';
import { config } from './config.js';
import { parsePage } from './parser.js';

export async function scrapePage() {
  const { rule } = config;
  const { executablePath, headless, timeoutMs } = config.scrape;
  // 启动策略：env 指定路径 > 系统 Chrome > Playwright 自带 Chromium
  // 低内存/root 部署适配：no-sandbox(容器/root 常用)、禁用 GPU、禁用 /dev/shm 共享内存
  const launchOpts = { headless, args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage', '--disable-software-rasterizer'] };
  const attempt = async (opts) => chromium.launch(opts);

  let browser = null;
  if (executablePath) {
    browser = await attempt({ ...launchOpts, executablePath });
  } else {
    // 依次尝试 chrome channel、msedge、默认 chromium
    for (const channel of ['chrome', 'msedge', undefined]) {
      try {
        browser = await attempt(channel ? { ...launchOpts, channel } : launchOpts);
        break;
      } catch (e) {
        console.log('[scrape] channel "' + channel + '" 不可用，尝试下一个');
      }
    }
    if (!browser) {
      console.error('[scrape] 无可用浏览器。请在部署机安装 chromium：npx playwright install chromium');
      throw new Error('无法启动浏览器');
    }
  }
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 2000 } });
    await page.goto(rule.url, { waitUntil: 'domcontentloaded', timeout: timeoutMs, referer: 'https://learn-jdm.jd.com/' });
    // 等待规则表出现
    await page.waitForFunction(
      () => document.querySelectorAll('table').length > 0 && document.body.innerText.includes('运营支持服务费率'),
      { timeout: timeoutMs },
    );
    await page.waitForTimeout(1500);
    const { ruleRows, brandRows } = await parsePage(page);
    // 生效时间与标题（首段文本）
    const meta = await page.evaluate(() => {
      const txt = document.body.innerText || '';
      const eff = (txt.match(/生效时间[:：]\s*([0-9-]+)/) || [])[1] || '';
      const title = (document.querySelector('h1, .rule-title, .title, .knowledge-title')?.innerText || txt.match(/[^\n]*资费标准/) || [''])[0] || '';
      return { effectiveAt: eff, title: title.trim() };
    });
    return { ruleRows, brandRows, effectiveAt: meta.effectiveAt, title: meta.title };
  } finally {
    await browser.close();
  }
}
