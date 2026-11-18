'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root=path.resolve(__dirname,'..'),base=process.env.BASE_URL||'http://127.0.0.1:8457';
(async()=>{const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const out={passed:false,cases:[],errors:[]};try{
 for(const width of [1440,390]){
  const p=await browser.newPage({viewport:{width,height:950}});p.on('pageerror',e=>out.errors.push(e.message));
  await p.goto(base+'/ANSWER_REVIEW_SUMMARY.html');
  assert.equal(await p.locator('tbody tr').count(),16);
  assert.equal(await p.locator('details').count(),16);assert.equal(await p.locator('details[open]').count(),0);
  const rows=await p.locator('tbody tr').evaluateAll(rs=>rs.map(r=>[...r.querySelectorAll('td')].map(n=>Number(n.textContent))));
  const fullSupport=fs.existsSync(path.join(root,'STUDY_NOTE_SUPPORT.json'));
  for(const row of rows)assert.equal(row[0],row.slice(fullSupport?2:1).reduce((a,b)=>a+b,0));
  assert.equal(rows.reduce((n,r)=>n+r[0],0),3485);
  assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await p.locator('details').first().locator(':scope>summary').click();
  const a=p.locator('details').first().locator('a').first(),href=await a.getAttribute('href');
  await a.click();await p.waitForSelector('article.question');
  assert.equal(new URL(p.url()).hash,new URL(href,base).hash);
  assert.equal(await p.locator(new URL(p.url()).hash).count(),1);
  await p.goBack();
  assert.ok(p.url().endsWith('/ANSWER_REVIEW_SUMMARY.html'));
  await p.screenshot({path:path.join(root,'.qa/answer-review-summary-'+width+'.png'),fullPage:false});
  out.cases.push({width,courses:16,total_questions:3485,table_totals_match:true,default_closed:true,question_deep_link_and_return:true,overflow:false});await p.close();
 }
 assert.equal(out.errors.length,0);out.passed=true;
}finally{await browser.close();fs.writeFileSync(path.join(root,'.qa/answer-review-summary-dom.json'),JSON.stringify(out,null,2)+'\n');}console.log('PASS readable answer-review summary');})().catch(e=>{console.error(e);process.exitCode=1});
