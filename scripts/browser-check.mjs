// Local-only browser QA. PLAYWRIGHT_MODULE may point to a bundled installation.
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const browser=await chromium.launch({headless:true, ...(process.env.PLAYWRIGHT_EXECUTABLE ? {executablePath:process.env.PLAYWRIGHT_EXECUTABLE}: {})});
const page=await browser.newPage({viewport:{width:1440,height:1100}});
const errors=[];page.on('pageerror',e=>errors.push(String(e)));
const base=process.env.BASE_URL||'http://127.0.0.1:4173';
await page.goto(base);await page.getByRole('heading',{name:'A little foresight. A better gameweek.'}).waitFor();
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
await page.goto(base+'/#fixtures');await page.locator('.match-card').first().waitFor();
if(await page.locator('.match-card').count()!==10)throw Error('Missing fixtures');
const scores=await page.locator('.match-card .score').allTextContents();
if(scores.some(s=>!/^\d+\.\d{2} – \d+\.\d{2}$/.test(s.trim())))throw Error('Expected goals must use two decimals');
await page.screenshot({path:'artifacts/qa/fixtures-desktop.png',fullPage:true});
await page.goto(base+'/#more');await page.getByRole('button',{name:'offline',exact:true}).click();await page.getByRole('heading',{name:'You’re offline.'}).waitFor();await page.getByRole('button',{name:'Return to preview'}).click();
for(const width of [390,768,1440]){
 await page.setViewportSize({width,height:1000});
 for(const route of ['home','team','discover','fixtures','compare','optimize','more']){
  await page.goto(`${base}/#${route}`);await page.locator('#main h1').waitFor();
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  if(overflow)throw Error(`Horizontal overflow ${route} ${width}`);
  if(route==='home'||route==='discover')await page.screenshot({path:`artifacts/qa/${route}-${width}.png`,fullPage:true});
 }
}
await page.setViewportSize({width:390,height:844});await page.goto(base+'/#home');await page.locator('.hero').waitFor();
await page.screenshot({path:'artifacts/qa/home-mobile.png',fullPage:true});
if(process.env.TEAM_IMPORT_LIVE==='1'){
 await page.setViewportSize({width:1440,height:1100});await page.goto(base+'/#team');
 await page.locator('#entry-id').fill('3795318');await page.getByRole('button',{name:'Import squad'}).click();
 await page.locator('.squad-status').waitFor({timeout:20000});
 if(await page.locator('.team-workspace .pitch-player').count()!==11||await page.locator('.bench button').count()!==4)throw Error('Imported squad does not have 11 starters and four bench players');
 if(!await page.getByText('Official squad locked after GW5').isVisible())throw Error('Locked gameweek is not labelled');
 await page.locator('#plan-bank').fill('1.3');await page.locator('#plan-bank').press('Tab');
 await page.locator('#plan-free-transfers').fill('2');await page.locator('#plan-free-transfers').press('Tab');
 await page.locator('#player-out').selectOption({index:1});await page.locator('#player-in').selectOption({index:1});
 await page.getByRole('button',{name:/Apply to planning squad/}).click();await page.getByText('1 PLANNED MOVE').waitFor();
 await page.reload();await page.getByText('1 PLANNED MOVE').waitFor();
 await page.screenshot({path:'artifacts/qa/team-import-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Imported team has horizontal overflow on mobile');
 await page.screenshot({path:'artifacts/qa/team-import-mobile.png',fullPage:true});
}
if(errors.length)throw Error(errors.join('\n'));
console.log(`PASS: search, watchlist, dialog, comparison, fixtures, preview state; 21 route/viewport overflow checks; zero browser exceptions${process.env.TEAM_IMPORT_LIVE==='1'?'; live Team ID import and planning persistence':''}.`);
await browser.close();
