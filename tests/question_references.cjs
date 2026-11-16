/* Exhaustive DOM evidence for the 16 question courses. No package installation needed. */
'use strict';
const fs = require('fs');
const path = require('path');
const assert = require('assert/strict');
const crypto = require('crypto');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || '/home/abel_asnake/Documents/Exit_Study/.study_guide_work/browser_test/node_modules/playwright');
const root = path.resolve(__dirname, '..');
const source = process.env.SOURCE_ROOT || '/home/abel_asnake/Documents/Exit_Study';
const base = (process.env.BASE_URL || 'http://127.0.0.1:8457').replace(/\/$/, '');
const readingPath = process.env.READING_MAP || path.join(source, '.master_guide_work/output/Question_Reading_Index.json');
const readingBytes = fs.readFileSync(readingPath);
const rows = JSON.parse(readingBytes);
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const output = path.join(root, '.qa/ref-dom-evidence.json');
const result = {schema_version: 1, passed: false, started_at: new Date().toISOString(), base_url: base,
  reading_map_sha256: hash(readingBytes), browser: {}, master_sections: {}, courses: [], questions: [],
  errors: [], script_errors: [], network_errors: [], scope_note: 'Link coverage and preserved behavior only; no claim that ambiguous items have a unique answer.'};
(async () => {
  let browser;
  try {
    assert.equal(rows.length, 3485);
    assert.equal(new Set(rows.map(r => r.id)).size, 3485);
    browser = await chromium.launch({executablePath: process.env.CHROME_BIN || '/opt/google/chrome/chrome', headless: true, args: ['--no-sandbox']});
    result.browser = {engine: 'chromium', version: browser.version(), executable: process.env.CHROME_BIN || '/opt/google/chrome/chrome'};
    const context = await browser.newContext({viewport: {width: 1440, height: 1000}});
    const page = await context.newPage();
    page.on('pageerror', e => result.script_errors.push({url: page.url(), message: e.message}));
    page.on('response', r => {if (r.url().startsWith(base) && r.status() >= 400) result.network_errors.push({url: r.url(), status: r.status()});});
    const masterResponse = await page.goto(base + '/Complete_CS_Exit_Study_Guide.html', {waitUntil: 'load'});
    assert.equal(masterResponse.status(), 200);
    assert.equal(hash(await masterResponse.body()), hash(fs.readFileSync(path.join(root, 'Complete_CS_Exit_Study_Guide.html'))), 'Served master differs from disk');
    const needed = [...new Set(rows.flatMap(r => r.section_ids))];
    result.master_sections = await page.evaluate(ids => Object.fromEntries(ids.map(id => {
      const matches = [...document.querySelectorAll('[id]')].filter(n => n.id === id);
      const node = matches[0];
      return [id, {count: matches.length, tag: node?.tagName || null, course_ancestor: node?.closest('article[id^="course-"]')?.id || null}];
    })), needed);
    for (const slug of [...new Set(rows.map(r => r.slug))].sort()) {
      const expected = rows.filter(r => r.slug === slug);
      const relative = 'Questions/Interactive_Study_Guides/' + slug + '.html';
      const response = await page.goto(base + '/' + relative, {waitUntil: 'load'});
      assert.equal(response.status(), 200);
      const diskHash = hash(fs.readFileSync(path.join(root, relative)));
      assert.equal(hash(await response.body()), diskHash, 'Served course differs from disk');
      await page.waitForSelector('article.question');
      const observed = await page.evaluate(() => {
        const model = JSON.parse(document.getElementById('guide-data').textContent);
        return [...document.querySelectorAll('article.question')].map(article => {
          const blocks = [...article.querySelectorAll(':scope > details.reveal')];
          const hint = blocks[0], answer = blocks[1];
          const links = block => [...block.querySelectorAll('a[href*="Complete_CS_Exit_Study_Guide.html#"]')].map(a => ({
            href: a.getAttribute('href'), resolved_href: a.href, text: a.textContent, target: a.getAttribute('target'), rel: a.getAttribute('rel'),
            in_answer_container: !!a.closest('.study-note-answer-references')
          }));
          const initiallyClosed = blocks.length === 2 && blocks.every(d => !d.open && d.querySelector('summary').getAttribute('aria-expanded') === 'false');
          const states = [];
          const toggle = node => {node.querySelector('summary').click(); states.push(blocks.map(d => d.open));};
          toggle(hint); const hintVisible = links(hint).length > 0 && !!hint.querySelector('a[href*="Complete_CS_Exit_Study_Guide.html#"]').getClientRects().length;
          toggle(answer); const answerVisible = links(answer).length > 0 && !!answer.querySelector('.study-note-answer-references a').getClientRects().length;
          toggle(hint); toggle(answer);
          const guidance = [...answer.querySelectorAll('h3')].find(n => n.textContent === 'Unified note guidance');
          const container = answer.querySelector('.study-note-answer-references');
          const item = model.questions.find(q => q.question.id === article.dataset.questionId);
          return {id: article.dataset.questionId, number: item.question.question, model_section_ids: item.guide.section_ids,
            block_count: blocks.length, initially_closed: initiallyClosed, toggle_states: states,
            hint_links_visible_when_open: hintVisible, answer_links_visible_when_open: answerVisible,
            answer_container_count: answer.querySelectorAll('.study-note-answer-references').length,
            answer_container_follows_guidance: guidance?.nextElementSibling === container,
            hint_links: links(hint), answer_links: links(answer)};
        });
      });
      assert.equal(observed.length, expected.length);
      assert.deepEqual(observed.map(q => q.id), expected.map(q => q.id), slug + ' question IDs/order');
      const wanted = new Map(expected.map(r => [r.id, r]));
      for (const q of observed) {
        const row = wanted.get(q.id);
        assert.deepEqual(q.model_section_ids, row.section_ids, q.id);
        assert.equal(q.initially_closed, true, q.id);
        assert.deepEqual(q.toggle_states, [[true, false], [true, true], [false, true], [false, false]], q.id);
        assert.equal(q.answer_container_count, 1, q.id);
        assert.equal(q.answer_container_follows_guidance, true, q.id);
        assert.equal(q.hint_links_visible_when_open, true, q.id);
        assert.equal(q.answer_links_visible_when_open, true, q.id);
        for (const [type, links] of [['hint', q.hint_links], ['answer', q.answer_links]]) {
          assert.deepEqual(links.map(a => a.href), row.section_ids.map(id => '../../Complete_CS_Exit_Study_Guide.html#' + encodeURIComponent(id)), q.id + ' ' + type);
          for (let i = 0; i < links.length; i++) {
            const link = links[i], section = result.master_sections[row.section_ids[i]];
            assert.equal(link.target, '_blank', q.id);
            assert.ok(link.rel.split(/\s+/).includes('noopener'), q.id);
            assert.ok(link.text.startsWith(row.section_ids[i] + ' · ') && !link.text.endsWith('undefined'), q.id);
            assert.equal(link.in_answer_container, type === 'answer', q.id);
            assert.equal(section.count, 1, q.id);
            assert.equal(section.tag, 'SECTION', q.id);
            assert.equal(section.course_ancestor, 'course-' + slug, q.id);
            assert.equal(link.resolved_href, new URL('/Complete_CS_Exit_Study_Guide.html#' + row.section_ids[i], base).href, q.id);
          }
        }
        result.questions.push({slug, ...q});
      }
      // Real pointer clicks at both ends of every course also check cross-question independence and ARIA.
      const pointerChecks = [];
      for (const index of [0, observed.length - 1]) {
        const card = page.locator('article.question').nth(index);
        const detail = card.locator(':scope > details.reveal');
        const states = [];
        for (const which of [0, 1, 0, 1]) {
          await detail.nth(which).locator('summary').click();
          const open = await detail.nth(which).evaluate(d => d.open);
          await assert.doesNotReject(() => page.waitForFunction(({id, which, open}) => document.querySelector('[data-question-id="' + id + '"]').querySelectorAll(':scope > details.reveal')[which].querySelector('summary').getAttribute('aria-expanded') === String(open), {id: observed[index].id, which, open}));
          states.push(await detail.evaluateAll(ds => ds.map(d => d.open)));
          assert.equal(await page.locator('article.question details.reveal[open]').count(), states.at(-1).filter(Boolean).length);
        }
        assert.deepEqual(states, [[true, false], [true, true], [false, true], [false, false]]);
        pointerChecks.push({id: observed[index].id, states, other_questions_closed: true, aria_synchronized: true});
      }
      // Hide-all and page reload must restore the original default-closed behavior.
      await page.locator('article.question').first().locator('details.reveal summary').first().click();
      await page.locator('#hide-all').click();
      assert.equal(await page.locator('details.reveal[open]').count(), 0);
      await page.reload({waitUntil: 'load'});
      assert.equal(await page.locator('article.question').count(), expected.length);
      assert.equal(await page.locator('details.reveal[open]').count(), 0);
      result.courses.push({slug, path: relative, sha256: diskHash, questions: observed.length, pointer_checks: pointerChecks, hide_all_closes: true, reload_defaults_closed: true});
      console.log('PASS DOM', slug, observed.length);
    }
    assert.equal(result.questions.length, 3485);
    assert.equal(new Set(result.questions.map(q => q.id)).size, 3485);
    assert.deepEqual(result.script_errors, []);
    assert.deepEqual(result.network_errors, []);
    result.passed = true;
  } catch (e) {
    result.errors.push(e.stack || String(e));
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    result.finished_at = new Date().toISOString();
    fs.writeFileSync(output, JSON.stringify(result, null, 2) + '\n');
    console.log(result.passed ? 'PASS all 3485 question DOM references' : 'FAIL: see ' + output);
    if (result.errors.length) console.error(result.errors.join('\n'));
  }
})();
