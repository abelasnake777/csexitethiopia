/* Check actual current-answer DOM, separately from the reference-link audit. */
'use strict';
const fs = require('fs'), path = require('path'), assert = require('assert/strict'), crypto = require('crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root = path.resolve(__dirname, '..'), base = process.env.BASE_URL || 'http://127.0.0.1:8457';
const inputBytes = fs.readFileSync(path.join(root, 'STUDY_NOTE_ANSWER_REVIEW.json')), data = JSON.parse(inputBytes);
const supportPath=path.join(root,'STUDY_NOTE_SUPPORT.json');
const support=fs.existsSync(supportPath)?JSON.parse(fs.readFileSync(supportPath)):null;
const reviewMap = new Map((support?support.questions.map(r=>r.answer_review):data.reviews).map(r => [r.id, r]));
if(support){data.courses=support.courses.map(c=>({...c,reviewed:c.questions}));data.reviewed=3485;data.targeted_questions=3485;}
const result = {passed:false, started_at:new Date().toISOString(), review_sha256:crypto.createHash('sha256').update(inputBytes).digest('hex'), courses:[], errors:[], script_errors:[], complete_review:data.complete, targeted:data.targeted_questions, reviewed:data.reviewed};
if(support)result.support_data_sha256=crypto.createHash('sha256').update(fs.readFileSync(supportPath)).digest('hex');
(async()=>{let browser;try{
 browser = await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});
 result.browser = browser.version();
 for(const width of [1440,390]){
  const page=await browser.newPage({viewport:{width,height:1000}});
  page.on('pageerror',e=>result.script_errors.push(e.message));
  for(const course of data.courses){
   await page.goto(base+'/Questions/Interactive_Study_Guides/'+course.slug+'.html');
   await page.waitForSelector('article.question');
   const observed=await page.evaluate(()=>{
    const payload=JSON.parse(document.getElementById('guide-data').textContent);
    const reviews=JSON.parse(document.getElementById('study-note-answer-data')?.textContent || '{}');
    const normalized=s=>s.replace(/\s+/g,' ').trim();
    return [...document.querySelectorAll('article.question')].map(article=>{
     const id=article.dataset.questionId, r=reviews[id], item=payload.questions.find(i=>i.question.id===id);
     const outer=[...article.querySelectorAll(':scope>details.reveal')];
     if(!r)return {id,reviewed:false,original_verified:item.review.status==='verified',unreviewed_status:item.review.status};
     const primary=article.querySelector('.current-study-answer');
     const archives=[...article.querySelectorAll('.legacy-module-review')];
     const initiallyClosed=[...outer,...archives].every(d=>!d.open);
     outer[0].querySelector(':scope>summary').click();
     const hintBody=outer[0].querySelector('.reveal-content');
     const hintVisible=!!hintBody.querySelector('.current-note-reading')?.getClientRects().length;
     const hintOnly=outer[0].open&&!outer[1].open;
     outer[1].querySelector(':scope>summary').click();
     const visibleText=normalized([...outer[1].querySelector('.reveal-content').children].filter(n=>!n.matches('.legacy-module-review')).map(n=>n.textContent).join(' '));
     const choiceNodes=[...primary.children].filter(n=>n.tagName==='P'&&n.firstElementChild?.tagName==='STRONG');
     const evidence=[...primary.querySelectorAll('blockquote')].map(n=>normalized([...n.childNodes].filter(x=>x.nodeName!=='CITE').map(n=>n.textContent).join('')));
     const record={displayed_variants:[...article.querySelectorAll(':scope > .variant-clarified-stem')].map(n=>({source:n.dataset.variantSource,stem:n.textContent,options:[...n.nextElementSibling.children].map(o=>o.textContent)})),displayed_stem:article.querySelector(':scope > .stem').textContent,displayed_options:[...article.querySelector(':scope > .choices').children].map(n=>n.textContent),clarification_note:article.querySelector(':scope > .question-clarification')?.textContent,clarified:article.dataset.questionClarified,id,reviewed:true,status:primary.dataset.reviewStatus,title:primary.querySelector('.current-answer-title').textContent,explanation:primary.querySelector('.current-answer-explanation').textContent,choices:choiceNodes.map(n=>n.textContent),evidence,variant_review_count:[...primary.querySelectorAll('h3')].filter(n=>n.textContent.startsWith('Alternative source choices · ')).length,variant_proofs_rendered:(r.variant_support||[]).every(v=>v.evidence.every(e=>[...primary.querySelectorAll('.current-variant-evidence')].some(n=>n.dataset.variantSource===v.source&&n.textContent.includes(e.quote)))),variants_rendered:(r.variant_reviews||[]).every(v=>primary.textContent.includes(v.source)&&primary.textContent.includes(v.answer_text)&&primary.textContent.includes(v.explanation)&&v.choices.every(c=>primary.textContent.includes(c.label+' · '+c.verdict+' — '+c.explanation))),external_sources:[...primary.querySelectorAll('.current-supplement')].map(n=>({statement:n.querySelector('p').textContent,url:n.querySelector('a').getAttribute('href'),title:n.querySelector('a').textContent})),hint_external_urls:[...hintBody.querySelectorAll('a')].map(a=>a.getAttribute('href')),archive_count:archives.length,archives_closed:archives.every(d=>!d.open),initially_closed:initiallyClosed,hint_visible:hintVisible,hint_only:hintOnly,legacy_warning_in_primary:/Not established by the supplied module|Review finding: insufficient module coverage|Source material is not an independently verified key/.test(visibleText)};
     outer.forEach(d=>d.open=false);
     return record;
    });
   });
   const target=observed.filter(q=>q.reviewed);
   assert.equal(target.length,course.reviewed,course.slug);
   for(const q of target){
    const r=reviewMap.get(q.id);
    assert.equal(q.status,r.status,q.id);
    if(r.question_revision){
     assert.equal(q.displayed_stem,r.question_revision.stem,q.id+' clarified stem');
     assert.deepEqual(q.displayed_options,r.question_revision.options.map(o=>o.label+'. '+o.text),q.id+' clarified options');
     assert.equal(q.clarification_note,r.question_revision.note,q.id+' clarification label');
     assert.equal(q.clarified,'true',q.id);
     assert.deepEqual(q.displayed_variants,(r.question_revision.variant_revisions||[]).map(v=>({source:v.source,stem:v.stem,options:v.options.map(o=>o.label+'. '+o.text)})),q.id+' source variant revisions');
    }
    assert.ok(q.title.includes(r.answer_text),q.id);
    assert.equal(q.explanation,r.explanation,q.id);
    assert.equal(q.choices.length,r.choices.length,q.id);
    for(let i=0;i<r.choices.length;i++)assert.ok(q.choices[i].includes(r.choices[i].explanation),q.id);
    assert.equal(q.variant_review_count,(r.variant_reviews||[]).length,q.id+' variant heading count');assert.equal(q.variants_rendered,true,q.id+' variant analysis missing');assert.equal(q.variant_proofs_rendered,true,q.id+' variant note proof missing');
    assert.deepEqual(q.external_sources,(r.external_evidence||[]).map(e=>({statement:e.statement,url:e.url,title:e.title})),q.id);
    for(const e of r.external_evidence||[])assert.ok(q.hint_external_urls.includes(e.url),q.id+' supplemental reading missing in hint');
    assert.deepEqual(q.evidence,r.evidence.map(e=>e.quote.replace(/\s+/g,' ').trim()),q.id);
    assert.equal(q.archive_count,2,q.id);assert.ok(q.archives_closed&&q.initially_closed&&q.hint_visible&&q.hint_only,q.id);
    assert.equal(q.legacy_warning_in_primary,false,q.id);
   }
   if(data.complete){assert.equal(observed.filter(q=>!q.reviewed&&!q.original_verified).length,0,course.slug+' non-verified record escaped review');}
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,course.slug+' overflow');
   // Opening an archive then hiding everything must close all nested blocks too.
   const first=page.locator('article.question[data-study-note-answer]').first();
   if(await first.count()){
    await first.locator(':scope>details.reveal').nth(1).locator(':scope>summary').click();
    await first.locator('.legacy-module-review').nth(1).locator(':scope>summary').click();
    await page.locator('#hide-all').click();
    assert.equal(await page.locator('article.question details[open]').count(),0);
   }
   result.courses.push({slug:course.slug,width,questions:observed.length,current_answers:target.length,all_current_answers_and_evidence_match:true,legacy_reviews_archived:true,default_hidden:true,overflow:false});
   console.log('PASS current answers',width,course.slug,target.length);
  }
  await page.close();
 }
 assert.equal(result.script_errors.length,0);result.passed=true;
}catch(e){result.errors.push(e.stack);process.exitCode=1;}finally{if(browser)await browser.close();result.finished_at=new Date().toISOString();fs.writeFileSync(path.join(root,'.qa/study-note-answers-dom.json'),JSON.stringify(result,null,2)+'\n');console.log(result.passed?'PASS current-answer audit':'FAIL current-answer audit');if(result.errors.length)console.error(result.errors.join('\n'));}})();
