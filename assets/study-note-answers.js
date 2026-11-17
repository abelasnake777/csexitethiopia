/* Current answers are grounded in the expanded note; original module reviews stay archived. */
(() => {
  function enhance() {
    const dataNode = document.getElementById('study-note-answer-data');
    if (!dataNode) return;
    const reviews = JSON.parse(dataNode.textContent);
    const model = JSON.parse(document.getElementById('guide-data').textContent);
    const items = new Map(model.questions.map(item => [item.question.id, item]));
    const el = (tag, text, cls) => { const e = document.createElement(tag); if (text) e.textContent = text; if (cls) e.className = cls; return e; };
    const titles = reviews._section_titles || model.section_titles;
    const url = id => '../../Complete_CS_Exit_Study_Guide.html#' + encodeURIComponent(id);
    const link = id => { const a = el('a', id + ' · ' + (titles[id] || model.section_titles[id] || id)); a.href = url(id); a.target = '_blank'; a.rel = 'noopener'; return a; };
    for (const article of document.querySelectorAll('article.question')) {
      const review = reviews[article.dataset.questionId];
      if (!review) continue;
      const item = items.get(article.dataset.questionId);
      if (review.question_revision) {
        const revision = review.question_revision;
        const stem = article.querySelector(':scope > .stem');
        stem.textContent = revision.stem;
        const options = article.querySelector(':scope > .choices');
        options.replaceChildren(...revision.options.map(option => el('li', option.label + '. ' + option.text, 'choice')));
        stem.after(el('p', revision.note, 'question-clarification'));
        article.dataset.questionClarified = 'true';
        // Keep the existing reader search in sync with the clarified display.
        if (typeof searchable !== 'undefined') {
          const entry = searchable.find(entry => entry.article === article);
          if (entry) entry.text = [article.dataset.questionId, revision.stem, ...revision.options.map(o => o.text)].join(' ').toLocaleLowerCase();
        }
      }
      const blocks = article.querySelectorAll(':scope > details.reveal');
      const hint = blocks[0].querySelector('.reveal-content') || blocks[0].querySelector('.reveal-body') || [...blocks[0].children].find(c => c.tagName !== 'SUMMARY');
      const answer = blocks[1].querySelector('.reveal-content') || blocks[1].querySelector('.reveal-body') || [...blocks[1].children].find(c => c.tagName !== 'SUMMARY');
      if (!hint || !answer) throw new Error('Missing question reveal body: ' + article.dataset.questionId);
      const sectionIDs = [...new Set([...(item.guide?.section_ids || []), ...review.section_ids])];
      const existingHint = [...hint.querySelectorAll('a[href*="Complete_CS_Exit_Study_Guide.html#"]')];
      let hintAnchor = existingHint.at(-1)?.closest('p');
      for (const id of sectionIDs.filter(id => !(item.guide?.section_ids || []).includes(id))) {
        const p = el('p'); p.append(link(id));
        if (hintAnchor) hintAnchor.after(p); else hint.prepend(p);
        hintAnchor = p;
      }
      const hintArchive = el('details', '', 'legacy-module-review');
      hintArchive.append(el('summary', 'Earlier module references'));
      for (const child of [...hint.children]) {
        if (child.tagName === 'H3' && child.textContent === 'Unified study note') continue;
        if (child.querySelector('a[href*="Complete_CS_Exit_Study_Guide.html#"]')) continue;
        hintArchive.append(child);
      }
      hint.prepend(el('p', review.hint, 'current-note-reading'));
      for (const source of review.external_evidence || []) {
        const p = el('p', 'Additional reading: ');
        const a = el('a', source.title); a.href = source.url; a.target = '_blank'; a.rel = 'noopener'; p.append(a); hint.append(p);
      }
      hint.append(hintArchive);
      const guideHeading = [...answer.querySelectorAll('h3')].find(n => n.textContent === 'Unified note guidance');
      const referenceBox = answer.querySelector('.study-note-answer-references');
      if (!guideHeading || !referenceBox) throw new Error('Missing study-note reference container');
      const archive = el('details', '', 'legacy-module-review');
      archive.append(el('summary', 'Archived earlier answer review'));
      archive.append(el('p', 'This historical review may contain module limitations or unverified source keys. The current review above uses the complete study note.', 'meta'));
      for (const child of [...answer.children]) if (child !== guideHeading && child !== referenceBox) archive.append(child);
      referenceBox.replaceChildren(...sectionIDs.map(id => { const p = el('p'); p.append(link(id)); return p; }));
      const primary = el('section', '', 'current-study-answer');
      primary.dataset.reviewStatus = review.status;
      const prefix = review.status === 'answered' ? 'Correct answer: ' : review.status === 'answered_open' ? 'Answer: ' : review.status === 'no_valid_option' ? 'Supported answer absent from the choices: ' : review.status === 'multiple_answers' ? 'Multiple valid answers: ' : review.status === 'ambiguous' ? 'Answer depends on interpretation: ' : review.status === 'incomplete_question' ? 'Question data incomplete: ' : 'Additional study reference needed: ';
      primary.append(el('p', prefix + (review.labels.length ? review.labels.join(', ') + ' — ' : '') + review.answer_text, 'current-answer-title'));
      if (review.basis === 'supplementary_reference') primary.append(el('p', 'The complete note gives related background. The additional rule needed for this item is supplied below from an authoritative reference.', 'current-note-reading'));
      primary.append(el('p', review.explanation, 'current-answer-explanation'));
      if (review.evidence.length) {
        primary.append(el('h3', review.basis === 'supplementary_reference' ? 'Related background in the complete study note' : 'Evidence in the complete study note'));
        for (const e of review.evidence) { const block = el('blockquote', e.quote, 'current-note-evidence'); block.append(el('cite', e.section_id)); primary.append(block); }
      }
      if (review.external_evidence?.length) {
        primary.append(el('h3', 'Additional authoritative reference'));
        for (const source of review.external_evidence) {
          const box = el('div', '', 'current-supplement'); box.append(el('p', source.statement));
          const a = el('a', source.title); a.href = source.url; a.target = '_blank'; a.rel = 'noopener'; box.append(a); primary.append(box);
        }
      }
      if (review.choices.length) primary.append(el('h3', 'Choice by choice'));
      for (const choice of review.choices) {
        const p = el('p'); p.append(el('strong', choice.label + ' · ' + choice.verdict + ' — ')); p.append(document.createTextNode(choice.explanation)); primary.append(p);
      }
      for (const variant of review.variant_reviews || []) {
        primary.append(el('h3', 'Alternative source choices · ' + variant.source));
        primary.append(el('p', (variant.labels.length ? variant.labels.join(', ') + ' — ' : '') + variant.answer_text));
        primary.append(el('p', variant.explanation));
        for (const choice of variant.choices) primary.append(el('p', choice.label + ' · ' + choice.verdict + ' — ' + choice.explanation));
      }
      answer.append(primary, archive);
      article.dataset.studyNoteAnswer = review.status;
    }
    const footer = document.querySelector('main > footer');
    if (footer) {
      footer.textContent = 'Current answer reviews use the complete study note; earlier verified module explanations are retained. Historical source reviews remain available in closed archives. User-approved clarified practice wording is labeled; original source data is retained. Ambiguity, missing question data and genuine note gaps are identified explicitly. ';
      const report = el('a', 'Answer review summary'); report.href = '../../ANSWER_REVIEW_SUMMARY.html'; footer.append(report);
    }
    const closeArchives = () => document.querySelectorAll('.legacy-module-review').forEach(d => d.open = false);
    window.addEventListener('pageshow', closeArchives);
    document.getElementById('hide-all')?.addEventListener('click', closeArchives);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance, {once: true});
  else enhance();
})();
