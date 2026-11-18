/* Static search: {records:[{title,text,url,course,type}]}; no external service.
   Query state: search.html?q=keywords&course=slug&type=notes&page=2.
   Main owns index generation. Result anchors navigate in the current tab. */
(() => {
  'use strict';
  const form = document.getElementById('site-search-form');
  if (!form) return;
  const query = document.getElementById('search-query');
  const course = document.getElementById('search-course');
  const type = document.getElementById('search-type');
  const status = document.getElementById('search-status');
  const results = document.getElementById('search-results');
  const region = document.getElementById('search-results-region');
  const heading = document.getElementById('search-results-heading');
  const pager = document.getElementById('search-pagination');
  const previous = document.getElementById('search-previous');
  const next = document.getElementById('search-next');
  const pageLabel = document.getElementById('search-page-label');
  const retry = document.getElementById('search-retry');
  const PAGE_SIZE = 12;
  const MAX_QUERY = 200;
  const TYPE_LABELS = {notes: 'Study notes', questions: 'Practice questions', outlines: 'Revision outlines', module: 'Course modules', modules: 'Course modules'};
  const root = new URL('./', location.href);
  const courseNames = new Map([...course.options].filter(o => o.value).map(o => [o.value, o.textContent]));
  let records = null;
  let matches = [];
  let page = 1;
  let failed = false;
  const fold = value => String(value).normalize('NFKC').toLocaleLowerCase('en');
  const element = (tag, value, className) => {
    const node = document.createElement(tag);
    if (value !== undefined) node.textContent = value;
    if (className) node.className = className;
    return node;
  };

  function resultURL(value) {
    if (typeof value !== 'string' || !value.trim() || /[\u0000-\u001f\\]/u.test(value)) return null;
    try {
      const url = new URL(value, root);
      if (url.origin !== root.origin || !url.pathname.startsWith(root.pathname) || !url.pathname.endsWith('.html')) return null;
      if (url.username || url.password) return null;
      return url.href;
    } catch (_) { return null; }
  }

  function readLocation() {
    const params = new URLSearchParams(location.search);
    query.value = (params.get('q') || '').slice(0, MAX_QUERY);
    const selectedCourse = params.get('course') || '';
    course.value = [...course.options].some(o => o.value === selectedCourse) ? selectedCourse : '';
    const selectedType = params.get('type') || '';
    type.value = [...type.options].some(o => o.value === selectedType) ? selectedType : '';
    const requested = Number(params.get('page'));
    page = Number.isSafeInteger(requested) && requested > 0 ? requested : 1;
  }

  function writeLocation() {
    const params = new URLSearchParams();
    if (query.value.trim()) params.set('q', query.value.trim().slice(0, MAX_QUERY));
    if (course.value) params.set('course', course.value);
    if (type.value) params.set('type', type.value);
    if (page > 1) params.set('page', String(page));
    const url = new URL(location.href);
    url.search = params.toString();
    try { history.replaceState(null, '', url); } catch (_) { /* Search remains usable without history access. */ }
  }

  function excerpt(record, terms) {
    const source = record.text.replace(/\s+/gu, ' ').trim();
    if (!source) return 'Open this resource to read more.';
    const folded = fold(source);
    const offsets = terms.map(term => folded.indexOf(term)).filter(index => index >= 0);
    const position = offsets.length ? Math.min(...offsets) : 0;
    let start = Math.max(0, position - 70);
    if (start) {
      const boundary = source.indexOf(' ', start);
      if (boundary >= 0 && boundary < start + 30) start = boundary + 1;
    }
    return (start ? '…' : '') + source.slice(start, start + 260) + (source.length > start + 260 ? '…' : '');
  }

  function render(focus = false) {
    const pages = Math.max(1, Math.ceil(matches.length / PAGE_SIZE));
    page = Math.max(1, Math.min(page, pages));
    writeLocation();
    results.replaceChildren();
    const terms = fold(query.value.trim()).split(/\s+/u).filter(Boolean).slice(0, 12);
    const start = (page - 1) * PAGE_SIZE;
    results.start = start + 1;
    for (const {record} of matches.slice(start, start + PAGE_SIZE)) {
      const item = element('li', undefined, 'search-result');
      const title = element('h3');
      const link = element('a', record.title);
      link.href = record.href;
      title.append(link);
      item.append(element('p', `${courseNames.get(record.course) || record.course.replace(/_/gu, ' ')} · ${TYPE_LABELS[record.type] || record.type}`, 'search-result-meta'),
                  title, element('p', excerpt(record, terms), 'search-result-excerpt'));
      results.append(item);
    }
    if (!matches.length) {
      status.textContent = 'No results found. Try fewer keywords, a different spelling, or choose all courses and resource types.';
    } else {
      const total = matches.length.toLocaleString();
      const context = query.value.trim() ? ` for “${query.value.trim()}”` : '';
      status.textContent = `Showing ${(start + 1).toLocaleString()}–${Math.min(start + PAGE_SIZE, matches.length).toLocaleString()} of ${total} results${context}.`;
    }
    pager.hidden = pages <= 1;
    previous.disabled = page <= 1;
    next.disabled = page >= pages;
    pageLabel.textContent = `Page ${page} of ${pages}`;
    if (focus) heading.focus();
  }

  function search(focus = false) {
    if (!records) return;
    retry.hidden = true;
    query.value = query.value.slice(0, MAX_QUERY);
    const phrase = fold(query.value.trim());
    const terms = [...new Set(phrase.split(/\s+/u).filter(Boolean))].slice(0, 12);
    if (!phrase && !course.value && !type.value) {
      results.replaceChildren();
      pager.hidden = true;
      status.textContent = 'Enter keywords or choose a course or resource type to begin.';
      page = 1;
      writeLocation();
      return;
    }
    matches = [];
    for (const record of records) {
      if (course.value && record.course !== course.value) continue;
      if (type.value && record.type !== type.value) continue;
      if (!terms.every(term => record.haystack.includes(term))) continue;
      let score = 0;
      if (phrase) {
        if (record.titleFold === phrase) score += 120;
        if (record.titleFold.includes(phrase)) score += 55;
        for (const term of terms) {
          if (record.titleFold.includes(term)) score += 12;
          if (record.courseFold.includes(term)) score += 5;
          if (record.textFold.includes(term)) score += 1;
        }
      }
      matches.push({record, score});
    }
    matches.sort((a, b) => b.score - a.score || a.record.order - b.record.order);
    render(focus);
  }

  async function loadIndex() {
    failed = false;
    records = null;
    retry.hidden = true;
    pager.hidden = true;
    results.replaceChildren();
    region.setAttribute('aria-busy', 'true');
    status.textContent = 'Loading searchable study resources…';
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 20000);
    try {
      const response = await fetch(new URL('assets/search-index.json', root), {signal: controller.signal, credentials: 'same-origin'});
      if (!response.ok) throw new Error('Index request failed');
      const data = await response.json();
      if (!data || !Array.isArray(data.records)) throw new Error('Invalid search index');
      const prepared = [];
      for (const entry of data.records) {
        if (!entry || !['title', 'text', 'course', 'type'].every(key => typeof entry[key] === 'string')) continue;
        const href = resultURL(entry.url);
        if (!href || !entry.title.trim()) continue;
        const titleFold = fold(entry.title), textFold = fold(entry.text);
        const courseFold = fold(courseNames.get(entry.course) || entry.course.replace(/_/gu, ' '));
        prepared.push({...entry, href, titleFold, textFold, courseFold,
                       haystack: `${titleFold}\n${courseFold}\n${textFold}`, order: prepared.length});
      }
      if (data.records.length && !prepared.length) throw new Error('No valid search records');
      records = prepared;
      // Keep exact catalog names from HTML; gracefully accept new public index labels.
      for (const slug of [...new Set(records.map(record => record.course))].sort()) {
        if (!courseNames.has(slug)) {
          const label = slug.replace(/_/gu, ' ');
          courseNames.set(slug, label);
          const option = element('option', label);
          option.value = slug;
          course.append(option);
        }
      }
      for (const key of [...new Set(records.map(record => record.type))].sort()) {
        if (![...type.options].some(option => option.value === key)) {
          const option = element('option', TYPE_LABELS[key] || key);
          option.value = key;
          type.append(option);
        }
      }
      if (!records.length) {
        status.textContent = 'No resources are indexed yet. Browse the study notes, questions or outlines below.';
        return;
      }
      search();
    } catch (_) {
      failed = true;
      status.textContent = 'Search could not load. Check your connection and try again, or browse the study resources below.';
      retry.hidden = false;
    } finally {
      clearTimeout(timer);
      region.setAttribute('aria-busy', 'false');
    }
  }

  form.addEventListener('submit', event => {
    event.preventDefault();
    page = 1;
    writeLocation();
    if (failed) loadIndex();
    else search();
  });
  [course, type].forEach(control => control.addEventListener('change', () => {
    page = 1;
    writeLocation();
    search();
  }));
  document.getElementById('search-clear').addEventListener('click', () => {
    query.value = '';
    course.value = '';
    type.value = '';
    page = 1;
    writeLocation();
    if (failed) loadIndex();
    else search();
    query.focus();
  });
  previous.addEventListener('click', () => { page -= 1; render(true); });
  next.addEventListener('click', () => { page += 1; render(true); });
  retry.addEventListener('click', loadIndex);
  window.addEventListener('popstate', () => { readLocation(); search(); });
  readLocation();
  loadIndex();
})();
