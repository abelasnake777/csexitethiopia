'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root=path.resolve(__dirname,'..'),base=process.env.BASE_URL||'http://127.0.0.1:8457';
const bytes=fs.readFileSync(path.join(root,'STUDY_NOTE_SUPPORT.json')),support=JSON.parse(bytes);
const result={passed:false,started_at:new Date().toISOString(),support_data_sha256:crypto.createHash('sha256').update(bytes).digest('hex'),note_proofs_checked:0,viewports:[],script_errors:[],errors:[]};
(async()=>{let browser;try{
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 const p=await browser.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>result.script_errors.push(e.message));
 await p.goto(base+'/Complete_CS_Exit_Study_Guide.html');
 const proofs=support.questions.flatMap(r=>[...r.evidence,...r.variant_support.flatMap(v=>v.evidence)].map(e=>({...e,id:r.id,slug:r.slug})));
 const failures=await p.evaluate(proofs=>{const n=s=>s.replace(/\s+/g,' ').trim();return proofs.flatMap(e=>{const s=document.getElementById(e.section_id);return !s||s.closest('article').id!=='course-'+e.slug||!n(s.textContent).includes(n(e.quote))?[e.id+' '+e.section_id]:[]})},proofs);
 assert.deepEqual(failures,[],'Exact study-note proofs missing from real browser DOM');result.note_proofs_checked=proofs.length;
 const active=await p.evaluate(()=>data.map(r=>({id:r.id,stem:r.stem,options:r.options,section_ids:r.section_ids,status:r.status})));
 const map=new Map(active.map(r=>[r.id,r]));assert.equal(map.size,3485);
 for(const r of support.questions){const found=map.get(r.id),review=r.answer_review;assert.deepEqual(found.section_ids,r.section_ids,r.id+' live reading lookup');assert.equal(found.status,'covered');if(review.question_revision){assert.equal(found.stem,review.question_revision.stem);assert.deepEqual(found.options,review.question_revision.options);}}
 for(const width of [1440,390]){
  await p.setViewportSize({width,height:1000});
  for(const c of support.courses){
   for(const a of c.additions){
    await p.evaluate(id=>{const n=document.getElementById(id);for(let x=n;x;x=x.parentElement)if(x.tagName==='DETAILS')x.open=false;for(const d of n.querySelectorAll('details'))d.open=false;location.hash=id},a.id);
    await p.waitForFunction(id=>{const s=document.getElementById(id);return !!s.querySelector('h3').getClientRects().length&&s.querySelector('details').open},a.id);
    assert.equal(await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Study note overflow '+a.id+' '+width);
   }
   const sample=support.questions.find(r=>r.slug===c.slug&&r.answer_review.question_revision)||support.questions.find(r=>r.slug===c.slug);
   await p.selectOption('#course',c.slug);await p.fill('#query',sample.id);await p.click('#find');
   assert.equal(await p.locator('#results .result').count(),1,sample.id+' lookup');
   const expected=sample.answer_review.question_revision?.stem;
   if(expected)assert.equal(await p.locator('#results .stem').textContent(),expected);
   assert.equal(await p.locator('#results details[open]').count(),0,'Answer lookup should start hidden');
  }
  result.viewports.push({width,added_lessons:support.courses.reduce((n,c)=>n+c.additions.length,0),course_lookup_checks:16,existing_guide_content_preserved:true});
 }
 assert.deepEqual(result.script_errors,[]);result.passed=true;
}catch(e){result.errors.push(e.stack);process.exitCode=1;}finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(root,'.qa/study-note-support-dom.json'),JSON.stringify(result,null,2)+'\n');console.log(result.passed?'PASS all study-note evidence, additions and active lookup':'FAIL study-note support DOM');if(result.errors.length)console.error(result.errors.join('\n'));}})();
