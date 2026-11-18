'use strict';
/* Real production exports: no fixtures, catalog overrides or replacement workers.
 * BASE_URL=http://127.0.0.1:8457 node tests/pdf_exports.cjs
 * Optional: --watch --wait-seconds=3600, --available, --stress-only.
 * PLAYWRIGHT_MODULE, CHROME_BIN, PDF_PYTHON, PDF_QA_DIR, PDF_TIMEOUT_MS override
 * local tooling/output. QA files must stay outside the published repository.
 */
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const ROOT = path.resolve(__dirname, '..');
const STUDY = path.resolve(ROOT, '../Exit_Study');
const BASE = (process.env.BASE_URL || 'http://127.0.0.1:8457').replace(/\/$/, '');
const OUT = path.resolve(process.env.PDF_QA_DIR || path.join(STUDY, '.platform_upgrade_work/pdf-exports'));
assert(!OUT.startsWith(ROOT + path.sep), 'PDF_QA_DIR must be private, outside the published repository');
const ARGS = new Set(process.argv.slice(2));
const WAIT = Number(process.argv.find(a => a.startsWith('--wait-seconds='))?.split('=')[1] || 3600) * 1000;
const TIMEOUT = Number(process.env.PDF_TIMEOUT_MS || 900000);
const KINDS = ['notes', 'outlines', 'questions'];
const GLOBAL = JSON.parse(fs.readFileSync(path.join(ROOT, 'assets/export-data/catalog.json'))).courses;
function dependency() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, 'playwright', path.join(STUDY, '.study_guide_work/browser_test/node_modules/playwright'), path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright')].filter(Boolean);
  for (const p of candidates) { try { return require(p); } catch (e) { if (e.code !== 'MODULE_NOT_FOUND') throw e; } }
  throw new Error('Install Playwright or set PLAYWRIGHT_MODULE.');
}
const PYTHON = process.env.PDF_PYTHON || (fs.existsSync(path.join(STUDY, '.study_guide_work/venv/bin/python')) ? path.join(STUDY, '.study_guide_work/venv/bin/python') : 'python3');
const PY_VERIFY = String.raw`
import sys,json,re,hashlib,unicodedata
try: import pymupdf as fitz
except ImportError: import fitz
spec=json.load(sys.stdin)
root=spec['root']; result=fitz.open(spec['output'])
def norm(s): return re.sub(r'\s+',' ',s).strip()
def body(s): return norm(re.sub(r'Page\s+\d+\s+of\s+\d+','',s))
def check(ok,message):
 if not ok: raise AssertionError(message)
n=len(result)
check(n>2,'PDF must contain front matter and body pages')
for i in range(n):
 text=result[i].get_text()
 check(re.search(r'Page\s+'+str(i+1)+r'\s+of\s+'+str(n)+r'\b',text),f'Global page number missing/wrong on {i+1}/{n}')
summary={'pages':n,'bytes':__import__('os').path.getsize(spec['output']),'all_page_numbers_checked':True}
if spec['mode']=='merged':
 expected=2; starts=[]; unicode_chars=set(); drawings=0; sample_pages=set([0,1]); all_identical=True
 front=norm(result[0].get_text()); toc=norm(result[1].get_text())
 for entry in spec['entries']:
  source=fitz.open(root+'/'+entry['fragment']); start=expected+1
  starts.append({'slug':entry['slug'],'title':entry['title'],'start':start,'pages':len(source)})
  title=norm(entry['title'])
  check(title in front,'Cover is missing '+title)
  check(re.search(re.escape(title)+r'\s+'+str(start)+r'\b',toc),'TOC start incorrect for '+title)
  check(title in norm(source[0].get_text()),'Source course divider missing '+title)
  sample_pages.add(expected)
  for j in range(len(source)):
   check(expected+j<n,'Merged output is truncated')
   before=source[j].get_text(); after=result[expected+j].get_text()
   check(body(before)==body(after),f'Copied body text changed: {entry["slug"]}, fragment page {j+1}')
   symbols={c for c in before if unicodedata.category(c)=='Sm' or '\u0370'<=c<='\u03ff' or '\U0001d400'<=c<='\U0001d7ff'}
   unicode_chars.update(symbols)
   if symbols and len(sample_pages)<8: sample_pages.add(expected+j)
   if j in (0,len(source)-1) or symbols:
    before_drawings=len(source[j].get_drawings()); after_drawings=len(result[expected+j].get_drawings())
    check(before_drawings==after_drawings,'Vector drawings changed on '+entry['slug']+' page '+str(j+1))
    drawings+=before_drawings
   check(len(source[j].get_images())==len(result[expected+j].get_images()),'Image resources changed')
  expected+=len(source); source.close()
 check(n==expected,f'Expected {expected} pages, received {n}')
 actual=spec.get('worker',{}).get('toc')
 if actual: check([(x['slug'],x['start'],x['pages']) for x in actual]==[(x['slug'],x['start'],x['pages']) for x in starts],'Worker TOC metadata incorrect')
 check(unicode_chars,'No scientific Unicode in production sources; choose richer courses')
 summary.update(toc=starts,all_fragment_text_identical=True,scientific_unicode=''.join(sorted(unicode_chars)),vector_drawings_checked=drawings,source_page_count=expected-2)
else:
 check(n==spec['expected_pages'],f'Expected {spec["expected_pages"]} pages, received {n}')
 sample_pages=set([0,1,2,n-1])
# Contact data and dated cover are public requirements.
cover=result[0].get_text()
for key in ['SITE_NAME','EMAIL']:
 check(spec['config'][key] in cover,'Cover missing '+key)
handle=spec['config']['TELEGRAM'].replace('https://t.me/','').lstrip('@')
check(handle in cover,'Cover missing Telegram')
if spec['mode']=='merged': check(re.search(r'\b\d{4}-\d{2}-\d{2}\b',cover),'Cover date missing')
# Save a few visual QA pages, never all thousands of stress pages.
render=[]
for p in sorted(sample_pages)[:8]:
 target=spec['render_prefix']+'-p'+str(p+1)+'.png'
 result[p].get_pixmap(matrix=fitz.Matrix(1.1,1.1),alpha=False).save(target);render.append(target)
summary['renders']=render
print(json.dumps(summary,ensure_ascii=False))
`;
function pythonVerify(spec) {
  return new Promise((resolve, reject) => {
    const p = spawn(PYTHON, ['-c', PY_VERIFY], { stdio: ['pipe', 'pipe', 'pipe'] });
    let stdout = '', stderr = '';
    p.stdout.on('data', b => stdout += b); p.stderr.on('data', b => stderr += b);
    p.on('error', reject);
    p.on('close', code => {
      if (code) reject(new Error('Production PDF validation failed: ' + stderr));
      else { try { resolve(JSON.parse(stdout)); } catch (e) { reject(new Error('Invalid verifier result: ' + stdout + stderr)); } }
    });
    p.stdin.end(JSON.stringify(spec));
  });
}
function readCatalog() { return JSON.parse(fs.readFileSync(path.join(ROOT, 'assets/pdf/catalog.json'))); }
function existsPDF(resource, field) {
  if (!resource?.[field]) return false;
  try { const s = fs.statSync(path.join(ROOT, resource[field])); return s.size > 100; } catch { return false; }
}
function plan(catalog) {
  const cases = [], missing = [];
  for (const kind of KINDS) {
    const ready = GLOBAL.map(c => catalog.courses.find(row => row.slug === c.slug)).filter(c => existsPDF(c?.resources?.[kind], 'download') && existsPDF(c?.resources?.[kind], 'fragment'));
    if (ready.length) cases.push({ id: 'single-' + kind, kind, mode: 'single', entries: ready.slice(0, 1), resource: ready[0].resources[kind] }); else missing.push('single-' + kind);
    if (ready.length >= 2) cases.push({ id: 'multi-' + kind, kind, mode: 'merged', entries: ready.slice(0, 2) }); else missing.push('multi-' + kind);
    if (catalog.courses.length === 16 && ready.length === 16 && existsPDF(catalog.all[kind], 'download')) cases.push({ id: 'all-' + kind, kind, mode: 'all', entries: ready, resource: catalog.all[kind] }); else missing.push('all-' + kind);
  }
  const questions = catalog.courses.filter(c => existsPDF(c.resources?.questions, 'fragment'));
  if (questions.length === 16) {
    const largest = questions.slice().sort((a,b) => b.resources.questions.fragment_pages - a.resources.questions.fragment_pages).slice(0,15);
    // The UI orders selected entries by the production catalog, not click order.
    const selected = new Set(largest.map(c => c.slug));
    cases.push({ id:'stress-15-questions', kind:'questions', mode:'merged', entries:catalog.courses.filter(c => selected.has(c.slug)), stress:true });
  } else missing.push('stress-15-questions');
  return { cases: ARGS.has('--stress-only') ? cases.filter(c => c.stress) : cases, missing: ARGS.has('--stress-only') ? missing.filter(x => x === 'stress-15-questions') : missing };
}
function hash(file) { return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex'); }
function inputHashes(test) {
  const files = ['assets/pdf/catalog.json', ...test.entries.map(c => c.resources[test.kind].fragment), ...(test.resource ? [test.resource.download] : [])];
  return Object.fromEntries(files.map(file => [file, hash(path.join(ROOT, file))]));
}
async function instrument(context) {
  await context.addInitScript(() => {
    const NativeWorker = window.Worker;
    window.__pdfQA = { created: [], terminated: [], progress: [], completed: [], errors: [] };
    window.Worker = class extends NativeWorker {
      constructor(url, options) {
        super(url, options); this.qaIndex = window.__pdfQA.created.length;
        window.__pdfQA.created.push({ url:String(url), at:performance.now() });
        this.addEventListener('message', event => {
          const data=event.data || {};
          if(data.type==='progress') window.__pdfQA.progress.push({ at:performance.now(), progress:data.progress, message:data.message });
          if(data.type==='error') window.__pdfQA.errors.push(data.message);
          if(data.type==='complete') window.__pdfQA.completed.push({ at:performance.now(), arrayBuffer:data.buffer instanceof ArrayBuffer, bytes:data.buffer?.byteLength, pages:data.pages, toc:data.toc });
        });
      }
      terminate() { window.__pdfQA.terminated.push({ index:this.qaIndex, at:performance.now() }); return super.terminate(); }
    };
  });
}
async function rss(browserCDP) {
  const {processInfo} = await browserCDP.send('SystemInfo.getProcessInfo');
  const readings = await Promise.all(processInfo.map(async p => {
    try { const data=await fsp.readFile('/proc/'+p.id+'/status','utf8'); return Number(data.match(/^VmRSS:\s+(\d+)/m)?.[1] || 0); } catch { return 0; }
  }));
  return readings.reduce((a,b)=>a+b,0)*1024;
}
async function runCase(browser, browserCDP, test, report) {
  const started = Date.now(), context=await browser.newContext({acceptDownloads:true,viewport:{width:390,height:844}});
  await instrument(context);
  const page=await context.newPage(), requests=[], responses=[], errors=[];
  page.on('request',r=>requests.push(r.url()));
  page.on('response',r=>{if(r.status()>=400)responses.push({url:r.url(),status:r.status()});});
  page.on('pageerror',e=>errors.push(e.message));
  page.on('crash',()=>errors.push('Browser page crashed'));
  const result={ id:test.id, kind:test.kind, mode:test.mode, selected:test.entries.map(c=>c.slug), started_at:new Date(started).toISOString(), passed:false, memory_measurement:'Peak sum of browser process resident-set sizes; shared pages may be counted more than once', peak_browser_rss_bytes:0 };
  result.input_hashes = inputHashes(test);
  report.cases.push(result);await saveReport(report);
  let monitoring=false;
  const monitor=setInterval(async()=>{
    if(monitoring)return;monitoring=true;
    try {result.peak_browser_rss_bytes=Math.max(result.peak_browser_rss_bytes,await rss(browserCDP));} catch {} finally {monitoring=false;}
  },500);
  const heartbeat=setInterval(async()=>{
    let message='';try{message=await page.locator('[data-pdf-status]').textContent({timeout:1000});}catch{}
    console.log(test.id,Math.round((Date.now()-started)/1000)+'s',Math.round(result.peak_browser_rss_bytes/1048576)+' MiB RSS',message);
  },15000);
  try {
    await page.goto(BASE+'/downloads.html');
    await page.waitForFunction(()=>!!window.CSExitPDF&&!!window.CSExitSite);
    const config=await page.evaluate(()=>window.CSExitSite.config);
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true,'Download page overflow');
    await page.locator('[data-cs-downloads] [data-pdf-kind="'+test.kind+'"]').click();
    const dialog=page.locator('dialog[open]');await dialog.waitFor({state:'visible'});
    assert.equal(await dialog.locator('.cs-pdf-course-list input').count(),16);
    assert.equal(await dialog.locator('.cs-pdf-course-list input:checked').count(),16);
    if(test.entries.length!==16){
      await dialog.locator('.cs-pdf-select-all input').uncheck();
      for(const course of test.entries) await dialog.locator('input[value='+JSON.stringify(course.slug)+']').check();
    }
    assert.equal(await dialog.locator('.cs-pdf-course-list input:checked').count(),test.entries.length);
    assert.equal(await dialog.locator('.cs-pdf-count').textContent(),test.entries.length+' of 16 courses selected');
    assert.equal(await dialog.locator('button[type=submit]').isEnabled(),true);
    await page.screenshot({path:path.join(OUT,test.id+'-selection.png')});
    const mergeStarted=Date.now();
    const outcome=Promise.race([
      page.waitForEvent('download',{timeout:TIMEOUT}),
      page.locator('[data-pdf-error]').waitFor({state:'visible',timeout:TIMEOUT}).then(async()=>{throw new Error(await page.locator('[data-pdf-error]').textContent());}),
      page.waitForEvent('crash',{timeout:TIMEOUT}).then(()=>{throw new Error('Browser page crashed during export');})
    ]);
    await dialog.locator('button[type=submit]').click();
    const download=await outcome;
    const failure=await download.failure();assert.equal(failure,null);
    const output=path.join(OUT,test.id+'.pdf');await download.saveAs(output);
    result.download_seconds=Number(((Date.now()-mergeStarted)/1000).toFixed(3));result.filename=download.suggestedFilename();result.output=output;
    result.peak_browser_rss_bytes=Math.max(result.peak_browser_rss_bytes,await rss(browserCDP));
    assert.equal(browser.contexts().filter(c=>c===context).length,1);
    assert.equal(context.pages().length,1,'Export must remain in the same tab');
    assert.equal(await page.locator('[data-pdf-result]').isVisible(),true);
    assert.equal(await page.locator('[data-pdf-cancel]').isVisible(),false);
    assert.equal(await page.locator('[data-pdf-progress]').getAttribute('value'),'100');
    assert(!new URL(page.url()).searchParams.has('generate'));
    const state=await page.evaluate(()=>window.__pdfQA);
    result.worker={created:state.created.length,terminated:state.terminated.length,completed:state.completed.length};
    result.requests=requests;result.http_errors=responses;result.page_errors=errors;
    if(test.mode==='merged'){
      assert.equal(state.created.length,1,'Custom selection must use one real worker');
      assert.equal(state.completed.length,1,'Worker did not return a completed PDF');
      assert.equal(state.terminated.length,1,'Completed worker was not terminated');
      assert(state.completed[0].arrayBuffer,'Worker must return an ArrayBuffer');
      assert.equal(state.completed[0].bytes,fs.statSync(output).size);
      assert(requests.some(u=>u.includes('/assets/pdf-merge-worker.js')));
      assert(requests.some(u=>u.includes('/assets/vendor/pdf-lib/pdf-lib.min.js')));
      for(const c of test.entries)assert(requests.includes(new URL(c.resources[test.kind].fragment,BASE+'/').href),'Fragment not fetched: '+c.slug);
      result.worker.progress_events=state.progress.length;
      result.worker.final=state.completed[0];
    }else{
      assert.equal(state.created.length,0,'Prebuilt download must not create a worker');
      assert(!requests.some(u=>u.includes('pdf-lib')||u.includes('pdf-merge-worker')),'Prebuilt download loaded merge code');
      assert.equal(hash(output),hash(path.join(ROOT,test.resource.download)),'Complete PDF download differs from catalog file');
    }
    assert.deepEqual(errors,[]);assert.deepEqual(responses,[]);
    await page.screenshot({path:path.join(OUT,test.id+'-complete.png')});
    assert.deepEqual(inputHashes(test), result.input_hashes, 'Production PDF inputs changed during the run; rerun after the build settles');
    result.pdf=await pythonVerify({root:ROOT,output,mode:test.mode==='merged'?'merged':'complete',expected_pages:test.resource?.pages,entries:test.entries.map(c=>({slug:c.slug,title:c.title,fragment:c.resources[test.kind].fragment})),worker:state.completed[0],config,render_prefix:path.join(OUT,test.id)});
    assert.deepEqual(inputHashes(test), result.input_hashes, 'Production PDF inputs changed during verification; rerun after the build settles');
    result.passed=true;
    console.log('PASS',test.id,result.pdf.pages+' pages',result.download_seconds+'s',Math.round(result.peak_browser_rss_bytes/1048576)+' MiB peak browser RSS');
  } catch(e){result.inputs_changed=JSON.stringify(inputHashes(test))!==JSON.stringify(result.input_hashes);result.error=e.stack||e.message;console.error('FAIL',test.id,e.message);try{await page.screenshot({path:path.join(OUT,test.id+'-failure.png')});}catch{}}
  finally{clearInterval(monitor);clearInterval(heartbeat);result.total_seconds=Number(((Date.now()-started)/1000).toFixed(3));await context.close();await saveReport(report);}
  return result.passed;
}
async function saveReport(report){
  await fsp.mkdir(OUT,{recursive:true});
  await fsp.writeFile(path.join(OUT,'report.json.pending'),JSON.stringify(report,null,2)+'\n');
  await fsp.rename(path.join(OUT,'report.json.pending'),path.join(OUT,'report.json'));
}
(async()=>{
  await fsp.mkdir(OUT,{recursive:true});
  const report={passed:false,status:'running',started_at:new Date().toISOString(),base_url:BASE,production:true,catalog_overrides:false,fixtures:false,cases:[]};
  const {chromium}=dependency();
  const browser=await chromium.launch({executablePath:process.env.CHROME_BIN||'/opt/google/chrome/chrome',headless:true,args:['--no-sandbox','--disable-dev-shm-usage']});
  const browserCDP=await browser.newBrowserCDPSession();const finished=new Set();const start=Date.now();
  try{
    while(true){
      const catalog=readCatalog(),current=plan(catalog);report.catalog_generated_at=catalog.generated_at;report.pending=current.missing;
      for(const test of current.cases){if(!finished.has(test.id)){await runCase(browser,browserCDP,test,report);finished.add(test.id);}}
      if(!current.missing.length)break;
      await saveReport(report);
      if(ARGS.has('--available'))break;
      if(!ARGS.has('--watch')||Date.now()-start>=WAIT)throw new Error('Production catalog not ready: '+current.missing.join(', ')+'. Use --watch to wait, or --available for an explicitly partial run.');
      console.log('Waiting for production catalog:',current.missing.join(', '));
      await new Promise(r=>setTimeout(r,5000));
    }
    report.passed=!report.pending.length&&report.cases.length>0&&report.cases.every(c=>c.passed);
    report.status=report.passed?'passed':report.pending.length?'partial':'failed';
  }catch(e){report.status='failed';report.error=e.stack;console.error(e.message);}
  finally{await browser.close();report.finished_at=new Date().toISOString();await saveReport(report);}
  console.log('Production PDF export report:',path.join(OUT,'report.json'));
  if(!report.passed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exitCode=1;});
