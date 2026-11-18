#!/usr/bin/env python3
"""Apply reviewed conceptual lessons and all-question study-note support.

Input STUDY_NOTE_SUPPORT.json is the saved per-question editorial audit. No
original question payload, original guide prose or original source is rewritten.
"""
import hashlib,html,json,re
from pathlib import Path
from urllib.parse import quote
from study_note_preservation import strip_additions,BASE_SHA256
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def esc(s):return html.escape(str(s),quote=True)
def js(v):return json.dumps(v,ensure_ascii=False).replace('</',r'<\/')
def main():
    support=json.loads((ROOT/'STUDY_NOTE_SUPPORT.json').read_text())
    manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
    entry=next(f for f in manifest['files'] if f['copied_path']=='Complete_CS_Exit_Study_Guide.html')
    raw=strip_additions((ROOT/entry['copied_path']).read_text(),manifest)
    assert sha(raw.encode())==BASE_SHA256
    entry.pop('public_reader_integration_block',None)
    catalog=json.loads((ROOT/'Modules/catalog.json').read_text())['courses']
    modules={x['source_file']:x for x in catalog};blocks=[];new_titles={}
    for c in support['courses']:
        lessons=[]
        for a in c['additions']:
            sid=a['id'];new_titles[sid]=a['title']
            rows=['<li><span class="cue-text">'+esc(t)+'</span></li>' for t in a.get('paragraphs',[])+a.get('bullets',[])]
            if a.get('table'):
                t=a['table'];rows.append('<li><div style="overflow-x:auto"><table><thead><tr>'+''.join('<th scope="col">'+esc(v)+'</th>'for v in t['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+esc(v)+'</td>'for v in row)+'</tr>'for row in t['rows'])+'</tbody></table></div></li>')
            refs=[]
            for s in a.get('sources',[]):
                href=s.get('url')
                if not href:
                    assert s['module']in modules,(sid,s)
                    href='Modules/'+quote(modules[s['module']]['file'],safe='/')+'#page='+str(s['pdf_page'])
                assert href.startswith(('https://','Modules/'))
                refs.append('<li><a href="'+esc(href)+'" target="_blank" rel="noopener">'+esc(s['title'])+'</a></li>')
            if refs:rows.append('<li class="sources"><span class="cue-text">Sources and further reading</span><ul class="detail-list">'+''.join(refs)+'</ul></li>')
            lessons.append('<li class="topic-node"><section id="'+esc(sid)+'" class="note"><details class="topic-details" open=""><summary><h3><span class="sid">'+esc(sid)+'</span> '+esc(a['title'])+'</h3></summary><ul class="cue-list">'+''.join(rows)+'</ul></details></section></li>')
        if lessons:
            block='<!-- STUDY-NOTE-SUPPORT:'+c['slug']+':START -->'+''.join(lessons)+'<!-- STUDY-NOTE-SUPPORT:'+c['slug']+':END -->'
            start=raw.index('<article id="course-'+c['slug']+'"');end=raw.index('</article>',start)
            before=raw[:end];assert before.endswith('</ul></details>')
            offset=end-len('</ul></details>');raw=raw[:offset]+block+raw[offset:];blocks.append(block)
    # Keep the original embedded reading index as a historical snapshot, then
    # update the live in-memory lookup to the current active practice versions.
    answer_reviews=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_text());reviews={r['id']:r for r in answer_reviews['reviews']}
    updates={}
    for r in support['questions']:
        out={'section_ids':r['section_ids'],'note':'Read the linked study-note sections, then apply their rules before revealing the answer.','status':'covered'}
        review=r['answer_review'];revision=review.get('question_revision')
        if revision:out.update(stem=revision['stem'],options=revision['options'])
        if review:out['answer']=(', '.join(review['labels'])+' — 'if review['labels']else'')+review['answer_text']+' '+review['explanation']
        updates[r['id']]=out
    block='<!-- STUDY-NOTE-SUPPORT:LOOKUP:START --><script id="study-note-support-lookup" type="application/json">'+js({'updates':updates,'titles':new_titles})+'</script><script>(()=>{const support=JSON.parse(document.getElementById("study-note-support-lookup").textContent);for(const row of data){const update=support.updates[row.id];if(update)Object.assign(row,update)}Object.assign(names,support.titles);if(document.getElementById("query").value.trim())find();})();</script><!-- STUDY-NOTE-SUPPORT:LOOKUP:END -->'
    raw=raw.replace('</body>',block+'</body>',1);blocks.append(block)
    entry['study_note_addition_blocks']=blocks
    restored=raw
    for b in blocks:assert restored.count(b)==1;restored=restored.replace(b,'',1)
    assert sha(restored.encode())==BASE_SHA256
    (ROOT/entry['copied_path']).write_text(raw)
    entry['copied_sha256']=sha(raw.encode());entry['copied_bytes']=len(raw.encode())
    entry['content_preservation']['existing_guide_bytes_preserved_before_authorized_additions']=True
    entry['content_preservation']['authorized_conceptual_support_sections_added']=len(new_titles)
    entry['content_preservation']['pre_addition_website_sha256']=BASE_SHA256
    manifest['assertions']['study_guide_unchanged_by_answer_review']=False
    manifest['assertions']['study_guide_existing_content_preserved_with_authorized_additions']=True
    manifest['integration']['removal_rule']='First remove any study_note_addition_blocks exactly once each. Then remove answer_review_integration_block, reference_integration_block and integration_block once if present. The recovered bytes must match each source_sha256.'
    (ROOT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    for review in answer_reviews['reviews']:
        row=next(r for r in support['questions']if r['id']==review['id'])
        review.update(row['answer_review'])
        review['section_ids']=row['section_ids'];review['evidence']=row['evidence']
        if row.get('hint'):review['hint']=row['hint']
        if review.get('basis')=='supplementary_reference':
            review['previous_basis']='supplementary_reference';review['basis']='study_note';review['resolved_note_gap']=review.pop('note_gap',None)
    from collections import Counter
    answer_reviews['statuses']=dict(Counter(r['status']for r in answer_reviews['reviews']))
    answer_reviews['study_guide_pre_addition_sha256']=BASE_SHA256
    answer_reviews.pop('study_guide_unchanged_sha256',None)
    answer_reviews['study_guide_sha256']=sha(raw.encode())
    answer_reviews['study_note_support']={'path':'STUDY_NOTE_SUPPORT.json','questions':len(support['questions']),'conceptual_sections_added':len(new_titles),'original_guide_content_retained':True}
    (ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').write_text(json.dumps(answer_reviews,ensure_ascii=False,indent=2)+'\n')
    print('Added',len(new_titles),'conceptual sections; preserved every original guide byte; linked',len(updates),'active questions.')
if __name__=='__main__':main()
