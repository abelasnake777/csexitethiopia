'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root=path.resolve(__dirname,'..'),base=process.env.BASE_URL||'http://127.0.0.1:8457';
const cases=[
 ['Automata_and_Complexity_Theory','Q00891','B','aⁿbⁿcⁿ'],
 ['Network_and_System_Administration','SS099','A','-rwxr--r--'],
 ['Operating_System','NS0693','C','context-switch overhead'],
 ['Software_Engineering','Q01601','A','exactly two parallel paths']
];
(async()=>{const b=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const result={passed:false,cases:[],script_errors:[]};try{
 for(const width of [1440,390]){
  const p=await b.newPage({viewport:{width,height:1000}});p.on('pageerror',e=>result.script_errors.push(e.message));
  for(const[slug,id,label,term]of cases){
   await p.goto(base+'/Questions/Interactive_Study_Guides/'+slug+'.html');
   const card=p.locator('article[data-question-id="'+id+'"]');
   assert.equal(await card.getAttribute('data-question-clarified'),'true');
   assert.equal(await card.locator(':scope>details.reveal[open]').count(),0);
   await p.locator('#search').fill(term);assert.equal(await card.evaluate(e=>e.hidden),false,id+' clarified wording missing from search');
   await p.locator('#search').fill('');
   await card.locator(':scope>details.reveal').nth(1).locator(':scope>summary').click();
   assert.ok((await card.locator('.current-answer-title').textContent()).startsWith('Correct answer: '+label+' — '));
   assert.equal(await card.locator(':scope>details.reveal').first().evaluate(e=>e.open),false);
   assert.equal(await card.locator('.legacy-module-review[open]').count(),0);
   assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   await card.scrollIntoViewIfNeeded();
   if(width===390&&id==='SS099')await p.screenshot({path:path.join(root,'.qa/clarified-permissions-mobile.png')});
   await p.reload();assert.equal(await card.locator(':scope>details.reveal[open]').count(),0);
   result.cases.push({id,slug,width,answer:label,clarified_search:true,independent_toggles:true,reload_hidden:true,overflow:false});
  }
  await p.close();
 }
 assert.equal(result.script_errors.length,0);result.passed=true;
}finally{await b.close();fs.writeFileSync(path.join(root,'.qa/question-clarifications-dom.json'),JSON.stringify(result,null,2)+'\n');}console.log('PASS all four clarified questions on desktop/mobile');})().catch(e=>{console.error(e);process.exitCode=1});
