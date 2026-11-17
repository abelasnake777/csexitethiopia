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
      const item = items.get(article.dataset.questionId);
      if (!review) {
        // Earlier verified variants sometimes state correctness only inside their
        // choice analysis. Give each version its own explicit answer heading.
        const answerBlock = article.querySelectorAll(':scope > details.reveal')[1];
        const headings = [...answerBlock.querySelectorAll('h3')].filter(n => n.textContent.startsWith('Alternative choices · '));
        for (const [index, variant] of (item.question.option_variants || []).entries()) {
          const analysis = (item.review.alternative_choice_analysis || [])[index];
          if (!analysis || !headings[index]) continue;
          const choices = analysis.choice_analysis || analysis.analysis || [];
          const labels = analysis.labels || analysis.answer_labels || choices.filter(c => c.verdict === 'correct').map(c => c.label);
          if (!labels.length) throw new Error('Missing verified variant answer: ' + article.dataset.questionId);
          headings[index].textContent = 'Alternative source choices · ' + variant.source;
          const text = labels.map(label => variant.options.find(o => o.label === label)?.text || label).join('; ');
          const title = el('p', (labels.length > 1 ? 'Correct answers: ' : 'Correct answer: ') + labels.join(', ') + ' — ' + text, 'answer-title explicit-variant-answer');
          title.dataset.variantSource = variant.source; headings[index].after(title);
        }
        continue;
      }
      if (review.question_revision) {
        const revision = review.question_revision;
        const stem = article.querySelector(':scope > .stem');
        stem.textContent = revision.stem;
        const options = article.querySelector(':scope > .choices');
        options.replaceChildren(...revision.options.map(option => el('li', option.label + '. ' + option.text, 'choice')));
        stem.after(el('p', revision.note, 'question-clarification'));
        for (const variant of revision.variant_revisions || []) {
          const heading = [...article.querySelectorAll(':scope > .variant')].find(n => n.textContent === 'Alternative source choices · ' + variant.source);
          if (!heading) throw new Error('Missing source variant: ' + article.dataset.questionId + ' ' + variant.source);
          const list = heading.nextElementSibling;
          const variantStem = el('p', variant.stem, 'stem variant-clarified-stem'); variantStem.dataset.variantSource = variant.source;
          heading.after(variantStem);
          list.replaceChildren(...variant.options.map(option => el('li', option.label + '. ' + option.text, 'choice')));
        }
        article.dataset.questionClarified = 'true';
        // Keep the existing reader search in sync with the clarified display.
        if (typeof searchable !== 'undefined') {
          const entry = searchable.find(entry => entry.article === article);
          if (entry) entry.text = [article.dataset.questionId, revision.stem, ...revision.options.map(o => o.text), ...(revision.variant_revisions || []).flatMap(v => [v.stem, ...v.options.map(o => o.text)])].join(' ').toLocaleLowerCase();
        }
      }
      const blocks = article.querySelectorAll(':scope > details.reveal');
      const hint = blocks[0].querySelector('.reveal-content') || blocks[0].querySelector('.reveal-body') || [...blocks[0].children].find(c => c.tagName !== 'SUMMARY');
      const answer = blocks[1].querySelector('.reveal-content') || blocks[1].querySelector('.reveal-body') || [...blocks[1].children].find(c => c.tagName !== 'SUMMARY');
      if (!hint || !answer) throw new Error('Missing question reveal body: ' + article.dataset.questionId);
      const sectionIDs = reviews._full_note_support ? review.section_ids : [...new Set([...(item.guide?.section_ids || []), ...review.section_ids])];
      const existingHint = [...hint.querySelectorAll('a[href*="Complete_CS_Exit_Study_Guide.html#"]')];
      let hintAnchor;
      if (reviews._full_note_support) {
        // The current editorial mapping supersedes the original keyword map.
        // Keep source JSON intact; show only reviewed reading targets here.
        for (const a of existingHint) a.closest('p')?.remove();
        hintAnchor = [...hint.querySelectorAll('h3')].find(n => n.textContent === 'Unified study note');
      } else hintAnchor = existingHint.at(-1)?.closest('p');
      for (const id of sectionIDs.filter(id => reviews._full_note_support || !(item.guide?.section_ids || []).includes(id))) {
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
      const prefix = review.status === 'answered' ? 'Correct answer: ' : review.status === 'answered_multiple' ? 'Correct answers (select all): ' : review.status === 'answered_open' ? 'Answer: ' : review.status === 'no_valid_option' ? 'Supported answer absent from the choices: ' : review.status === 'multiple_answers' ? 'Multiple valid answers: ' : review.status === 'ambiguous' ? 'Answer depends on interpretation: ' : review.status === 'incomplete_question' ? 'Question data incomplete: ' : 'Additional study reference needed: ';
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
        const variantTitle = el('p', (variant.labels.length > 1 ? 'Correct answers (select all): ' : 'Correct answer: ') + (variant.labels.length ? variant.labels.join(', ') + ' — ' : '') + variant.answer_text, 'variant-answer-title'); variantTitle.dataset.variantSource = variant.source; primary.append(variantTitle);
        primary.append(el('p', variant.explanation));
        const support = (review.variant_support || []).find(v => v.source === variant.source);
        for (const e of support?.evidence || []) { const p = el('p', e.quote, 'current-variant-evidence'); p.dataset.variantSource = variant.source; p.append(el('cite', e.section_id)); primary.append(p); }
        for (const choice of variant.choices) primary.append(el('p', choice.label + ' · ' + choice.verdict + ' — ' + choice.explanation));
      }
      answer.append(primary, archive);
      article.dataset.studyNoteAnswer = review.status;
    }
    const footer = document.querySelector('main > footer');
    if (footer) {
      footer.textContent = 'Every practice question has a reading hint, answer, explanation and cited study-note evidence. Necessary conceptual lessons have been added to the complete note. Earlier source reviews remain in closed archives. Clarified practice wording is labeled and original source data is retained. ';
      const report = el('a', 'Answer review summary'); report.href = '../../ANSWER_REVIEW_SUMMARY.html'; footer.append(report);
    }
    const closeArchives = () => document.querySelectorAll('.legacy-module-review').forEach(d => d.open = false);
    window.addEventListener('pageshow', closeArchives);
    document.getElementById('hide-all')?.addEventListener('click', closeArchives);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', enhance, {once: true});
  else enhance();
})();
