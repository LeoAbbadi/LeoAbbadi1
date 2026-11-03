// usage: node scripts/check_errors.js <html file>  — loads deck + print mode and prints JS errors
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
  p.on('pageerror', e => console.log('PAGEERROR', e.message));
  p.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  const url = 'file://' + path.resolve(process.argv[2]);
  await p.goto(url); await p.waitForTimeout(1500);
  await p.goto(url + '?print=1'); await p.waitForTimeout(1000);
  console.log('checked');
  await b.close();
})();
