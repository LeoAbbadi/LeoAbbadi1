// Render the presentation to a 16:9 PDF (one slide per page, links kept).
// usage: node scripts/make_pdf.js <html file> <out.pdf>
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [file, out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  page.on('pageerror', e => { console.error('PAGEERROR', e.message); process.exitCode = 1; });
  const q = '?print=1';
  await page.goto('file://' + path.resolve(file) + q, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  // make sure every CSS background image has been decoded before printing
  await page.evaluate(async () => {
    const urls = new Set();
    for (const el of document.querySelectorAll('*')) {
      const bg = getComputedStyle(el).backgroundImage;
      for (const m of bg.matchAll(/url\("?(.*?)"?\)/g)) urls.add(m[1]);
    }
    await Promise.all([...urls].map(u => new Promise(r => { const i = new Image(); i.onload = i.onerror = r; i.src = u; })));
  });
  await page.waitForTimeout(500);
  await page.pdf({ path: out, width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
  await browser.close();
  console.log('wrote', out);
})();
