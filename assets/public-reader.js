/* Student-facing language and accessible source attribution. */
(function () {
  'use strict';
  function createTextCleaner(rules) {
    const pairs = [...rules].filter(r => r.from && r.from !== r.to).sort((a,b) => b.from.length-a.from.length);
    const values = new Map(pairs.map(r => [r.from, r.to]));
    const escape = s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = pairs.length ? new RegExp(pairs.map(r => escape(r.from)).join('|'), 'g') : null;
    return text => {
      let value = String(text);
      if (pattern) for (let pass=0;pass<4;pass++) { const next=value.replace(pattern, key => values.get(key));if(next===value)break;value=next; }
      return value;
    };
  }
  if (typeof module !== 'undefined' && module.exports) { module.exports={createTextCleaner}; return; }
  function start() {
    const node=document.getElementById('public-reader-copy');if(!node)return;
    const config=JSON.parse(node.textContent),clean=createTextCleaner(config.replacements);
    const root=config.root||'./',make=(tag,text,cls)=>{const n=document.createElement(tag);if(text)n.textContent=text;if(cls)n.className=cls;return n;};
    const sourceLink=(title,href)=>{const a=make('a',title);a.setAttribute('href',href);a.target='_blank';a.rel='noopener';return a;};
    const modules=new Map(config.modules.map(m=>[m.slug,m]));
    function publicSources() {
      const data=document.getElementById('guide-data');if(!data)return;
      const model=JSON.parse(data.textContent),reviews=JSON.parse(document.getElementById('study-note-answer-data').textContent);
      for(const item of model.questions){
        const article=document.querySelector('article[data-question-id="'+item.question.id+'"]');if(!article)continue;
        article.querySelectorAll('.question-clarification,.provenance-file,.legacy-module-review').forEach(n=>n.remove());
        const aside=article.querySelector('.question-provenance'),list=aside?.querySelector('.provenance-list');
        if(list){
          const seen=new Set();list.replaceChildren();
          for(const source of item.provenance||[]){
            const title=config.source_titles[source.filename];if(!title)throw new Error('Missing public source title');
            const number=source.text.match(/\boriginal question\s+([A-Za-z]?\d+(?:[-–]\d+)?)/i);
            const label=title+(number?' · Question '+number[1]:'');if(seen.has(label))continue;seen.add(label);
            const li=make('li');li.append(make('p',label));list.append(li);
          }
          aside.querySelector('.provenance-title').textContent=reviews[item.question.id]?.question_revision?'Adapted from':seen.size>1?'Sources':'Source';
        }
        [...article.querySelectorAll(':scope>.variant')].forEach((n,i)=>n.textContent='Alternative version '+(i+1));
        [...article.querySelectorAll('.current-study-answer h3')].filter(n=>n.textContent.startsWith('Alternative source choices · ')).forEach((n,i)=>n.textContent='Alternative version '+(i+1));
      }
      for(const p of document.querySelectorAll('main>p.meta'))if(/Keep the original module PDFs|Question source labels use saved file records/.test(p.textContent))p.textContent='Read the linked study-guide sections before revealing the answer. PDF page references count from the first page of the document.';
    }
    function readingSources() {
      const refs=document.getElementById('references');if(!refs)return;
      const index=new Map(),external=[],publications=[];
      for(const item of refs.querySelectorAll('.reference-list>li')){
        const strong=item.querySelector('strong');if(!strong)continue;
        const parts=strong.textContent.split(' · '),id=parts.shift(),title=parts.join(' · ')||id;
        if(id==='BP')publications.push(clean(title));
        const links=[...item.querySelectorAll('a[href^="https://"]')];
        if(links.length){const entries=links.map(a=>({title:clean(title),href:a.getAttribute('href')}));index.set(id,entries);external.push(...entries);}
        else{
          const matching=config.modules.filter(m=>item.textContent.includes(m.source_file));
          if(matching.length)index.set(id,matching.map(m=>({title:m.course+' module',href:root+'Modules/'+m.slug+'.html'})));
        }
      }
      for(const note of document.querySelectorAll('article[id^="course-"] li.sources')){
        if(note.querySelector('a'))continue;
        const match=note.textContent.match(/^\s*References:\s*(.*)$/);if(!match)continue;
        const course=note.closest('article').id.slice(7),items=match[1].split(/,\s*/).flatMap(id=>index.get(id.trim())||[]);
        if(!items.length&&modules.has(course))items.push({title:modules.get(course).course+' module',href:root+'Modules/'+course+'.html'});
        note.replaceChildren(make('span','Further reading: ','cue-text'));
        const list=make('ul','','detail-list'),seen=new Set();for(const item of items){if(seen.has(item.href))continue;seen.add(item.href);const li=make('li');li.append(sourceLink(item.title,item.href));list.append(li);}note.append(list);
      }
      refs.replaceChildren(make('h2','References & further reading'),make('p','Use the course modules and these references to explore topics in more detail.'));
      const list=make('ul','','reference-list'),seen=new Set();
      for(const title of publications)list.append(make('li',title));
      for(const m of config.modules){const li=make('li');li.append(sourceLink(m.course+' — course module',root+'Modules/'+m.slug+'.html'));list.append(li);}
      for(const item of external){if(seen.has(item.href))continue;seen.add(item.href);const li=make('li');li.append(sourceLink(item.title,item.href));list.append(li);}refs.append(list);
    }
    function visit(rootNode) {
      const walker=document.createTreeWalker(rootNode,NodeFilter.SHOW_TEXT);let n;
      while((n=walker.nextNode())){
        if(!n.parentElement||n.parentElement.closest('script,style,pre,code,textarea,.stem,.choices,.variant-clarified-stem'))continue;
        const value=clean(n.data);if(value!==n.data)n.data=value;
      }
      if(rootNode.nodeType===Node.TEXT_NODE&&rootNode.parentElement&&!rootNode.parentElement.closest('script,style,pre,code,textarea,.stem,.choices'))rootNode.data=clean(rootNode.data);
      const scope=rootNode.querySelectorAll?rootNode:rootNode.parentElement;
      if(scope){
        scope.querySelectorAll('a[href$=".pdf"],a[href*=".pdf#"],a[href$=".docx"]').forEach(a=>{
          if(a.closest('.stem,.choices'))return;
          const href=decodeURIComponent(a.getAttribute('href'));
          const matches=config.modules.filter(m=>m.file&&href.includes('Modules/'+m.file));
          if(matches.length){const slug=a.closest('article[id^="course-"]')?.id.slice(7)||config.course;const m=matches.find(m=>m.slug===slug)||matches[0],page=href.match(/#page=(\d+)/);a.textContent=m.course+' module'+(page?' · page '+page[1]:'');}
          else a.textContent=a.textContent.replace(/\.(?:pdf|docx)\b/gi,'').replace(/\s*·\s*PDF page\s*/i,' · page ');
        });
        scope.querySelectorAll('a[href]').forEach(a=>{if(/(?:SOURCE_MANIFEST|QUESTION_REFERENCE_AUDIT|STUDY_NOTE_(?:ANSWER_REVIEW|SUPPORT(?:_AUDIT)?)|ANSWER_COMPLETENESS_AUDIT|VERIFICATION|Outline_Coverage_Audit|PUBLIC_READER_COPY)\.json|ANSWER_REVIEW_SUMMARY\.html/.test(a.getAttribute('href')))a.remove();});
        scope.querySelectorAll('#results .result>h3').forEach(n=>n.textContent=n.textContent.split(' · ').slice(0,2).join(' · '));
        scope.querySelectorAll('#results details>summary').forEach(n=>n.textContent='Show answer & explanation');
        scope.querySelectorAll('p').forEach(p=>{if(!p.textContent.trim()&&!p.children.length)p.remove();});
      }
    }
    publicSources();readingSources();
    for(const selector of config.remove_selectors||[])document.querySelectorAll(selector).forEach(n=>n.remove());
    visit(document);
    window.CSExitPublicCopy={clean};
    const observer=new MutationObserver(records=>{
      observer.disconnect();
      const added=new Set();for(const r of records){if(r.type==='characterData')added.add(r.target);for(const n of r.addedNodes)if(n.isConnected)added.add(n);}
      for(const n of added)if(n.isConnected)visit(n);
      observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    });
    observer.observe(document.body,{subtree:true,childList:true,characterData:true});
    document.documentElement.dataset.publicReader='ready';
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();
