'use strict';
/** Additional all-course regression coverage. Product files are read-only.
 * Run: BASE_URL=http://127.0.0.1:8457 node tests/platform_all_courses.cjs
 * Optional: PLAYWRIGHT_PATH, CHROME_PATH, PLATFORM_QA_WORK (private report dir).
 * Requires the final build and an existing static HTTP server, as platform.cjs does.
 * Only JSON/Markdown reports in the private work directory are written at runtime.
 */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {execFileSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const work = process.env.PLATFORM_QA_WORK || '/home/abel_asnake/Documents/Exit_Study/.platform_upgrade_work';
const base = new URL((process.env.BASE_URL || 'http://127.0.0.1:8457').replace(/\/?$/, '/'));
let playwright;
for (const candidate of [process.env.PLAYWRIGHT_PATH, 'playwright', '/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright'].filter(Boolean)) {
  try { playwright = require(candidate); break; } catch (_) { /* Try the next installed location. */ }
}
if (!playwright) throw new Error('Playwright unavailable; set PLAYWRIGHT_PATH to an existing installation.');
const config = require(path.join(root, 'site.config.js'));
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'Modules/catalog.json'), 'utf8')).courses;
const courses = catalog.map(c => ({...c, title: c.title || c.course}));
const exportsBySlug = new Map(courses.map(c => [c.slug, JSON.parse(fs.readFileSync(path.join(root, 'assets/export-data', c.slug + '.json'), 'utf8'))]));
const started = new Date();
const report = {started_at: started.toISOString(), base_url: base.href, product_files_modified: false,
  coverage: {public_pages: 55, all_page_widths: [360, 768], representative_widths: [1024], courses: courses.length,
    original_module_pdfs: new Set(courses.map(c => c.file)).size}, checks: [], issues: [], page_errors: []};
let current = {phase: 'startup'};
let browser;
const keyOf = context => [context.phase, context.path || '', context.width || '', context.slug || ''].join('|');
async function check(context, fn) {
  current = context;
  const before = Date.now();
  try {
    const detail = await fn();
    report.checks.push({...context, passed: true, duration_ms: Date.now() - before, ...(detail ? {detail} : {})});
    return true;
  } catch (error) {
    const issue = {...context, message: error.message, stack: error.stack?.split('\n').slice(0, 5).join('\n')};
    report.checks.push({...context, passed: false, duration_ms: Date.now() - before});
    report.issues.push(issue);
    console.error('FAIL', keyOf(context), error.message);
    return false;
  }
}
function save() {
  report.finished_at = new Date().toISOString();
  report.elapsed_seconds = Math.round((Date.now() - started.getTime()) / 1000);
  report.passed = report.issues.length === 0 && report.page_errors.length === 0;
  report.summary = {passed_checks: report.checks.filter(c => c.passed).length, failed_checks: report.checks.filter(c => !c.passed).length,
    page_errors: report.page_errors.length, layout_checks: report.checks.filter(c => c.phase === 'layout').length};
  fs.mkdirSync(work, {recursive: true});
  fs.writeFileSync(path.join(work, 'platform-all-courses.json'), JSON.stringify(report, null, 2) + '\n');
  const issues = report.issues.map(i => `- ${i.phase}: ${i.path || i.slug || 'suite'}${i.width ? ` at ${i.width}px` : ''}: ${i.message.replace(/\n/g, ' ')}`);
  issues.push(...report.page_errors.map(i => `- Browser pageerror: ${i.url}: ${i.message}`));
  const text = [`# Additional platform verification`, '', `Result: ${report.passed ? 'PASS — no new issues found.' : 'FAIL — new issues listed below.'}`,
    ``, `Checked ${report.coverage.public_pages} final public pages at 360px and 768px, plus representative pages at 1024px.`,
    `${report.summary.layout_checks} layout checks; ${report.summary.passed_checks} total passed checks; ${report.summary.page_errors} browser page errors.`,
    `All-course coverage includes every question's default toggles and hint/answer reading references, each course's outline search and saved progress, and each module's actual rendered physical start page across 14 original PDFs.`,
    `SEO checks compare every final page with helper output, unique length-bounded metadata, and visible FAQ content matched to schema. Search covers stable question IDs for all 16 courses.`,
    '', ...(issues.length ? ['New issues:', '', ...issues] : ['No new product issues found.']), '',
    `Product pages/assets were not edited. This test and these private reports are the only task writes.`,
    `Run: BASE_URL=${base.href} node tests/platform_all_courses.cjs`, `Duration: ${report.elapsed_seconds}s.`, ''].join('\n');
  fs.writeFileSync(path.join(work, 'platform-all-courses.md'), text);
}

