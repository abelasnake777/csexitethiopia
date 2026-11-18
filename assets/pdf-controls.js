/* Lightweight, safe to inline before or after DOMContentLoaded. No PDF library here.
 * Main supplies window.CSExitSite = {root,config,page,courses:[{slug,title}]}.
 * API: CSExitPDF.mount(); CSExitPDF.open(kind, courseSlugOrArrayOrNull);
 *      CSExitPDF.cancel(); CSExitPDF.create(window, {site?,navigate?}).
 * Event on window OR document: cs:export, detail {kind,course}; null selects all.
 * Outside downloads: same-tab downloads.html?type=...&courses=...&generate=1.
 * CommonJS exports the factory for isolated tests. Loading/mounting is idempotent.
 */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) { module.exports = factory; return; }
  if (root.CSExitPDF) { root.CSExitPDF.mount(); return; }
  root.CSExitPDF = factory(root);
  root.CSExitPDF.create = factory;
  root.CSExitPDF.mount();
})(typeof window !== 'undefined' ? window : this, function createPDFControls(win, options) {
  'use strict';
  options = options || {};
  var doc = win.document, kinds = { questions: 'Questions and answers', notes: 'Complete study notes', outlines: 'Quick revision outlines' };
  var modal, form, list, toggle, count, confirm, heading, description, previousFocus, inertElements = [];
  var activeKind = 'questions', selected = [], pendingOpen, activeJob = null, sequence = 0;
  var catalogPromise, center, mountedCenter = false, listening = false, seenEvents = new WeakSet();
  var resultURL = null, lastRequest = null;
  function site() {
    return options.site || win.CSExitSite || { root: './', config: win.CS_EXIT_CONFIG || {}, page: {}, courses: [] };
  }
  function courses() {
    var found = new Set();
    return (site().courses || []).filter(function (course) {
      if (!course || !course.slug || found.has(course.slug)) return false;
      found.add(course.slug); return true;
    });
  }
  function resourceURL(path) {
    var base = new URL(site().root || './', win.location.href);
    var url = new URL(path, base);
    if (url.origin !== win.location.origin || !/^https?:$/.test(url.protocol)) throw new Error('PDF downloads must come from this website.');
    return url.href;
  }
  function isKind(value) { return Object.prototype.hasOwnProperty.call(kinds, value); }
  function element(tag, text, className) {
    var node = doc.createElement(tag);
    if (text) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function isDownloads() { return !!doc.querySelector('[data-cs-downloads]'); }
  function focusables() {
    return Array.from(modal.querySelectorAll('button:not([disabled]),input:not([disabled]),[href],[tabindex="0"]')).filter(function (node) { return !node.hidden; });
  }
  function restoreBackground() {
    inertElements.forEach(function (entry) { entry.node.inert = entry.inert; });
    inertElements = [];
    doc.documentElement.classList.remove('cs-pdf-modal-open');
  }
  function closeModal() {
    if (!modal || !modal.hasAttribute('open')) return;
    if (typeof modal.close === 'function') modal.close();
    else modal.removeAttribute('open');
    restoreBackground();
    if (previousFocus && previousFocus.isConnected && typeof previousFocus.focus === 'function') previousFocus.focus();
  }
  function updateCount() {
    var fields = Array.from(list.querySelectorAll('input[type="checkbox"]'));
    selected = fields.filter(function (field) { return field.checked; }).map(function (field) { return field.value; });
    count.textContent = selected.length + ' of ' + fields.length + ' courses selected';
    toggle.checked = selected.length > 0 && selected.length === fields.length;
    toggle.indeterminate = selected.length > 0 && selected.length < fields.length;
    confirm.disabled = selected.length === 0;
    confirm.textContent = isDownloads() ? 'Download PDF' : 'Continue to downloads';
  }
  function makeModal() {
    if (modal) return;
    modal = element('dialog', '', 'cs-pdf-dialog');
    modal.setAttribute('aria-modal', 'true'); modal.setAttribute('aria-labelledby', 'cs-pdf-dialog-title');
    modal.setAttribute('aria-describedby', 'cs-pdf-dialog-description'); modal.tabIndex = -1;
    var panel = element('div', '', 'cs-pdf-dialog-panel');
    var top = element('div', '', 'cs-pdf-dialog-top');
    heading = element('h2'); heading.id = 'cs-pdf-dialog-title';
    var close = element('button', 'Close', 'cs-pdf-button cs-pdf-secondary'); close.type = 'button';
    close.setAttribute('aria-label', 'Close course selection'); close.addEventListener('click', closeModal);
    top.append(heading, close);
    description = element('p', 'Choose the courses to include in one PDF. Each course starts on a new page.');
    description.id = 'cs-pdf-dialog-description';
    form = element('form');
    var allLabel = element('label', '', 'cs-pdf-course cs-pdf-select-all');
    toggle = element('input'); toggle.type = 'checkbox';
    allLabel.append(toggle, element('span', 'Select all courses'));
    var fieldset = element('div', '', 'cs-pdf-fieldset');
    fieldset.setAttribute('role', 'group'); fieldset.setAttribute('aria-label', 'Courses');
    list = element('div', '', 'cs-pdf-course-list');
    fieldset.append(list);
    count = element('p', '', 'cs-pdf-count'); count.setAttribute('role', 'status'); count.setAttribute('aria-live', 'polite');
    var actions = element('div', '', 'cs-pdf-dialog-actions');
    var cancelButton = element('button', 'Cancel', 'cs-pdf-button cs-pdf-secondary'); cancelButton.type = 'button'; cancelButton.addEventListener('click', closeModal);
    confirm = element('button', 'Continue to downloads', 'cs-pdf-button'); confirm.type = 'submit';
    actions.append(cancelButton, confirm);
    form.append(allLabel, fieldset, count, actions); panel.append(top, description, form); modal.append(panel); doc.body.append(modal);
    list.addEventListener('change', updateCount);
    toggle.addEventListener('change', function () {
      list.querySelectorAll('input').forEach(function (field) { field.checked = toggle.checked; }); updateCount();
    });
    form.addEventListener('submit', function (event) {
      event.preventDefault(); updateCount(); if (!selected.length) return;
      var choice = selected.slice(), kind = activeKind;
      closeModal();
      if (isDownloads()) { updateQuery(kind, choice); run(kind, choice); }
      else {
        var destination = new URL(resourceURL('downloads.html'));
        destination.searchParams.set('type', kind); destination.searchParams.set('courses', choice.join(',')); destination.searchParams.set('generate', '1');
        if (options.navigate) options.navigate(destination.href); else win.location.assign(destination.href);
      }
    });
    modal.addEventListener('cancel', function (event) { event.preventDefault(); closeModal(); });
    modal.addEventListener('close', restoreBackground);
    modal.addEventListener('click', function (event) {
      if (event.target !== modal) return;
      var bounds = modal.getBoundingClientRect();
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) closeModal();
    });
    modal.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { event.preventDefault(); closeModal(); return; }
      if (event.key !== 'Tab') return;
      var items = focusables(), first = items[0], last = items[items.length - 1];
      if (!items.length) { event.preventDefault(); modal.focus(); }
      else if (event.shiftKey && (doc.activeElement === first || doc.activeElement === modal)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && doc.activeElement === last) { event.preventDefault(); first.focus(); }
    });
    doc.addEventListener('focusin', function (event) {
      if (modal.hasAttribute('open') && !modal.contains(event.target)) { var first = focusables()[0]; if (first) first.focus(); }
    });
  }
  function open(kind, course) {
    if (!isKind(kind)) return false;
    if (!doc.body || doc.readyState === 'loading') { pendingOpen = [kind, course]; return true; }
    makeModal();
    activeKind = kind; heading.textContent = kinds[kind] + ' PDF';
    var available = courses();
    var initial = Array.isArray(course) ? course : (course ? [course] : available.map(function (item) { return item.slug; }));
    list.replaceChildren();
    available.forEach(function (item, i) {
      var label = element('label', '', 'cs-pdf-course');
      var field = element('input'); field.type = 'checkbox'; field.value = item.slug; field.id = 'cs-pdf-course-' + i; field.checked = initial.indexOf(item.slug) !== -1;
      label.append(field, element('span', item.title)); list.append(label);
    });
    description.textContent = available.length ? 'Choose the courses to include in one PDF. Each course starts on a new page.' : 'The course list is unavailable. Please reload this page and try again.';
    toggle.disabled = !available.length; updateCount();
    if (!modal.hasAttribute('open')) {
      previousFocus = doc.activeElement;
      // Native dialog supplies background isolation; inert also supports the fallback.
      if (typeof modal.showModal === 'function') modal.showModal(); else modal.setAttribute('open', '');
      Array.from(doc.body.children).forEach(function (node) {
        if (node !== modal && node.tagName !== 'SCRIPT' && node.tagName !== 'STYLE') { inertElements.push({ node: node, inert: node.inert }); node.inert = true; }
      });
      doc.documentElement.classList.add('cs-pdf-modal-open');
    }
    var first = list.querySelector('input:checked') || toggle;
    first.focus(); return true;
  }
  async function catalog() {
    if (!catalogPromise) {
      catalogPromise = win.fetch(resourceURL('assets/pdf/catalog.json'), { credentials: 'same-origin', cache: 'no-cache' }).then(function (response) {
        if (!response.ok) throw new Error('The PDF catalog is unavailable (HTTP ' + response.status + '). Please try again shortly.');
        return response.json();
      }).then(function (value) {
        if (!value || !Array.isArray(value.courses) || !value.courses.length || !value.all) throw new Error('The PDF catalog is incomplete. Please try again shortly.');
        return value;
      }).catch(function (error) { catalogPromise = null; throw error; });
    }
    return catalogPromise;
  }
  function status(message, percent) {
    if (!center) return;
    center.querySelector('[data-pdf-status]').textContent = message;
    var bar = center.querySelector('[data-pdf-progress]');
    bar.hidden = false;
    if (typeof percent === 'number') { bar.value = percent; bar.setAttribute('aria-valuetext', Math.round(percent) + '%'); }
    else { bar.removeAttribute('value'); bar.removeAttribute('aria-valuetext'); }
  }
  function busy(value) {
    center.querySelectorAll('[data-pdf-kind]').forEach(function (button) { button.disabled = value; });
    center.querySelector('[data-pdf-cancel]').hidden = !value;
    center.querySelector('[data-pdf-retry]').hidden = true;
    center.querySelector('[data-pdf-error]').hidden = true;
    center.querySelector('.cs-downloads-grid').setAttribute('aria-busy', String(value));
  }
  function cancel(silent) {
    if (!activeJob) return;
    var job = activeJob; activeJob = null;
    job.controller.abort(); if (job.worker) job.worker.terminate();
    if (center) {
      busy(false); center.querySelector('[data-pdf-progress]').hidden = true;
      if (!silent) { status('Download cancelled. Choose a resource to try again.'); center.querySelector('[data-pdf-progress]').hidden = true; }
    }
  }
  function updateQuery(kind, slugs) {
    var url = new URL(win.location.href);
    url.searchParams.set('type', kind); url.searchParams.set('courses', slugs.join(',')); url.searchParams.delete('generate');
    win.history.replaceState(null, '', url.href);
  }
  function releaseResult() {
    if (resultURL) { win.URL.revokeObjectURL(resultURL); resultURL = null; }
    if (center) center.querySelector('[data-pdf-result]').hidden = true;
  }
  function save(blob, filename, job) {
    if (activeJob !== job) return;
    releaseResult(); resultURL = win.URL.createObjectURL(blob);
    var link = center.querySelector('[data-pdf-result]');
    link.href = resultURL; link.download = filename; link.hidden = false;
    busy(false); status('Your PDF is ready. If the download did not start, use “Save PDF”.', 100);
    activeJob = null; link.click();
  }
  async function directDownload(path, filename, job) {
    var url = resourceURL(path);
    var fallback = center.querySelector('[data-pdf-direct]'); fallback.href = url; fallback.download = filename;
    status('Downloading the complete PDF...');
    var response = await win.fetch(url, { signal: job.controller.signal, credentials: 'same-origin' });
    if (!response.ok) throw new Error('The PDF could not be downloaded (HTTP ' + response.status + '). Please try again.');
    var size = Number(response.headers.get('content-length')) || 0, parts = [], loaded = 0;
    var blob;
    if (response.body && response.body.getReader) {
      var reader = response.body.getReader();
      try {
        while (true) {
          var part = await reader.read(); if (part.done) break;
          if (activeJob !== job) { await reader.cancel(); return; }
          parts.push(part.value); loaded += part.value.byteLength;
          status('Downloading PDF: ' + (loaded / 1048576).toFixed(1) + ' MB' + (size ? ' of ' + (size / 1048576).toFixed(1) + ' MB' : '') + '...', size ? Math.min(99, loaded / size * 100) : undefined);
        }
      } finally { reader.releaseLock(); }
      blob = new win.Blob(parts, { type: 'application/pdf' });
    } else blob = new win.Blob([await response.arrayBuffer()], { type: 'application/pdf' });
    if ((await blob.slice(0, 1024).text()).indexOf('%PDF-') === -1) throw new Error('The server did not return a PDF. Please try again shortly.');
    save(blob, filename, job);
  }
  function startWorker(kind, entries, filename, job) {
    if (!win.Worker) throw new Error('This browser cannot combine PDFs. Download one course or all courses, or use a newer browser.');
    var worker = new win.Worker(resourceURL('assets/pdf-merge-worker.js')); job.worker = worker;
    worker.onmessage = function (event) {
      if (activeJob !== job || !event.data || event.data.id !== job.id) return;
      var data = event.data;
      if (data.type === 'progress') status(data.message, data.progress);
      else if (data.type === 'complete') {
        worker.terminate(); job.worker = null;
        if (!(data.buffer instanceof ArrayBuffer)) { fail(new Error('The PDF merger returned an invalid file.'), job); return; }
        save(new win.Blob([data.buffer], { type: 'application/pdf' }), filename, job);
      } else if (data.type === 'error') fail(new Error(data.message || 'The PDFs could not be combined.'), job);
    };
    worker.onerror = function (event) { event.preventDefault(); fail(new Error('The PDF merger could not run. Please try again, or download one course at a time.'), job); };
    worker.onmessageerror = function () { fail(new Error('The PDF merger response could not be read. Please try again.'), job); };
    worker.postMessage({ type: 'merge', id: job.id, kind: kind, courses: entries, config: site().config || {} });
  }
  function fail(error, job) {
    if (activeJob !== job) return;
    if (job.worker) job.worker.terminate(); job.controller.abort(); activeJob = null;
    busy(false); status('Your PDF could not be prepared.'); center.querySelector('[data-pdf-progress]').hidden = true;
    var output = center.querySelector('[data-pdf-error]'); output.textContent = error.message || 'Please check your connection and try again.'; output.hidden = false;
    center.querySelector('[data-pdf-retry]').hidden = false;
    var fallback = center.querySelector('[data-pdf-direct]'); if (fallback.hasAttribute('href')) fallback.hidden = false;
  }
  async function run(kind, slugs) {
    if (!center) return;
    cancel(true); releaseResult();
    var job = { id: ++sequence, controller: new win.AbortController(), worker: null }; activeJob = job;
    lastRequest = { kind: kind, slugs: slugs.slice() };
    busy(true); status('Checking available PDFs...');
    var fallback = center.querySelector('[data-pdf-direct]'); fallback.hidden = true; fallback.removeAttribute('href');
    try {
      if (!isKind(kind)) throw new Error('Choose questions, notes or outlines.');
      var data = await catalog(); if (activeJob !== job) return;
      var wanted = new Set(slugs);
      var entries = data.courses.filter(function (course) { return wanted.has(course.slug); });
      if (!entries.length || entries.length !== wanted.size || entries.length > 16) throw new Error('Please choose valid courses and try again.');
      var all = entries.length === data.courses.length;
      var complete = all ? data.all[kind] : entries.length === 1 && entries[0].resources && entries[0].resources[kind];
      var filename = 'cs-exit-' + kind + '-' + (all ? 'all-courses' : entries.length === 1 ? entries[0].slug : entries.length + '-courses') + '.pdf';
      if (all || entries.length === 1) {
        if (!complete || !complete.download) throw new Error('This complete PDF is not available yet. Please try again shortly.');
        await directDownload(complete.download, filename, job);
      } else {
        var fragments = entries.map(function (course) {
          var resource = course.resources && course.resources[kind];
          if (!resource || !resource.fragment) throw new Error('The PDF for ' + course.title + ' is not available yet.');
          return { slug: course.slug, title: course.title, fragment: resourceURL(resource.fragment) };
        });
        status('Starting your selected-course PDF...', 0); startWorker(kind, fragments, filename, job);
      }
    } catch (error) { if (activeJob === job) fail(error, job); }
  }
  function exportEvent(event) {
    if (seenEvents.has(event)) return; seenEvents.add(event);
    var detail = event.detail || {};
    var course = Object.prototype.hasOwnProperty.call(detail, 'course') ? detail.course : (site().page || {}).course;
    open(detail.kind, course);
  }
  function mount() {
    if (!listening) {
      listening = true;
      win.addEventListener('cs:export', exportEvent); doc.addEventListener('cs:export', exportEvent);
      doc.addEventListener('DOMContentLoaded', mount, { once: true });
      win.addEventListener('pagehide', function () { cancel(true); closeModal(); releaseResult(); });
    }
    if (!doc.body || doc.readyState === 'loading') return api;
    if (pendingOpen) { var pending = pendingOpen; pendingOpen = null; open(pending[0], pending[1]); }
    center = doc.querySelector('[data-cs-downloads]');
    if (!center || mountedCenter) return api;
    mountedCenter = true;
    center.querySelectorAll('[data-pdf-kind]').forEach(function (button) {
      button.addEventListener('click', function (event) {
        // Main delegates the same attribute globally; this center owns its selection.
        event.stopPropagation();
        var params = new URL(win.location.href).searchParams;
        open(button.getAttribute('data-pdf-kind'), params.has('courses') ? params.get('courses').split(',').filter(Boolean) : null);
      });
    });
    center.querySelector('[data-pdf-cancel]').addEventListener('click', function () { cancel(); });
    center.querySelector('[data-pdf-retry]').addEventListener('click', function () { if (lastRequest) run(lastRequest.kind, lastRequest.slugs); });
    var params = new URL(win.location.href).searchParams;
    var kind = params.get('type'), requested = (params.get('courses') || '').split(',').filter(Boolean);
    if (params.get('generate') === '1') {
      // Remove the autorun marker so reload/back does not trigger another download.
      var cleaned = new URL(win.location.href); cleaned.searchParams.delete('generate'); win.history.replaceState(null, '', cleaned.href);
      run(kind, requested);
    }
    return api;
  }
  var api = { mount: mount, open: open, cancel: function () { cancel(); } };
  return api;
});
