// Local-only browser QA. PLAYWRIGHT_MODULE may point to a bundled installation.
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser=await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_EXECUTABLE}: {})});
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
await page.goto('http://127.0.0.1:4173');await page.getByRole('heading',{name:'A little foresight. A better gameweek.'}).waitFor();
await fs.mkdir('artifacts/qa',{recursive:true});
await page.screenshot({path:'artifacts/qa/home-desktop.png',fullPage:true});
await page.getByRole('link',{name:'Discover',exact:true}).click();
await page.locator('#global-search').fill('Saka');
if(await page.locator('tbody tr').count()!==3) throw Error('Search did not return the three matching names');
await page.getByRole('button',{name:'Watch Saka',exact:true}).click();
await page.locator('[data-player]').first().click();await page.locator('dialog[open]').waitFor();
await page.keyboard.press('Escape');
await page.locator('#global-search').fill('');
await page.locator('[data-compare]').nth(0).check();await page.locator('[data-compare]').nth(1).check();
await page.getByRole('link',{name:/Compare players/}).click();
await page.locator('.compare-card').nth(1).waitFor();
if(await page.locator('.compare-card').count()!==2)throw Error('Comparison failed');
await page.screenshot({path:'artifacts/qa/compare-desktop.png',fullPage:true});
await page.goto('http://127.0.0.1:4173/#fixtures');await page.locator('.match-card').first().waitFor();
if(await page.locator('.match-card').count()!==10)throw Error('Missing fixtures');
await page.screenshot({path:'artifacts/qa/fixtures-desktop.png',fullPage:true});
await page.goto('http://127.0.0.1:4173/#more');await page.getByRole('button',{name:'offline',exact:true}).click();await page.getByRole('heading',{name:'You’re offline.'}).waitFor();await page.getByRole('button',{name:'Return to preview'}).click();
for(const width of [390,768,1440]){
 await page.setViewportSize({width,height:1000});
 for(const route of ['home','team','discover','fixtures','compare','optimize','more']){
  await page.goto(`http://127.0.0.1:4173/#${route}`);await page.locator('#main h1').waitFor();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw Error(`Horizontal overflow ${route} ${width}`);
  if(route==='home'||route==='discover')await page.screenshot({path:`artifacts/qa/${route}-${width}.png`,fullPage:true});
 }
}
await page.setViewportSize({width:390,height:844});await page.goto('http://127.0.0.1:4173/#home');await page.locator('.hero').waitFor();
await page.screenshot({path:'artifacts/qa/home-mobile.png',fullPage:true});
if(errors.length)throw Error(errors.join('\n'));
console.log('PASS: search, watchlist, dialog, comparison, fixtures, preview state; 21 route/viewport overflow checks; zero browser exceptions.');
await browser.close();