const staticCode = String.raw`
import sys,json,re
from pathlib import Path
from lxml import html
from xml.etree import ElementTree as ET
sys.path.insert(0,str(Path.cwd()/'tools'))
from seo_metadata import public_page_paths,page_metadata,generate_head,PUBLIC_FAQ
cfg=json.load(sys.stdin);root=Path.cwd();courses=json.loads((root/'Modules/catalog.json').read_text())['courses']
paths=public_page_paths(courses);out=[];titles={};descriptions={}
for p in paths:
 try:
  d=html.fromstring((root/p).read_text());expected=page_metadata(p,cfg,courses)
  ts=d.xpath('//head/title/text()');ds=d.xpath('//head/meta[@name="description"]/@content')
  assert ts==[expected['title']],('title/helper mismatch',ts)
  assert ds==[expected['description']],('description/helper mismatch',ds)
  assert 55<=len(ts[0])<=60 and 150<=len(ds[0])<=160,'metadata lengths'
  assert ts[0] not in titles,('duplicate title',titles.get(ts[0]));titles[ts[0]]=p
  assert ds[0] not in descriptions,('duplicate description',descriptions.get(ds[0]));descriptions[ds[0]]=p
  assert d.xpath('//link[@rel="canonical"]/@href')==[expected['canonical']],'canonical'
  if expected['course']:
   assert expected['course']['title'] in ds[0],'full course description'
   assert expected['course']['title'] in ' '.join(d.xpath('//h1//text()')),'full course H1'
  graphs=[json.loads(s.text) for s in d.xpath('//script[@type="application/ld+json"]')]
  nodes=[n for g in graphs for n in g.get('@graph',[g])]
  helper=html.fragment_fromstring('<div>'+generate_head(p,cfg,courses)+'</div>')
  expected_nodes=json.loads(helper.xpath('.//script')[0].text)['@graph']
  actual_core=[n for n in nodes if n.get('@type')!='FAQPage']
  assert actual_core==expected_nodes,'final schema/helper mismatch'
  org=[n for n in nodes if n.get('@type')=='EducationalOrganization'];assert len(org)==1,'organization schema'
  ws=[n for n in nodes if n.get('@type')=='WebSite'];assert len(ws)==1,'website schema'
  assert ws[0]['potentialAction']['target']['urlTemplate']==cfg['SITE_URL']+'/search.html?q={search_term_string}','functional SearchAction'
  assert d.xpath('//meta[@property="og:image"]/@content')==[cfg['SITE_URL']+'/assets/social-preview.png'],'absolute PNG OG'
  assert d.xpath('//meta[@name="twitter:card"]/@content')==['summary_large_image'],'Twitter card'
  faq=[n for n in nodes if n.get('@type')=='FAQPage'];sections=d.cssselect('.hub-faq')
  kind='home' if p=='index.html' else 'downloads' if p=='downloads.html' else None
  assert len(faq)==len(sections)==int(kind is not None),'FAQ only where visible'
  if kind:
   visible=[]
   for item in sections[0].xpath('./details'):
    assert not item.xpath('ancestor-or-self::*[@hidden]'),'FAQ hidden'
    visible.append({'question':item.find('summary').text_content().strip(),'answer':item.find('p').text_content().strip()})
   schema=[{'question':q['name'],'answer':q['acceptedAnswer']['text']} for q in faq[0]['mainEntity']]
   assert visible==schema==list(PUBLIC_FAQ[kind]),'FAQ visible text/schema mismatch'
  out.append({'path':p,'passed':True,'title_length':len(ts[0]),'description_length':len(ds[0])})
 except Exception as e:out.append({'path':p,'passed':False,'message':str(e)})
try:
 actual={n.text for n in ET.parse(root/'sitemap.xml').findall('.//{*}loc')}
 assert actual=={cfg['SITE_URL']+('/' if p=='index.html' else '/'+p) for p in paths},'sitemap page set'
 assert len(paths)==55,'expected 55 public pages'
 out.append({'path':'sitemap.xml','passed':True})
except Exception as e:out.append({'path':'sitemap.xml','passed':False,'message':str(e)})
print(json.dumps({'paths':paths,'checks':out}))
`;

