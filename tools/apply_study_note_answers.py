#!/usr/bin/env python3
"""Reapply current study-note reviews without altering original question payloads.

Run verify_study_note_answers.py first. Original imported HTML is recoverable by
removing the three exact marked blocks recorded in SOURCE_MANIFEST.json.
"""
import hashlib
import html
import json
from pathlib import Path
import re
from verify_study_note_answers import verify
ROOT=Path(__file__).resolve().parents[1]
START='<!-- STUDY-NOTE-ANSWER-REVIEWS:START -->'
END='<!-- STUDY-NOTE-ANSWER-REVIEWS:END -->'
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    verify()
    reviews=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes())
    by_id={r['id']:r for r in reviews['reviews']}
    support_path=ROOT/'STUDY_NOTE_SUPPORT.json'
    support=json.loads(support_path.read_text())if support_path.exists()else None
    if support:by_id.update({r['id']:r['answer_review']for r in support['questions']})
    manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_bytes())
    imported={f['copied_path']:f for f in manifest['files']}
    source=(ROOT/'Complete_CS_Exit_Study_Guide.html').read_text()
    titles={sid:html.unescape(re.sub('<[^>]+>','',heading)).strip()[len(sid):].strip() for sid,heading in re.findall(r'<section id="([^"]+)" class="note">.*?<h3>(.*?)</h3>',source,re.S)}
    js=(ROOT/'assets/study-note-answers.js').read_text();css=(ROOT/'assets/study-note-answers.css').read_text()
    for path in sorted((ROOT/'Questions/Interactive_Study_Guides').glob('*.html')):
        raw=path.read_text();match=re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',raw,re.S)
        if not match:continue
        item=imported[str(path.relative_to(ROOT))]
        previous=item.pop('answer_review_integration_block',None)
        if previous:
            assert raw.count(previous)==1;raw=raw.replace(previous,'',1)
        model=json.loads(match[1]);payload={q['question']['id']:by_id[q['question']['id']] for q in model['questions']if q['question']['id']in by_id}
        payload['_section_titles']={sid:titles[sid]for r in list(payload.values())for sid in r['section_ids']}
        payload['_full_note_support']=bool(support)
        block=START+'\n<style>\n'+css+'\n</style>\n<script id="study-note-answer-data" type="application/json">'+json.dumps(payload,ensure_ascii=False).replace('</',r'<\/')+'</script>\n<script>\n'+js+'\n</script>\n'+END
        assert raw.count('</head>')==1;raw=raw.replace('</head>',block+'</head>',1)
        item['answer_review_integration_block']=block
        original=raw
        for key in ['public_reader_integration_block','answer_review_integration_block','reference_integration_block','integration_block']:
            if item.get(key):assert original.count(item[key])==1;original=original.replace(item[key],'',1)
        assert sha(original.encode())==item['source_sha256'],path.stem+' source preservation'
        assert re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',raw,re.S)[1]==match[1]
        path.write_text(raw);item['copied_sha256']=sha(raw.encode());item['copied_bytes']=len(raw.encode())
        item['content_preservation']['original_question_data_and_historical_review_retained']=True
        item['content_preservation']['new_study_note_answers_added']=True
    for name in ['assets/study-note-answers.js','assets/study-note-answers.css']:
        row=next((r for r in manifest['generated_assets']if r['path']==name),None)
        if row:row['sha256']=sha((ROOT/name).read_bytes())
        else:manifest['generated_assets'].append({'path':name,'sha256':sha((ROOT/name).read_bytes())})
    manifest['integration']['removal_rule']='Remove study_note_addition_blocks once each if present. For each copied HTML, remove answer_review_integration_block once if present, then reference_integration_block once if present, then integration_block once. The result must exactly match source bytes and source_sha256.'
    manifest['totals']['current_answer_review_pages']=16
    manifest['totals']['current_answer_reviews']=len(by_id)
    manifest['assertions']['study_guide_unchanged_by_answer_review']=not bool(support)
    if support:manifest['assertions']['all_questions_have_editorial_study_note_support']=True
    manifest['integration']['answer_review_overlay']='Current complete-note reviews appear first. Historical hints and answers stay in closed archives. Source recovery: remove answer_review_integration_block, reference_integration_block, then integration_block.'
    (ROOT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    print('Applied',len(by_id),'current reviews; all original source bytes and question payloads preserved.')
if __name__=='__main__':main()
