/* Keep local file previews useful without weakening browser file security. */
(() => {
  if (location.protocol === 'file:') {
    const config = JSON.parse(document.getElementById('module-config').textContent);
    const frame = document.createElement('iframe');
    frame.className = 'native-pdf-frame';
    frame.title = config.course + ' original PDF';
    frame.src = new URL(config.file, document.baseURI).href + '#page=' + config.start_page;
    document.querySelector('.pdf-controls').hidden = true;
    const stage = document.getElementById('pdf-stage');
    stage.replaceChildren(frame); stage.setAttribute('aria-busy', 'false');
    document.getElementById('viewer-status').textContent = 'Using your browser’s PDF viewer. Open PDF and Download PDF are also available above.';
    return;
  }
  const script = document.createElement('script');
  script.type = 'module';
  script.src = new URL('../assets/module-viewer.js', document.baseURI).href;
  script.onerror = () => { document.getElementById('viewer-status').textContent = 'Use Open PDF or Download PDF above to access this module.'; };
  document.head.append(script);
})();
