/* One-time/public-source extraction for deterministic static readers and exports. */
'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const {chromium}=require('/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const ROOT=path.resolve(__dirname,'..'),base=process.env.BASE_URL||'http://127.0.0.1:8457';
const work='/home/abel_asnake/Documents/Exit_Study/.platform_upgrade_work';
const out=path.join(ROOT,'assets/export-data'),snap=path.join(ROOT,'maintenance/public-baseline');fs.mkdirSync(out,{recursive:true});fs.mkdirSync(snap,{recursive:true});
const cat=JSON.parse(fs.readFileSync(path.join(ROOT,'Modules/catalog.json'))).courses;
const srcManifest=JSON.parse(fs.readFileSync(path.join(ROOT,'SOURCE_MANIFEST.json')));
const sourceRoot='/home/abel_asnake/Documents/Exit_Study';
// Archive original imported bytes outside the public upload; no educational input is changed.
for(const f of srcManifest.files){if(!f.copied_path.endsWith('.html'))continue;const p=path.join(sourceRoot,f.source_path),bytes=fs.readFileSync(p);if(crypto.createHash('sha256').update(bytes).digest('hex')!==f.source_sha256)throw Error('Original source changed: '+p);const dest=path.join(ROOT,'maintenance/source-snapshots',f.copied_path);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,bytes);}
fs.writeFileSync(path.join(ROOT,'maintenance/SOURCE_MANIFEST.pre-platform.json'),JSON.stringify(srcManifest,null,2));
(async()=>{const browser=await chromium.launch({executablePath:'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}});
const records=[],index=[];
try{
 await page.goto(base+'/Complete_CS_Exit_Study_Guide.html');await page.waitForFunction(()=>document.documentElement.dataset.publicReader==='ready');
 const book=await page.evaluate(()=>{
  const text=n=>n.textContent.replace(/\s+/g,' ').trim();
  function listItems(ul){return[...ul.children].filter(n=>n.tagName==='LI').map(li=>{const copy=li.cloneNode(true);copy.querySelectorAll('ul,ol').forEach(n=>n.remove());return{text:text(copy),children:[...li.children].filter(n=>['UL','OL'].includes(n.tagName)).flatMap(listItems)}});}
  function blocks(node){const result=[];for(const n of node.children){if(n.tagName==='SUMMARY')continue;
   if(n.matches('.sources')){for(const a of n.querySelectorAll('a'))result.push({type:'source',text:text(a),url:a.getAttribute('href')});continue;}
   if(n.matches('.example,.trap')){result.push({type:'callout',title:n.matches('.trap')?'Exam tip':'Example',blocks:blocks(n)});continue;}
   if(n.tagName==='TABLE'){const rows=[...n.rows].map(r=>[...r.cells].map(text));result.push({type:'table',headers:n.tHead?rows.shift():[],rows});continue;}
   if(n.tagName==='PRE'||n.matches('.verbatim')){result.push({type:'code',text:n.textContent});continue;}
   if(n.tagName==='IMG'){result.push({type:'image',data:n.src});continue;}
   if(['H3','H4','H5','H6'].includes(n.tagName)){result.push({type:'heading',level:Number(n.tagName.slice(1)),text:text(n)});continue;}
   if(n.matches('ul.cue-list')){for(const li of n.children){if(li.matches('.sources')){result.push(...blocks({children:[li]}));continue;}const own=[...li.childNodes].filter(c=>c.nodeType===Node.TEXT_NODE||c.nodeType===Node.ELEMENT_NODE&&c.matches('.cue-text')).map(c=>c.textContent).join('').trim();if(own)result.push({type:'paragraph',text:own});for(const child of li.children){if(child.matches('.cue-text'))continue;if(child.matches('ul.detail-list')){for(const sub of child.children){if(sub.children.length)result.push(...blocks({children:[sub]}));else if(text(sub))result.push({type:'paragraph',text:text(sub)});}}else result.push(...blocks({children:[child]}));}}continue;}
   if(['UL','OL'].includes(n.tagName)){result.push({type:'list',ordered:n.tagName==='OL',items:listItems(n)});continue;}
   if(['P','BLOCKQUOTE'].includes(n.tagName)){if(text(n))result.push({type:'paragraph',text:text(n)});continue;}
   if(n.children.length)result.push(...blocks(n));else if(text(n))result.push({type:'paragraph',text:text(n)});
  }return result;}
  const courses=Object.fromEntries([...document.querySelectorAll('article[id^="course-"]')].map(a=>[a.id.slice(7),{intro:[...a.querySelectorAll(':scope>details>ul>.course-intro')].map(n=>({type:'paragraph',text:text(n)})),notes:[...a.querySelectorAll('section.note')].map(n=>({id:n.id,title:text(n.querySelector('h3')).replace(n.id,'').trim(),blocks:blocks(n.querySelector('details')||n)}))}]));
  return{courses,html:document.documentElement.outerHTML,intro:['START01','START02','START03'].map(id=>({id,title:text(document.getElementById(id).querySelector('h3')||document.getElementById(id).querySelector('summary')),blocks:blocks(document.getElementById(id))}))};
 });
 fs.writeFileSync(path.join(snap,'Complete_CS_Exit_Study_Guide.html'),book.html);fs.writeFileSync(path.join(out,'study-introduction.json'),JSON.stringify(book.intro));
 for(const course of cat){
  const slug=course.slug,rel='Questions/Interactive_Study_Guides/'+slug+'.html';
  const original=JSON.parse(fs.readFileSync(path.join(ROOT,rel),'utf8').match(/<script id="guide-data" type="application\/json">([\s\S]*?)<\/script>/)[1]);
  await page.goto(base+'/'+rel);await page.waitForFunction(()=>document.documentElement.dataset.publicReader==='ready');
  const data=await page.evaluate(()=>{
   const publicData=JSON.parse(document.getElementById('study-note-answer-data').textContent),clean=window.CSExitPublicCopy.clean;
   const questions=[...document.querySelectorAll('article.question')].map(article=>{
    const id=article.dataset.questionId,r=publicData[id],revision=r.question_revision;
    const qs={id,number:Number(article.id.slice(9)),stem:article.querySelector(':scope>.stem').textContent,options:[...article.querySelector(':scope>.choices').children].map(n=>({label:n.textContent[0],text:n.textContent.slice(3)})),hint:article.querySelector('.current-note-reading').textContent,section_ids:r.section_ids,sources:[...article.querySelectorAll('.provenance-list li')].map(n=>n.textContent.trim()),adapted:!!revision,answer:{labels:r.labels,text:clean(r.answer_text),explanation:clean(r.explanation),choices:r.choices.map(c=>({...c,explanation:clean(c.explanation)})),evidence:r.evidence.map(e=>({section_id:e.section_id,quote:clean(e.quote),url:'Complete_CS_Exit_Study_Guide.html#'+e.section_id})),module_refs:[]},variants:(r.variant_reviews||[]).map((v,i)=>({source:'Alternative version '+(i+1),stem:revision?.variant_revisions?.[i]?.stem||revision?.stem||article.querySelector(':scope>.stem').textContent,options:revision?.variant_revisions?.[i]?.options||JSON.parse(document.getElementById('guide-data').textContent).questions.find(q=>q.question.id===id).question.option_variants[i].options,answer:{labels:v.labels,text:clean(v.answer_text),explanation:clean(v.explanation),choices:v.choices.map(c=>({...c,explanation:clean(c.explanation)})),evidence:(r.variant_support||[])[i]?.evidence.map(e=>({section_id:e.section_id,quote:clean(e.quote),url:'Complete_CS_Exit_Study_Guide.html#'+e.section_id}))||[],module_refs:[]}}))};
    const image=article.querySelector(':scope>img.question-diagram');if(image)qs.diagram={data:image.src};return qs;
   });return{questions,html:document.documentElement.outerHTML};
  });
  const byId=new Map(original.questions.map(q=>[q.question.id,q]));
  for(const q of data.questions){const legacy=byId.get(q.id).review,refs=[...(legacy.answer?.references||[]),...(legacy.hint?.references||[])],seen=new Set();
   for(const ref of refs){const m=cat.find(m=>m.source_file===ref.module);if(!m||!ref.pdf_page)continue;const key=ref.module+'|'+ref.pdf_page+'|'+ref.line_start+'|'+ref.line_end;if(seen.has(key))continue;seen.add(key);q.answer.module_refs.push({title:m.course+' module',url:'Modules/'+m.file+'#page='+ref.pdf_page,page:ref.pdf_page,line_start:ref.line_start??null,line_end:ref.line_end??null,quote:ref.quote||''});}
   index.push({title:course.course+' - Question '+q.number,text:q.stem+' '+q.options.map(o=>o.text).join(' '),url:rel+'#question-'+q.number,course:slug,type:'questions',section_ids:q.section_ids});
  }
  const dest=path.join(snap,rel);fs.mkdirSync(path.dirname(dest),{recursive:true});fs.writeFileSync(dest,data.html);
  await page.goto(base+'/Outlines/'+slug+'.html');await page.waitForFunction(()=>document.documentElement.dataset.publicReader==='ready');
  const outline=await page.evaluate(()=>{
   const t=n=>n.textContent.replace(/\s+/g,' ').trim();
   function cues(ul){return[...ul.children].filter(n=>n.tagName==='LI').map(li=>{const own=[...li.childNodes].filter(n=>n.nodeType===Node.TEXT_NODE||n.nodeType===Node.ELEMENT_NODE&&!['UL','OL','DETAILS'].includes(n.tagName)).map(n=>n.textContent).join(' ').replace(/\s+/g,' ').trim();return{text:own,children:[...li.children].filter(n=>['UL','OL'].includes(n.tagName)).flatMap(cues)}});}
   return{html:document.documentElement.outerHTML,config:JSON.parse(document.getElementById('outline-config').textContent),topics:[...document.querySelectorAll('.topic-card')].map(n=>({id:n.id,title:t(n.querySelector('h2')||n.querySelector('summary')).replace(/\[Exam Focus\]/g,'').trim(),exam_focus:n.textContent.includes('[Exam Focus]'),cues:[...n.querySelectorAll(':scope>.topic-grid>details>ul.concepts,:scope>details>ul,:scope>ul')].flatMap(cues)}))};
  });
  // Preserve exact public outline DOM and its progress-key/source checksum.
  const od=path.join(snap,'Outlines',slug+'.html');fs.mkdirSync(path.dirname(od),{recursive:true});fs.writeFileSync(od,outline.html);
  const record={slug,title:course.course,question_count:data.questions.length,questions:data.questions,notes:book.courses[slug].notes,note_intro:book.courses[slug].intro,outline_config:outline.config,outlines:outline.topics,outline_intro:[]};
  fs.writeFileSync(path.join(out,slug+'.json'),JSON.stringify(record));records.push({slug,title:course.course,questions:record.questions.length,notes:record.notes.length,outlines:record.outlines.length});
  for(const note of record.notes)index.push({title:course.course+' - '+note.title,text:JSON.stringify(note.blocks),url:'Complete_CS_Exit_Study_Guide.html#'+note.id,course:slug,type:'notes'});
  index.push({title:course.course+' revision outline',text:JSON.stringify(record.outlines),url:'Outlines/'+slug+'.html',course:slug,type:'outlines'});
  console.log('EXTRACTED',slug,record.questions.length,'questions',record.notes.length,'notes',record.outlines.reduce((n,t)=>n+t.cues.length,0),'outline top cues');
 }
 fs.writeFileSync(path.join(out,'catalog.json'),JSON.stringify({courses:records},null,2));fs.writeFileSync(path.join(ROOT,'assets/search-index.json'),JSON.stringify({records:index}));
 fs.writeFileSync(path.join(work,'extraction-complete.json'),JSON.stringify({courses:records,questions:records.reduce((n,c)=>n+c.questions,0),complete:true},null,2));
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1});
