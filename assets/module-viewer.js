/* Lazy, self-hosted PDF rendering. No account, CDN, or server-side code. */
(async () => {
  const config = JSON.parse(document.getElementById('module-config').textContent);
  const status = document.getElementById('viewer-status');
  const canvas = document.getElementById('pdf-canvas');
  const stage = document.getElementById('pdf-stage');
  const pageInput = document.getElementById('page-number');
  const previous = document.getElementById('previous-page');
  const next = document.getElementById('next-page');
  const zoomInput = document.getElementById('pdf-zoom');
  if (location.protocol === 'file:') {
    status.textContent = 'Use “Open PDF” to read this file directly. The embedded reader works when this website is served over HTTP or HTTPS.';
    return;
  }
  let pdf, current = config.start_page || 1, desired = current, rendering = false, queued = false, lastPage;
  function lock(value) {
    stage.setAttribute('aria-busy', String(value));
    previous.disabled = value || current <= 1;
    next.disabled = value || !pdf || current >= pdf.numPages;
    pageInput.disabled = value;
    zoomInput.disabled = value || !pdf;
  }
  async function render() {
    if (rendering) { queued = true; return; }
    rendering = true; queued = false; lock(true);
    const number = desired;
    status.textContent = 'Loading page ' + number + '…';
    try {
      const page = await pdf.getPage(number);
      const natural = page.getViewport({ scale: 1 });
      const width = Math.max(220, stage.clientWidth - 32);
      const scale = (width / natural.width) * Number(zoomInput.value);
      const viewport = page.getViewport({ scale });
      const density = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = Math.ceil(viewport.width * density);
      canvas.height = Math.ceil(viewport.height * density);
      canvas.style.width = viewport.width + 'px';
      canvas.style.height = viewport.height + 'px';
      await page.render({ canvasContext: canvas.getContext('2d'), viewport, transform: density === 1 ? null : [density, 0, 0, density, 0, 0] }).promise;
      if (lastPage && lastPage !== page) lastPage.cleanup();
      lastPage = page; current = number;
      pageInput.value = String(number);
      canvas.setAttribute('aria-label', config.course + ' module, page ' + number + ' of ' + pdf.numPages);
      canvas.dataset.renderedPage = String(number);
      document.getElementById('page-total').textContent = String(pdf.numPages);
      status.textContent = 'Page ' + number + ' of ' + pdf.numPages;
      stage.scrollTop = 0;
    } catch (error) {
      status.textContent = 'This page could not be previewed. You can still open or download the original PDF.';
      canvas.dataset.error = 'true';
      console.error('PDF page preview:', error.message);
    } finally {
      rendering = false; lock(false);
      if (queued || desired !== current) { queued = false; if (!canvas.dataset.error) render(); }
    }
  }
  function go(number) {
    const requested = Number(number);
    if (!Number.isInteger(requested)) { pageInput.value = String(current); return; }
    desired = Math.max(1, Math.min(pdf.numPages, requested));
    delete canvas.dataset.error;
    render();
  }
  try {
    const pdfjs = await import('./pdfjs/pdf.mjs');
    pdfjs.GlobalWorkerOptions.workerSrc = new URL('./pdfjs/pdf.worker.mjs', import.meta.url).href;
    pdf = await pdfjs.getDocument({
      url: new URL(config.file, document.baseURI).href,
      cMapUrl: new URL('./pdfjs/cmaps/', import.meta.url).href,
      cMapPacked: true,
      standardFontDataUrl: new URL('./pdfjs/standard_fonts/', import.meta.url).href,
      wasmUrl: new URL('./pdfjs/wasm/', import.meta.url).href,
      isEvalSupported: false
    }).promise;
    pageInput.max = String(pdf.numPages);
    previous.addEventListener('click', () => go(current - 1));
    next.addEventListener('click', () => go(current + 1));
    pageInput.addEventListener('change', () => go(pageInput.value));
    pageInput.addEventListener('keydown', event => { if (event.key === 'Enter') go(pageInput.value); });
    zoomInput.disabled = false;
    zoomInput.addEventListener('change', () => { desired = current; render(); });
    let resizeTimer;
    window.addEventListener('resize', () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { render(); }, 180); });
    await render();
  } catch (error) {
    status.textContent = 'The embedded reader is unavailable. Use “Open PDF” or “Download PDF” above to access the original module.';
    stage.setAttribute('aria-busy', 'false');
    canvas.dataset.error = 'true';
    console.error('PDF reader:', error.message);
  }
})();