async function ready(page, file) {
  const response = await page.goto(new URL(file, base).href, {waitUntil: 'load'});
  assert(response && response.ok(), `${file}: HTTP ${response?.status()}`);
  await page.waitForFunction(() => document.documentElement.dataset.platformReady === 'true');
  await page.evaluate(() => document.fonts.ready);
  if (file.startsWith('Modules/') && !file.endsWith('/index.html')) {
    await page.waitForFunction(() => {
      const c = JSON.parse(document.getElementById('module-config').textContent);
      const canvas = document.getElementById('pdf-canvas');
      return canvas?.dataset.error || (canvas?.dataset.renderedPage === String(c.start_page) && document.getElementById('pdf-stage').getAttribute('aria-busy') === 'false');
    }, null, {timeout: 30000});
    assert.equal(await page.locator('#pdf-canvas').getAttribute('data-error'), null, await page.locator('#viewer-status').textContent());
  }
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function noOverflow(page, context) {
  const geometry = await page.evaluate(() => ({width: innerWidth, client: document.documentElement.clientWidth, scroll: document.documentElement.scrollWidth,
    protrusions: [...document.querySelectorAll('body *')].filter(n => {
      const r = n.getBoundingClientRect();
      if (!r.width || !r.height || getComputedStyle(n).position === 'fixed') return false;
      if (r.right <= innerWidth + 1 && r.left >= -1) return false;
      // Content deliberately contained in an internal scroller is allowed.
      for (let p = n.parentElement; p && p !== document.body; p = p.parentElement) {
        if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX) && p.getBoundingClientRect().right <= innerWidth + 1) return false;
      }
      return true;
    }).slice(0, 8).map(n => ({tag: n.tagName, id: n.id, class: n.className?.baseVal || n.className}))}));
  assert.equal(geometry.width, context.width, 'exact requested viewport');
  assert(geometry.scroll <= geometry.width + 1, `document overflow ${JSON.stringify(geometry)}`);
  return geometry;
}
async function navAndIcon(page, file, width) {
  const actual = await page.evaluate(() => ({headers: document.querySelectorAll('.hub-header').length,
    icon: document.getElementById('hub-favicon')?.href, fallback: document.getElementById('hub-favicon-fallback')?.href,
    mobile: getComputedStyle(document.getElementById('hub-toggle')).display !== 'none',
    expanded: document.getElementById('hub-toggle').getAttribute('aria-expanded'),
    links: [...document.querySelectorAll('#hub-menu a')].map(a => ({href: a.href, target: a.target, current: a.getAttribute('aria-current')}))}));
  assert.equal(actual.headers, 1);
  assert.equal(actual.icon, new URL('favicon.svg', base).href);
  assert(actual.fallback?.startsWith('data:image/svg+xml,'), 'inline favicon fallback');
  assert.equal(actual.mobile, width < 992);
  assert.equal(actual.expanded, 'false');
  const expected = ['index.html', 'Questions/Interactive_Study_Guides/index.html', 'Complete_CS_Exit_Study_Guide.html', 'Outlines/index.html', 'Modules/index.html', 'downloads.html', 'search.html', 'index.html#support'];
  assert.deepEqual(actual.links.map(a => a.href), expected.map(p => new URL(p, base).href));
  assert(actual.links.every(a => !a.target), 'nav stays in same tab');
  assert.deepEqual(actual.links.filter(a => a.current === 'page').map(a => a.href), expected.includes(file) ? [new URL(file, base).href] : []);
  if (width === 360) {
    await page.locator('#hub-toggle').click();
    assert.equal(await page.locator('#hub-toggle').getAttribute('aria-expanded'), 'true');
    assert(await page.locator('#hub-menu').isVisible());
    await noOverflow(page, {width});
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#hub-toggle').getAttribute('aria-expanded'), 'false');
  }
}
async function questionDefaults(page, course) {
  const expected = exportsBySlug.get(course.slug).questions.map(q => ({id: q.id, number: String(q.number), sections: q.section_ids}));
  const snapshot = await page.evaluate(expected => {
    const articles = [...document.querySelectorAll('article.question')];
    const errors = [];
    for (let i = 0; i < expected.length; i++) {
      const exp = expected[i], a = articles[i];
      if (!a || a.id !== 'question-' + exp.number || a.dataset.questionId !== exp.id) {errors.push('question identity ' + exp.id); continue;}
      const reveals = [...a.querySelectorAll(':scope > details.reveal')];
      if (reveals.length !== 2) {errors.push(exp.id + ': two reveal controls required'); continue;}
      reveals.forEach((r, index) => {
        const summary = r.querySelector('summary');
        if (r.open || summary?.getAttribute('aria-expanded') !== 'false') errors.push(exp.id + ': default-closed aria state ' + index);
        if (!summary?.getAttribute('aria-label')?.startsWith('Show ')) errors.push(exp.id + ': summary accessible name');
        const refs = [...r.querySelectorAll('a[href*="Complete_CS_Exit_Study_Guide.html#"]')];
        for (const id of exp.sections) if (!refs.some(a => new URL(a.href).hash === '#' + id)) errors.push(exp.id + ': missing ' + (index ? 'answer' : 'hint') + ' reference ' + id);
        if (!refs.length || !r.querySelector('.reveal-content')?.textContent.trim()) errors.push(exp.id + ': empty reveal ' + index);
      });
    }
    return {articles: articles.length, inspected: expected.length, errors: errors.slice(0, 20)};
  }, expected);
  assert.equal(snapshot.articles, course.questions || expected.length);
  assert.deepEqual(snapshot.errors, []);
  return {questions_inspected: snapshot.inspected};
}
async function questionInteractions(page) {
  const reveals = page.locator('article.question').first().locator(':scope > details.reveal');
  await reveals.nth(0).locator('summary').click();
  await page.waitForFunction(() => document.querySelector('article.question > details.reveal summary').getAttribute('aria-expanded') === 'true');
  assert.equal(await reveals.nth(1).getAttribute('open'), null, 'hint does not reveal answer');
  await reveals.nth(1).locator('summary').click();
  assert.equal(await reveals.nth(0).getAttribute('open'), '', 'answer does not close hint');
  await reveals.nth(0).locator('summary').click();
  assert.equal(await reveals.nth(1).getAttribute('open'), '', 'closing hint keeps answer open');
  await page.locator('#hide-all').click();
  assert.equal(await page.locator('details.reveal[open]').count(), 0);
  // Follow a real hint reference; check the target reading section is revealed.
  await reveals.nth(0).locator('summary').click();
  const link = reveals.nth(0).locator('a[href*="Complete_CS_Exit_Study_Guide.html#"]').first();
  const url = new URL(await link.getAttribute('href'), page.url());
  await link.click();
  await page.waitForURL(url.href);
  await page.waitForFunction(id => {
    const n = document.getElementById(id);
    return n && [...n.querySelectorAll(':scope > details')].every(d => d.open);
  }, decodeURIComponent(url.hash.slice(1)));
  assert(await page.locator('[id="' + decodeURIComponent(url.hash.slice(1)) + '"]').isVisible());
}
async function outlineFunctions(page, course) {
  const total = await page.locator('.topic-card').count();
  assert.equal(total, exportsBySlug.get(course.slug).outlines.length);
  assert.equal(await page.locator('.topic-details[open]').count(), 0, 'default closed outlines');
  const first = page.locator('.topic-card').first();
  const id = await first.getAttribute('id');
  const title = (await first.locator('h2').textContent()).trim();
  assert.equal(await page.locator('#progress').getAttribute('value'), '0');
  await first.locator('.review-check').check();
  assert.equal(await page.locator('#progress').evaluate(n => n.value), 1);
  assert((await page.locator('#progress-label').textContent()).startsWith('1 / '));
  await page.reload();
  await page.waitForFunction(() => document.documentElement.dataset.platformReady === 'true');
  assert(await page.locator('.review-check').first().isChecked(), 'progress survives reload');
  await page.locator('#filter').selectOption('reviewed');
  assert.equal(await page.locator('.topic-card:visible').count(), 1);
  assert.equal(await page.locator('.topic-card:visible').getAttribute('id'), id);
  await page.locator('#filter').selectOption('unreviewed');
  assert.equal(await page.locator('.topic-card:visible').count(), total - 1);
  await page.locator('#filter').selectOption('focus');
  const focus = await page.locator('.topic-card:visible').evaluateAll(nodes => nodes.every(n => n.dataset.focus === 'true'));
  assert(focus, 'exam-focus filter');
  await page.locator('#filter').selectOption('all');
  await page.locator('#search').fill(title);
  assert(await first.isVisible(), 'search finds course topic');
  assert(await first.locator('.topic-details').evaluate(n => n.open));
  await page.locator('#collapse').click();
  assert.equal(await page.locator('.topic-details[open]').count(), 0);
  await page.locator('#expand').click();
  assert(await page.locator('.topic-card:visible .topic-details').evaluateAll(ns => ns.every(n => n.open)));
  await page.locator('#search').fill('zzzz_platform_no_topic_583129');
  assert.equal(await page.locator('.topic-card:visible').count(), 0);
  assert(await page.locator('#no-results').isVisible());
  await page.locator('#search').fill('');
  await page.locator('.review-check').first().uncheck();
  assert.equal(await page.locator('#progress').evaluate(n => n.value), 0);
  return {topics: total, persistence: true};
}
async function moduleFunctions(page, course) {
  const state = await page.evaluate(() => ({config: JSON.parse(document.getElementById('module-config').textContent),
    rendered: document.getElementById('pdf-canvas').dataset.renderedPage,
    input: document.getElementById('page-number').value, pages: document.getElementById('page-total').textContent,
    label: document.getElementById('pdf-canvas').getAttribute('aria-label'),
    open: [...document.querySelectorAll('a[href*=".pdf#page="]')].map(a => ({href: a.href, target: a.target})),
    download: document.querySelector('a[download][href$=".pdf"]')?.href,
    pixels: [...document.getElementById('pdf-canvas').getContext('2d').getImageData(0, 0, 50, 50).data].some(v => v > 0)}));
  assert.equal(state.config.start_page, course.start_page);
  assert.equal(state.config.file, course.file);
  assert.equal(state.rendered, String(course.start_page));
  assert.equal(state.input, String(course.start_page));
  assert.equal(state.pages, String(course.pages));
  assert(state.label.includes(`page ${course.start_page} of ${course.pages}`));
  const url = new URL('Modules/' + course.file, base);
  assert.equal(state.download, url.href);
  assert(state.open.some(a => a.href === url.href + '#page=' + course.start_page && !a.target));
  assert(state.pixels, 'PDF canvas has rendered pixels');
  assert.equal(await page.locator('#previous-page').isDisabled(), course.start_page === 1);
  await page.locator('#next-page').click();
  await page.waitForSelector(`#pdf-canvas[data-rendered-page="${course.start_page + 1}"]`, {timeout: 30000});
  await page.waitForFunction(() => document.getElementById('pdf-stage').getAttribute('aria-busy') === 'false');
  await page.locator('#previous-page').click();
  await page.waitForSelector(`#pdf-canvas[data-rendered-page="${course.start_page}"]`, {timeout: 30000});
  return {file: course.file, physical_start_page: course.start_page, pages: course.pages};
}
async function searchFunctions(page) {
  for (const course of courses) {
    const q = exportsBySlug.get(course.slug).questions[0];
    await ready(page, 'search.html?' + new URLSearchParams({q: q.id, course: course.slug, type: 'questions'}));
    await page.waitForFunction(() => document.getElementById('search-results-region').getAttribute('aria-busy') === 'false');
    const hits = page.locator('#search-results a');
    assert(await hits.count() > 0, course.slug + ' stable ID not searchable: ' + q.id);
    const first = hits.first();
    assert((await first.textContent()).includes(q.id), 'stable ID in ranked result');
    const expected = new URL('Questions/Interactive_Study_Guides/' + course.slug + '.html#question-' + q.number, base);
    assert.equal(await first.getAttribute('href'), expected.href);
    assert.equal(await first.getAttribute('target'), null);
    await first.click();
    await page.waitForURL(expected.href);
    assert(await page.locator('#question-' + q.number).isVisible());
  }
  await ready(page, 'search.html?type=module');
  await page.waitForFunction(() => document.getElementById('search-results-region').getAttribute('aria-busy') === 'false');
  assert.equal(await page.locator('#search-results>li').count(), 12);
  await page.locator('#search-next').click();
  assert.equal(await page.locator('#search-results>li').count(), 4);
  assert.equal(await page.locator('#search-results').getAttribute('start'), '13');
  assert(new URL(page.url()).searchParams.get('page') === '2');
  await page.locator('#search-clear').click();
  assert.equal(new URL(page.url()).search, '');
  await page.locator('#search-query').fill('zzzz_platform_no_topic_583129');
  await page.locator('#site-search-form button[type="submit"]').click();
  assert((await page.locator('#search-status').textContent()).startsWith('No results'));
  return {stable_question_ids: 16, real_result_navigation: 16, module_records: 16, pagination: true, clear: true, empty: true};
}

