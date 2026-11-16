/* Resource hub navigation. Educational markup and original scripts remain untouched. */
(() => {
  'use strict';
  const script = document.currentScript;
  function mountNavigation() {
  if (!script || !document.body || document.querySelector('.resource-hub-nav')) return;
  const root = new URL(script.dataset.hubRoot || './', document.baseURI);
  const destinations = [
    ['Home', 'index.html'],
    ['Study guide', 'Complete_CS_Exit_Study_Guide.html'],
    ['Questions', 'Questions/Interactive_Study_Guides/index.html'],
    ['Outlines', 'Outlines/index.html'],
    ['How to study', 'index.html#how-to-study']
  ];
  const nav = document.createElement('nav');
  nav.className = 'resource-hub-nav';
  nav.setAttribute('aria-label', 'Study hub');
  const links = document.createElement('div');
  links.className = 'resource-hub-links';
  const current = new URL(window.location.href);
  for (const [label, path] of destinations) {
    const link = document.createElement('a');
    const target = new URL(path, root);
    link.className = 'resource-hub-link';
    link.setAttribute('href', (script.dataset.hubRoot || './') + path);
    link.textContent = label;
    if (!target.hash && target.pathname === current.pathname) {
      link.setAttribute('aria-current', 'page');
    }
    links.append(link);
  }
  nav.append(links);
  document.body.prepend(nav);
  // Only this simple index receives layout classes; retain every original node.
  if (script.dataset.resourceHubIndex === 'questions') {
    document.body.classList.add('resource-hub-questions-index');
    for (const child of document.body.children) {
      if (child.tagName === 'UL') child.classList.add('resource-hub-course-grid');
    }
  }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mountNavigation, { once: true });
  else mountNavigation();
})();
