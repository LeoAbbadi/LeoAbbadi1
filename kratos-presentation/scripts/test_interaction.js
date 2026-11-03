// Smoke test of the interactive HTML: menu clicks, keyboard, reveal cards, grammar toggle.
// usage: node scripts/test_interaction.js <html file>
const { chromium } = require('playwright');
const path = require('path');
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1366, height: 1024 } });
  const errors = [];
  p.on('pageerror', e => errors.push(e.message));
  await p.goto('file://' + path.resolve(process.argv[2]));
  const active = () => p.$eval('.slide.active', s => s.id);
  const check = (label, got, want) => { console.log((got === want ? 'PASS ' : 'FAIL ') + label + ' -> ' + got); if (got !== want) process.exitCode = 1; };
  check('starts on menu', await active(), 's-menu');
  await p.click('#mainmenu a[href="#s-chapters"]'); await p.waitForTimeout(300);
  check('menu click: chapter select', await active(), 's-chapters');
  await p.click('#s-chapters .card[href="#s-gow2"]'); await p.waitForTimeout(300);
  check('chapter card click', await active(), 's-gow2');
  await p.click('#s-gow2 [data-reveal]');
  check('reveal opens', await p.$eval('#s-gow2 [data-reveal]', r => r.classList.contains('open')), true);
  await p.keyboard.press('ArrowRight'); await p.waitForTimeout(200);
  check('arrow right', await active(), 's-gow3');
  await p.keyboard.press('ArrowLeft'); await p.waitForTimeout(200);
  check('arrow left', await active(), 's-gow2');
  await p.click('#s-gow2 .hud-bot .seg[href="#s-ragnarok"]'); await p.waitForTimeout(200);
  check('saga bar click', await active(), 's-ragnarok');
  await p.keyboard.press('g');
  check('grammar toggle off', await p.evaluate(() => document.documentElement.classList.contains('nogrammar')), true);
  await p.keyboard.press('g');
  await p.keyboard.press('Escape'); await p.waitForTimeout(200);
  check('escape -> menu', await active(), 's-menu');
  await p.hover('#mainmenu a[href="#s-prologue"]');
  await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('Enter'); await p.waitForTimeout(200);
  check('menu keyboard select', await active(), 's-arsenal');
  check('no JS errors', errors.length, 0);
  await b.close();
})();
