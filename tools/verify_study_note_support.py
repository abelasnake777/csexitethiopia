#!/usr/bin/env python3
"""Validate every question's reading hint, explanation and literal note proof.

Editorial reviewers assess relevance. This checks their exact evidence against
real course sections and checks coverage, variants and preserved original text.
"""
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,re
from pathlib import Path
from verify_study_note_answers import Note,norm,require,PAYLOAD
from study_note_preservation import verify_base
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def verify():
 raw=(ROOT/'Complete_CS_Exit_Study_Guide.html').read_text();verify_base(raw);note=Note();note.feed(raw)
 d=json.loads((ROOT/'STUDY_NOTE_SUPPORT.json').read_text());rows={r['id']:r for r in d['questions']};seen=set();proof=variants=0;counts=Counter();revisions=0
 require(d['complete']and len(rows)==len(d['questions'])==3485,'Incomplete/duplicate support IDs')
 for path in sorted((ROOT/'Questions/Interactive_Study_Guides').glob('*.html')):
  m=PAYLOAD.search(path.read_text())
  if not m:continue
  model=json.loads(m[1])
  for item in model['questions']:
   q=item['question'];qid=q['id'];seen.add(qid);row=rows[qid];r=row['answer_review'];counts[path.stem]+=1
   require(row['slug']==path.stem and row['number']==q['question'],'Wrong support course/order '+qid)
   require(row.get('hint','').strip()and r['explanation'].strip()and r['answer_text'].strip(),qid+' empty hint/answer/explanation')
   require(row['section_ids']and row['evidence'],qid+' missing study-note proof')
   for sid in row['section_ids']:require(sid in note.sections and note.sections[sid]['course']==path.stem,qid+' missing/wrong-course section '+sid)
   def check(e,ids):
    require(e['section_id']in ids,qid+' evidence outside linked sections')
    quote=norm(e['quote']);require(len(quote)>=10 and quote in norm(''.join(note.sections[e['section_id']]['text'])),qid+' absent/short exact quote '+e['section_id']+' '+quote[:90])
   for e in row['evidence']:check(e,row['section_ids']);proof+=1
   require(len(row.get('variant_support',[]))==len(q.get('option_variants',[])),qid+' missing variant support')
   for v,source in zip(row.get('variant_support',[]),q.get('option_variants',[])):
    require(v['source']==source['source']and v['evidence']and v['section_ids'],qid+' variant source/proof')
    for sid in v['section_ids']:require(sid in row['section_ids'],qid+' variant ref absent from hint/answer')
    for e in v['evidence']:check(e,v['section_ids']);proof+=1
    variants+=1
   require(r['id']==qid and r['section_ids']==row['section_ids']and r['evidence']==row['evidence'],qid+' effective review disagreement')
   require(r['status']in ['answered','answered_multiple','answered_open'],qid+' unresolved answer')
   rev=r.get('question_revision');options=rev['options']if rev else q['options'];stem=rev['stem']if rev else q['stem'];labels=[o['label']for o in options]
   require([c['label']for c in r['choices']]==labels and all(c['explanation'].strip()for c in r['choices']),qid+' missing choice contrasts')
   require(set(r['labels'])<=set(labels),qid+' invalid key')
   for c in r['choices']:
    require(c['verdict']==('correct'if c['label']in r['labels']else'incorrect'),qid+' indefinite/contradictory choice '+c['label'])
   if r['status']=='answered':require(len(r['labels'])==1,qid+' no unique answer')
   if r['status']=='answered_multiple':require(len(r['labels'])>1 and re.search(r'\b(select|choose|identify|mark)\s+all\b',stem,re.I),qid+' select-all not explicit')
   if r['status']=='answered_open':require(not options and not r['labels'],qid+' invalid written answer')
   if rev:
    original_labels=[o['label']for o in q['options']]
    require(labels==original_labels or(not original_labels and rev.get('options_restored_from_embedded_stem')and re.findall(r'(?:^|\n)\s*([A-Z])[).]\s+',q['stem'])==labels),qid+' unproved source choice reconstruction')
    revisions+=1;require(rev['original_stem']==q['stem']and rev['original_options']==q['options']and rev['note']and rev['assumptions'],qid+' original practice revision provenance')
   require(len(r['variant_reviews'])==len(q.get('option_variants',[])),qid+' missing variant answers')
   for v in r['variant_reviews']:
    require(v['labels']and v['answer_text']and v['explanation']and all(c['explanation']for c in v['choices']),qid+' variant explanation')
    for c in v['choices']:require(c['verdict']==('correct'if c['label']in v['labels']else'incorrect'),qid+' indefinite variant choice '+c['label'])
 require(seen==set(rows)and len(counts)==16 and variants==24,'Unexpected bank coverage')
 require(all(f['resolved']for f in d['editorial_findings']),'Unresolved editorial finding')
 require(all(p['complete']and all(f['resolved']for f in p['findings'])for p in d.get('independent_spot_reviews',[])),'Unresolved independent finding')
 result={'passed':True,'generated_at':datetime.now(timezone.utc).isoformat(),'scope':d['scope'],'questions':len(seen),'courses':len(counts),'variants':variants,'literal_note_passages_checked':proof,'conceptual_sections_added':sum(len(c['additions'])for c in d['courses']),'editorial_findings_resolved':len(d['editorial_findings']),'independent_spot_review_unique_questions':len({qid for p in d.get('independent_spot_reviews',[])for qid in p['reviewed']}),'independent_spot_findings_resolved':sum(len(p['findings'])for p in d.get('independent_spot_reviews',[])),'clarified_practice_records':revisions,'study_guide_sha256':sha(raw.encode()),'support_data_sha256':sha((ROOT/'STUDY_NOTE_SUPPORT.json').read_bytes()),'existing_study_note_bytes_preserved':True,'course_counts':dict(counts)}
 (ROOT/'STUDY_NOTE_SUPPORT_AUDIT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2));return result
if __name__=='__main__':verify()
