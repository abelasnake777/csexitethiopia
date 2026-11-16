(() => {
  'use strict';
  const timers = new WeakMap();
  function fallbackCopy(value) {
    const field = document.createElement('textarea');
    field.value = value;
    field.readOnly = true;
    field.setAttribute('aria-hidden', 'true');
    Object.assign(field.style, { position: 'fixed', top: '0', left: '-9999px', fontSize: '16px' });
    const previous = document.activeElement;
    document.body.append(field);
    field.select();
    field.setSelectionRange(0, value.length);
    let copied = false;
    try { copied = document.execCommand('copy'); } finally {
      field.remove();
      if (previous && typeof previous.focus === 'function') previous.focus({ preventScroll: true });
    }
    return copied;
  }
  document.querySelectorAll('[data-copy]').forEach(button => {
    button.addEventListener('click', async () => {
      const status = button.parentElement.querySelector('.copy-status');
      clearTimeout(timers.get(button));
      let copied = false;
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(button.dataset.copy);
          copied = true;
        }
      } catch (_) { /* Normal clipboard denial uses the local fallback below. */ }
      if (!copied) {
        try { copied = fallbackCopy(button.dataset.copy); } catch (_) { copied = false; }
      }
      status.textContent = copied ? 'Copied!' : 'Copy manually';
      button.dataset.copied = String(copied);
      timers.set(button, setTimeout(() => { status.textContent = ''; delete button.dataset.copied; }, 2200));
    });
  });
})();
