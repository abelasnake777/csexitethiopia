/* Custom selections only. Official pdf-lib copyPages preserves vector text/fonts:
 * https://pdf-lib.js.org/docs/api/classes/pdfdocument#copypages
 * Input: {type:'merge', id, kind, courses:[{slug,title,fragment}], config}.
 * Output: progress | complete {id,buffer,pages,toc} | error {id,message}.
 * Cancel by terminating this worker; every completed buffer is transferred.
 */
(function (scope) {
  'use strict';
  var busy = false;
  var kinds = { questions: 'Practice questions and answers', notes: 'Complete study notes', outlines: 'Quick revision outlines' };
  function ascii(value) {
    return String(value || '').normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
      .replace(/[\u2010-\u2015]/g, '-').replace(/[\u2018\u2019]/g, "'")
      .replace(/[\u201c\u201d]/g, '"').replace(/[^\x20-\x7e]/g, ' ').replace(/\s+/g, ' ').trim();
  }
  function progress(id, value, message) {
    scope.postMessage({ type: 'progress', id: id, progress: Math.min(99, Math.round(value)), message: message });
  }
  function localPDF(path) {
    var url = new URL(path, scope.location.href);
    if (url.origin !== scope.location.origin || !/^https?:$/.test(url.protocol)) throw new Error('PDF fragments must be hosted on this website.');
    return url.href;
  }
  async function readFragment(url, update) {
    var response = await fetch(url, { credentials: 'same-origin' });
    if (!response.ok) throw new Error('A course PDF could not be loaded (HTTP ' + response.status + '). Please try again.');
    var size = Number(response.headers.get('content-length')) || 0;
    if (!response.body || !response.body.getReader) return response.arrayBuffer();
    var reader = response.body.getReader(), chunks = [], length = 0;
    try {
      while (true) {
        var part = await reader.read();
        if (part.done) break;
        chunks.push(part.value); length += part.value.byteLength;
        if (size) update(Math.min(1, length / size));
      }
    } finally { reader.releaseLock(); }
    var bytes = new Uint8Array(length), offset = 0;
    chunks.forEach(function (part) { bytes.set(part, offset); offset += part.length; });
    return bytes.buffer;
  }
  function wrap(text, font, size, width) {
    var words = ascii(text).split(' '), lines = [], line = '';
    words.forEach(function (word) {
      // Split unusually long tokens too, so metadata can never spill off a page.
      var token = '';
      Array.from(word).forEach(function (letter) {
        if (font.widthOfTextAtSize(token + letter, size) > width) { if (line) { lines.push(line); line = ''; } lines.push(token); token = ''; }
        token += letter;
      });
      if (font.widthOfTextAtSize(line ? line + ' ' + token : token, size) > width) { lines.push(line); line = token; }
      else line = line ? line + ' ' + token : token;
    });
    if (line) lines.push(line);
    return lines;
  }
  async function merge(data) {
    if (!Object.prototype.hasOwnProperty.call(kinds, data.kind)) throw new Error('Choose questions, notes or outlines.');
    if (!Array.isArray(data.courses) || data.courses.length < 2 || data.courses.length > 15) throw new Error('Custom PDFs need 2 to 15 courses. Use the complete PDF for all 16.');
    var seen = new Set();
    var courses = data.courses.map(function (course) {
      if (!course.slug || !course.title || seen.has(course.slug)) throw new Error('The course selection is invalid.');
      seen.add(course.slug);
      return { slug: course.slug, title: ascii(course.title), fragment: localPDF(course.fragment) };
    });
    progress(data.id, 1, 'Loading the PDF merger...');
    if (!scope.PDFLib) importScripts('vendor/pdf-lib/pdf-lib.min.js');
    var lib = scope.PDFLib;
    var pdf = await lib.PDFDocument.create();
    var font = await pdf.embedFont(lib.StandardFonts.Helvetica);
    var bold = await pdf.embedFont(lib.StandardFonts.HelveticaBold);
    var ink = lib.rgb(0.10, 0.18, 0.16), green = lib.rgb(0.12, 0.36, 0.28), muted = lib.rgb(0.30, 0.36, 0.34);
    var config = data.config || {}, brand = ascii(config.SITE_NAME || 'CS Exit Ethiopia');
    var today = new Date(), date = today.getFullYear() + '-' + String(today.getMonth() + 1).padStart(2, '0') + '-' + String(today.getDate()).padStart(2, '0');
    var label = kinds[data.kind];
    function text(page, value, x, y, size, face, color) {
      page.drawText(ascii(value), { x: x, y: y, size: size, font: face || font, color: color || ink });
    }
    function fitted(page, value, x, y, size, face, width, color) {
      var str = ascii(value), chosen = face || font;
      var measured = chosen.widthOfTextAtSize(str, size);
      text(page, str, x, y, measured > width ? size * width / measured : size, chosen, color);
    }
    function frontFooter(page) {
      fitted(page, config.SITE_URL, 46, 62, 9, font, 503, muted);
      fitted(page, 'Email: ' + ascii(config.EMAIL), 46, 48, 9, font, 503, muted);
      var handle = ascii(config.TELEGRAM).replace(/^https?:\/\/(?:t\.me|telegram\.me)\//, '').replace(/^@/, '');
      fitted(page, 'Telegram: ' + (handle ? 'https://t.me/' + handle : ''), 46, 34, 9, font, 503, muted);
    }
    var cover = pdf.addPage([595.28, 841.89]);
    fitted(cover, brand, 46, 781, 18, bold, 503, green);
    var titleLines = wrap(label, bold, 27, 503);
    titleLines.forEach(function (line, i) { text(cover, line, 46, 715 - i * 34, 27, bold); });
    text(cover, 'Selected course collection', 46, 626, 14, bold);
    text(cover, 'Prepared ' + date + '  |  ' + courses.length + ' courses', 46, 603, 11, font, muted);
    var coverSize = 11;
    function listHeight(size) { return courses.reduce(function (total, course, i) { return total + wrap((i + 1) + '. ' + course.title, font, size, 503).length * (size + 4) + 6; }, 0); }
    while (listHeight(coverSize) > 450 && coverSize > 7) coverSize -= 0.5;
    var y = 568;
    courses.forEach(function (course, i) {
      wrap((i + 1) + '. ' + course.title, font, coverSize, 503).forEach(function (line) { text(cover, line, 46, y, coverSize); y -= coverSize + 4; });
      y -= 6;
    });
    frontFooter(cover);
    // Reserve the TOC before importing, but compute its entries from actual pages.
    var contents = pdf.addPage([595.28, 841.89]), toc = [];
    for (var index = 0; index < courses.length; index++) {
      var course = courses[index];
      var base = 5 + index / courses.length * 78;
      progress(data.id, base, 'Loading ' + course.title + ' (' + (index + 1) + ' of ' + courses.length + ')...');
      var bytes = await readFragment(course.fragment, function (fraction) { progress(data.id, base + fraction * 55 / courses.length, 'Loading ' + course.title + '...'); });
      var source = await lib.PDFDocument.load(bytes);
      if (!source.getPageCount()) throw new Error('The PDF for ' + course.title + ' has no pages.');
      var start = pdf.getPageCount() + 1;
      // copyPages preserves the source page geometry, vector content and embedded Unicode fonts.
      var copied = await pdf.copyPages(source, source.getPageIndices());
      copied.forEach(function (page) { pdf.addPage(page); });
      toc.push({ slug: course.slug, title: course.title, start: start, pages: copied.length });
      bytes = null; source = null; copied = null;
      progress(data.id, 5 + (index + 1) / courses.length * 78, 'Added ' + course.title + '.');
    }
    text(contents, 'Contents', 46, 776, 26, bold, green);
    text(contents, 'Course', 46, 735, 11, bold);
    text(contents, 'Page', 521, 735, 11, bold);
    y = 704;
    var tocSize = 11;
    while (toc.reduce(function (total, entry) { return total + wrap(entry.title, font, tocSize, 450).length * (tocSize + 4) + 12; }, 0) > 570 && tocSize > 7) tocSize -= 0.5;
    toc.forEach(function (entry) {
      var lines = wrap(entry.title, font, tocSize, 450);
      lines.forEach(function (line, i) { text(contents, line, 46, y - i * (tocSize + 4), tocSize); });
      var number = String(entry.start);
      text(contents, number, 549 - font.widthOfTextAtSize(number, tocSize), y, tocSize, bold);
      y -= lines.length * (tocSize + 4) + 12;
    });
    frontFooter(contents);
    progress(data.id, 87, 'Adding page numbers...');
    var pages = pdf.getPages();
    pages.forEach(function (page, i) {
      var number = 'Page ' + (i + 1) + ' of ' + pages.length;
      var box = page.getMediaBox();
      var numberSize = Math.min(8, box.width / 30);
      text(page, number, box.x + (box.width - font.widthOfTextAtSize(number, numberSize)) / 2, box.y + 12, numberSize, font, muted);
    });
    pdf.setTitle(brand + ' - ' + label);
    pdf.setAuthor(brand);
    pdf.setSubject(courses.map(function (course) { return course.title; }).join('; '));
    pdf.setCreationDate(today); pdf.setModificationDate(today);
    progress(data.id, 94, 'Saving your PDF...');
    var result = await pdf.save();
    var buffer = result.buffer.slice(result.byteOffset, result.byteOffset + result.byteLength);
    scope.postMessage({ type: 'complete', id: data.id, buffer: buffer, pages: pages.length, toc: toc }, [buffer]);
  }
  scope.onmessage = function (event) {
    var data = event.data || {};
    if (data.type !== 'merge') return;
    if (busy) { scope.postMessage({ type: 'error', id: data.id, message: 'A PDF is already being prepared.' }); return; }
    busy = true;
    merge(data).catch(function (error) {
      scope.postMessage({ type: 'error', id: data.id, message: error.message || 'The selected PDFs could not be combined. Please try fewer courses.' });
    }).finally(function () { busy = false; });
  };
})(self);