(async () => {
  const result = JSON.parse(execFileSync('python3', ['-B', '-c', staticCode], {cwd: root, input: JSON.stringify(config), encoding: 'utf8', maxBuffer: 8 * 1024 * 1024}));
  for (const item of result.checks) {
    report.checks.push({phase: 'static-seo', ...item});
    if (!item.passed) report.issues.push({phase: 'static-seo', path: item.path, message: item.message});
  }
  assert.equal(result.paths.length, 55);
  assert.equal(report.coverage.original_module_pdfs, 14);
  console.log('Static SEO:', result.checks.filter(x => x.passed).length + '/' + result.checks.length);
  browser = await playwright.chromium.launch({executablePath: process.env.CHROME_PATH || '/opt/google/chrome/chrome', args: ['--no-sandbox']});
  const context = await browser.newContext({viewport: {width: 360, height: 900}});
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  page.setDefaultNavigationTimeout(30000);
  page.on('pageerror', error => report.page_errors.push({...current, url: page.url(), message: error.message}));
  const representatives = ['index.html', 'Complete_CS_Exit_Study_Guide.html', 'Questions/Interactive_Study_Guides/index.html',
    'Questions/Interactive_Study_Guides/Computer_Programming.html', 'Outlines/index.html', 'Outlines/Computer_Programming.html',
    'Modules/index.html', 'Modules/Fundamental_of_Database_Systems.html', 'downloads.html', 'search.html'];
  for (const width of [360, 768, 1024]) {
    await page.setViewportSize({width, height: 900});
    const paths = width === 1024 ? representatives : result.paths;
    for (const file of paths) {
      const ctx = {path: file, width};
      if (!await check({...ctx, phase: 'navigation-load'}, () => ready(page, file))) continue;
      await check({...ctx, phase: 'layout'}, () => noOverflow(page, {width}));
      await check({...ctx, phase: 'nav-favicon'}, () => navAndIcon(page, file, width));
      const course = courses.find(c => file.endsWith('/' + c.slug + '.html'));
      if (course && file.startsWith('Questions/')) {
        await check({...ctx, phase: 'question-defaults', slug: course.slug}, () => questionDefaults(page, course));
        if (width === 360) await check({...ctx, phase: 'question-controls-references', slug: course.slug}, () => questionInteractions(page));
      }
      if (course && file.startsWith('Outlines/') && width === 360) {
        await check({...ctx, phase: 'outline-search-progress', slug: course.slug}, () => outlineFunctions(page, course));
      }
      if (course && file.startsWith('Modules/') && width === 360) {
        await check({...ctx, phase: 'module-physical-start', slug: course.slug}, () => moduleFunctions(page, course));
      }
      // Make interrupted runs reviewable without waiting for the whole matrix.
      save();
    }
    console.log('Completed width', width, 'pages', paths.length, 'issues', report.issues.length);
  }
  await page.setViewportSize({width: 360, height: 900});
  await check({phase: 'search-all-course-stable-ids', path: 'search.html', width: 360}, () => searchFunctions(page));
  assert.equal(context.pages().length, 1, 'all tested internal links navigate in the same tab');
  await browser.close();
  browser = null;
})().catch(error => {report.issues.push({phase: 'suite', message: error.stack || error.message}); console.error(error);}).finally(async () => {
  if (browser) await browser.close().catch(() => {});
  save();
  console.log(report.passed ? 'ALL-COURSES PASS' : 'ALL-COURSES FAIL', JSON.stringify(report.summary));
  console.log('Private report:', path.join(work, 'platform-all-courses.md'));
  if (!report.passed) process.exitCode = 1;
});
