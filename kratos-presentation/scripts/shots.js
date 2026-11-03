// Screenshot every slide, for checking the layout.
// usage: node scripts/shots.js <html file> <out dir> [print]
const { chromium } = require('playwright');
const path = require('path');

(async () => {
  const [file, out, mode] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => console.log('PAGEERROR', e.message));
  const url = 'file://' + path.resolve(file);
  if (mode === 'print') {
    await page.goto(url + '?print=1');
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(800);
    const els = await page.$$('.slide');
    for (let i = 0; i < els.length; i++) {
      await els[i].screenshot({ path: `${out}/p${String(i + 1).padStart(2, '0')}.png` });
    }
  } else {
    await page.goto(url);
    await page.evaluate(() => document.fonts.ready);
    const ids = await page.$$eval('.slide', s => s.map(x => x.id));
    for (let i = 0; i < ids.length; i++) {
      await page.evaluate(id => { location.hash = id; }, ids[i]);
      await page.waitForTimeout(5200);
      await page.screenshot({ path: `${out}/s${String(i + 1).padStart(2, '0')}.png` });
    }
  }
  await browser.close();
})();
