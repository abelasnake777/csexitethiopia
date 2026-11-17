'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert/strict'),crypto=require('crypto');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root=path.resolve(__dirname,'..'),base=process.env.BASE_URL||'http://127.0.0.1:8457';
const audit=JSON.parse(fs.readFileSync(path.join(root,'ANSWER_COMPLETENESS_AUDIT.json')));
const result={passed:false,started_at:new Date().toISOString(),review_data_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(root,'STUDY_NOTE_ANSWER_REVIEW.json'))).digest('hex'),courses:[],questions:[],variants:[],errors:[],script_errors:[]};
const supportPath=path.join(root,'STUDY_NOTE_SUPPORT.json');if(fs.existsSync(supportPath))result.support_data_sha256=crypto.createHash('sha256').update(fs.readFileSync(supportPath)).digest('hex');
(async()=>{let browser;try{
 assert.equal(audit.passed,true,'Finish all repairs and regenerate completeness audit before this test');assert.equal(audit.review_data_sha256,result.review_data_sha256,'Stale completeness audit');
 browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const p=await browser.newPage({viewport:{width:1440,height:1000}});p.on('pageerror',e=>result.script_errors.push(e.message));
 for(const course of audit.courses){
  await p.goto(base+'/Questions/Interactive_Study_Guides/'+course.slug+'.html');await p.waitForSelector('article.question');
  const observed=await p.evaluate(()=>[...document.querySelectorAll('article.question')].map(article=>{
   const details=[...article.querySelectorAll(':scope>details.reveal')],initial=details.every(d=>!d.open);details[1].querySelector(':scope>summary').click();
   const primary=article.querySelector('.current-study-answer');
   const title=primary?.querySelector('.current-answer-title')||[...details[1].querySelectorAll('.answer-title')].find(n=>/^Correct answer/.test(n.textContent));
   const variants=[...article.querySelectorAll('.variant-answer-title,.explicit-variant-answer')].map(n=>({source:n.dataset.variantSource,title:n.textContent,visible:!!n.getClientRects().length}));
   const row={id:article.dataset.questionId,title:title?.textContent||'',answer_visible:!!title?.getClientRects().length,initially_closed:initial,outer_blocks:details.length,reading_links:[...details].map(d=>d.querySelectorAll('a[href*="Complete_CS_Exit_Study_Guide.html#"]').length),variants};details[1].querySelector(':scope>summary').click();return row;
  }));
  const expected=audit.questions.filter(q=>q.slug===course.slug);assert.equal(observed.length,expected.length);
  for(let i=0;i<expected.length;i++){
   const e=expected[i],q=observed[i];assert.equal(q.id,e.id);assert.ok(e.resolved,e.id);assert.ok(q.initially_closed&&q.outer_blocks===2&&q.answer_visible&&q.reading_links.every(n=>n>0),e.id);
   if(e.answer_kind==='written')assert.ok(q.title.startsWith('Answer: '),e.id);
   else{assert.ok(q.title.startsWith('Correct answer'),e.id);assert.ok(q.title.includes(e.labels.join(', ')),e.id);}
   const variants=audit.variants.filter(v=>v.id===e.id);assert.equal(q.variants.length,variants.length,e.id+' variant title count');
   for(const v of variants){const found=q.variants.find(n=>n.source===v.source);assert.ok(found?.visible&&found.title.startsWith('Correct answer')&&found.title.includes(v.labels.join(', ')),e.id+' '+v.source);result.variants.push({...v,actual_title:found.title});}
   result.questions.push({id:q.id,slug:course.slug,actual_title:q.title,initially_closed:true,answer_visible_when_open:true});
  }
  result.courses.push({slug:course.slug,questions:observed.length,all_answered:true});console.log('PASS every answer',course.slug,observed.length);
 }
 assert.equal(result.questions.length,3485);assert.equal(result.variants.length,24);assert.equal(result.script_errors.length,0);result.passed=true;
}catch(e){result.errors.push(e.stack);process.exitCode=1;}finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(root,'.qa/answer-completeness-dom.json'),JSON.stringify(result,null,2)+'\n');console.log(result.passed?'PASS all3485answers and24sourcevariants':'FAIL answer completeness');if(result.errors.length)console.error(result.errors.join('\n'));}})();
