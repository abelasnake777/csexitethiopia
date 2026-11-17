#!/usr/bin/env python3
"""Count definite answers for every displayed main question and source variant.

Coverage is separate from independent correctness review. Explicit select-all
questions count as answered; historical ambiguous single-choice items do not.
"""
from collections import Counter
from datetime import datetime,timezone
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RESOLVED={'answered','answered_multiple','answered_open','verified'}
SELECT_ALL=re.compile(r'\b(select|choose|identify|mark)\s+all\b',re.I)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def get_labels(a):
    labels=a.get('labels',a.get('answer_labels'))
    return labels if labels is not None else[c['label']for c in a.get('choices',a.get('choice_analysis',a.get('analysis',[])))if c.get('verdict')=='correct']
def answer_state(status,labels,answer_text,options,stem):
    if status not in RESOLVED:return False,status
    if status=='answered_open':return not options and not labels and bool(answer_text.strip()),'written'
    if not labels or not set(labels)<={o['label']for o in options}:return False,'missing/invalid answer label'
    if len(labels)>1 and not SELECT_ALL.search(stem):return False,'multiple answers without select-all wording'
    return bool(answer_text.strip()),'select_all'if len(labels)>1 else'single'
def verify(allow_pending=False):
    ledger=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes());reviews={r['id']:r for r in ledger['reviews']};support_path=ROOT/'STUDY_NOTE_SUPPORT.json'
    if support_path.exists():reviews.update({r['id']:r['answer_review']for r in json.loads(support_path.read_text())['questions']})
    rows=[];courses=[];variants=[];seen=set();prompt_groups={}
    for path in sorted((ROOT/'Questions/Interactive_Study_Guides').glob('*.html')):
        m=re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',path.read_text(),re.S)
        if not m:continue
        model=json.loads(m[1]);course=[]
        for item in model['questions']:
            q=item['question'];qid=q['id'];assert qid not in seen;seen.add(qid)
            current=reviews.get(qid);r=current or item['review']['answer'];status=current['status']if current else item['review']['status'];revision=r.get('question_revision',{});stem=revision.get('stem',q['stem']);options=revision.get('options',q['options']);labels=get_labels(r);answer_text=r.get('answer_text','')
            prompt_key=(re.sub(r'\s+',' ',stem).strip().lower(),tuple((o['label'],re.sub(r'\s+',' ',o['text']).strip().lower())for o in options));prompt_groups.setdefault(prompt_key,[]).append(qid)
            resolved,kind=answer_state(status,labels,answer_text,options,stem)
            row={'id':qid,'slug':path.stem,'course':model['course'],'number':q['question'],'resolved':resolved,'answer_kind':kind,'status':status,'labels':labels,'answer_text':answer_text,'clarified':bool(revision)};course.append(row);rows.append(row)
            declared=(r.get('variant_reviews',[])if current else item['review'].get('alternative_choice_analysis',[]));revisions=revision.get('variant_revisions',[])
            for index,v in enumerate(q.get('option_variants',[])):
                a=declared[index]if index<len(declared)else{};vr=revisions[index]if index<len(revisions)else{};ls=get_labels(a);vs=a.get('status','answered'if len(ls)==1 else'answered_multiple'if len(ls)>1 and SELECT_ALL.search(vr.get('stem',stem))else'unresolved');text=a.get('answer_text')or'; '.join(o['text']for o in vr.get('options',v['options'])if o['label']in ls)
                okay,vkind=answer_state(vs,ls,text,vr.get('options',v['options']),vr.get('stem',stem));variants.append({'id':qid,'slug':path.stem,'source':v['source'],'resolved':okay,'status':vs,'labels':ls,'answer_kind':vkind})
        courses.append({'slug':path.stem,'course':model['course'],'questions':len(course),'answered':sum(r['resolved']for r in course),'unresolved':sum(not r['resolved']for r in course)})
    assert len(seen)==3485 and len(courses)==16 and len(variants)==24
    unresolved=[r for r in rows if not r['resolved']];vbad=[v for v in variants if not v['resolved']];complete=not unresolved and not vbad;duplicates=[ids for ids in prompt_groups.values()if len(ids)>1]
    result={'schema_version':1,'passed':complete and not duplicates,'all_answers_present':complete,'generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Definite declared-answer coverage for clarified practice versions, including explicit select-all and written answers. This does not independently prove every answer correct. Original source text remains in the audit.','review_data_sha256':sha(ROOT/'STUDY_NOTE_ANSWER_REVIEW.json'),'totals':{'courses':16,'questions':3485,'answered':3485-len(unresolved),'unresolved':len(unresolved),'source_variants':24,'answered_source_variants':24-len(vbad),'unresolved_source_variants':len(vbad),'exact_duplicate_question_groups':len(duplicates),'clarified_question_records':sum(r['clarified']for r in rows),'answer_kinds':dict(Counter(r['answer_kind']for r in rows if r['resolved']))},'exact_duplicate_groups':duplicates,'courses':courses,'unresolved':unresolved,'unresolved_source_variants':vbad,'questions':rows,'variants':variants}
    if support_path.exists():result['support_data_sha256']=sha(support_path)
    (ROOT/'ANSWER_COMPLETENESS_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['totals'],indent=2))
    if not allow_pending:assert complete and not duplicates,'Some main/source versions lack an answer, or exact duplicate practice questions remain'
    return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--allow-pending',action='store_true');a=p.parse_args();verify(a.allow_pending)
