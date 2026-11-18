#!/usr/bin/env python3
"""Validate the original repair ledger against questions and the expanded note.

This checks coverage, option bookkeeping and literal evidence, not the truth of
an explanation. Ambiguous questions and note gaps remain distinct from answers.
"""
from study_note_preservation import verify_base,without_public_block
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = re.compile(r'<script id="guide-data" type="application/json">(.*?)</script>', re.S)
TARGET_STATUSES = {'insufficient_module_coverage','source_gap','ambiguous_question','source_unverified'}
STATUSES = {'answered','multiple_answers','ambiguous','incomplete_question','study_note_gap','answered_open','no_valid_option','answered_multiple'}

def sha(data): return hashlib.sha256(data).hexdigest()
def norm(s): return re.sub(r'\s+', ' ', s).strip()
def require(condition, message):
    if not condition: raise AssertionError(message)

class Note(HTMLParser):
    def __init__(self):
        super().__init__(); self.sections={}; self.stack=[]; self.course=None
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if tag=='article' and attrs.get('id','').startswith('course-'): self.course=attrs['id'][7:]
        if tag=='section':
            sid=attrs.get('id'); self.stack.append(sid)
            if sid: self.sections[sid]={'course':self.course,'text':[]}
    def handle_endtag(self,tag):
        if tag=='section' and self.stack:self.stack.pop()
        if tag=='article':self.course=None
    def handle_data(self, data):
        for sid in self.stack:
            if sid:self.sections[sid]['text'].append(data)

def verify(allow_partial=False):
    master=(ROOT/'Complete_CS_Exit_Study_Guide.html').read_bytes(); note=Note();note.feed(master.decode())
    data=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes()); reviews={r['id']:r for r in data['reviews']}
    require(len(reviews)==len(data['reviews']), 'Repeated review ID')
    verify_base(master.decode())
    require(sha(without_public_block(master.decode()).encode())==data.get('study_guide_sha256',data.get('study_guide_unchanged_sha256')),'Study-note version mismatch')
    targets={}; original_verified=0; courses=[]; seen=set(); variants=0; evidence_count=0
    for path in sorted((ROOT/'Questions/Interactive_Study_Guides').glob('*.html')):
        matches=PAYLOAD.findall(path.read_text())
        if not matches:continue
        require(len(matches)==1, path.stem+' payload count')
        model=json.loads(matches[0]); c={'slug':path.stem,'questions':len(model['questions']),'targeted':0,'reviewed':0,'statuses':Counter()}
        for item in model['questions']:
            q=item['question']; qid=q['id'];require(qid not in seen,qid+' repeated source ID');seen.add(qid)
            old=item['review']['status']
            if old not in TARGET_STATUSES:
                require(old=='verified',qid+' unexpected legacy status');original_verified+=1;continue
            targets[qid]=path.stem;c['targeted']+=1
            if qid not in reviews:
                require(allow_partial,qid+' current review missing');continue
            r=reviews[qid];c['reviewed']+=1;c['statuses'][r['status']]+=1
            require(r['status']in STATUSES,qid+' invalid review status')
            require(r['previous_status']==old,qid+' previous status mismatch')
            revision=r.get('question_revision')
            if revision:
                require(revision['kind']=='user_approved_intended_reading' and revision['approved_on'] and revision['assumptions'] and revision['note'],qid+' clarification provenance')
                require(revision['original_stem']==q['stem'] and revision['original_options']==q['options'],qid+' original clarification snapshot differs')
                active_labels=[o['label']for o in revision['options']];original_labels=[o['label']for o in q['options']]
                restored=not original_labels and revision.get('options_restored_from_embedded_stem')and re.findall(r'(?:^|\n)\s*([A-Z])[).]\s+',q['stem'])==active_labels
                require(revision['stem'].strip()and(active_labels==original_labels or restored),qid+' clarified question/options mismatch')
                require(all(o['text'].strip() for o in revision['options']),qid+' empty clarified option')
            if r['status']=='answered_multiple':require(revision and re.search(r'\b(select|choose|identify|mark)\s+all\b',revision['stem'],re.I),qid+' explicit select-all wording missing')
            options=[o['label']for o in(revision['options']if revision else q['options'])]
            require([a['label']for a in r['choices']]==options,qid+' options missing/reordered')
            require(len(set(r['labels']))==len(r['labels']) and set(r['labels'])<=set(options),qid+' answer label mismatch')
            if r['status']=='answered_open':require(not options,qid+' open answer has choices')
            if r['status']=='answered':require(len(r['labels'])==1,qid+' unique label count')
            if r['status']in ['multiple_answers','answered_multiple']:require(len(r['labels'])>=2,qid+' multiple label count')
            if r['status']in ['study_note_gap','incomplete_question','answered_open','no_valid_option']:require(not r['labels'],qid+' unsupported answer label')
            for a in r['choices']:
                require(a['verdict']in ['correct','incorrect','possible','invalid']and a['explanation'].strip(),qid+' choice analysis')
                if r['status']in ['answered','multiple_answers','answered_multiple']and a['label']in r['labels']:require(a['verdict']in ['correct','possible'],qid+' selected label contradicts verdict')
            if r.get('basis')=='supplementary_reference':
                require(r.get('note_gap')and r.get('external_evidence'),qid+' supplemental evidence missing')
                for e in r['external_evidence']:require(e['url'].startswith('https://')and e['title']and e['statement']and e['checked_on'],qid+' invalid supplementary reference')
            for k in ['hint','answer_text','explanation']:require(r[k].strip(),qid+' empty '+k)
            require(r['section_ids']and len(set(r['section_ids']))==len(r['section_ids']),qid+' duplicate/empty sections')
            for sid in r['section_ids']:require(sid in note.sections and note.sections[sid]['course']==path.stem,qid+' wrong-course/missing note section '+sid)
            if r['status']in ['answered','multiple_answers','answered_multiple','ambiguous','answered_open','no_valid_option']:require(r['evidence'],qid+' missing note evidence')
            for e in r['evidence']:
                evidence_count+=1;sid=e['section_id']
                require(sid in r['section_ids'],qid+' evidence outside references')
                require(len(e['quote'].strip())>=5 and norm(e['quote'])in norm(''.join(note.sections[sid]['text'])),qid+' quotation absent from actual HTML '+sid)
            rv=r.get('variant_reviews',[]); ov=q.get('option_variants',[]);require(len(rv)==len(ov),qid+' alternative choices omitted')
            variants+=len(rv)
            corrected_variants=revision.get('variant_revisions',[])if revision else []
            if corrected_variants:require(len(corrected_variants)==len(ov),qid+' revised variant coverage')
            for vi,(v,source)in enumerate(zip(rv,ov)):
                labels=[o['label']for o in source['options']]
                require(v['source']==source['source']and[a['label']for a in v['choices']]==labels,qid+' variant source/options mismatch')
                require(set(v['labels'])<=set(labels)and v['explanation']and v['answer_text'],qid+' variant answer')
                if corrected_variants:
                    corrected=corrected_variants[vi]
                    require(corrected['source']==source['source']and corrected['stem'].strip()and corrected['assumptions']and[o['label']for o in corrected['options']]==labels,qid+' revised variant question')
                    require(v['status']in ['answered','answered_multiple']and v['labels'],qid+' variant answer status')
                    if v['status']=='answered_multiple':require(len(v['labels'])>=2 and re.search(r'\b(select|choose|identify|mark)\s+all\b',corrected['stem'],re.I),qid+' variant select-all wording')
                    else:require(len(v['labels'])==1,qid+' variant single answer')
                require(all(a['verdict']in ['correct','incorrect','possible','invalid']and a['explanation']for a in v['choices']),qid+' variant choice verdict/explanation')
        c['statuses']=dict(c['statuses']);courses.append(c)
    require(set(reviews)<=set(targets),'Reviews contain foreign or previously verified IDs')
    require(len(seen)==3485 and len(targets)==2164 and original_verified==1321,'Unexpected coverage counts')
    require(len(reviews)==data['reviewed'] and data['targeted_questions']==len(targets),'Summary count mismatch')
    require(Counter(r['status']for r in reviews.values())==data['statuses'],'Status summary mismatch')
    if not allow_partial:require(data['complete']and len(reviews)==len(targets),'Review incomplete')
    result={'passed':True,'generated_at':datetime.now(timezone.utc).isoformat(),'scope':'Structural and evidence verification; not a guarantee of answer correctness or exam completeness.','study_guide_sha256':sha(master),'review_data_sha256':sha((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes()),'questions':len(seen),'targeted':len(targets),'reviewed':len(reviews),'previous_verified_unchanged':original_verified,'all_targeted_reviewed':len(reviews)==len(targets),'literal_note_passages_checked':evidence_count,'alternative_choice_sets_checked':variants,'clarified_question_ids':[r['id']for r in reviews.values()if r.get('question_revision')],'statuses':data['statuses'],'courses':courses}
    (ROOT/'.qa/study-note-answers-static.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--allow-partial',action='store_true');args=parser.parse_args()
    result=verify(args.allow_partial);print(json.dumps({k:v for k,v in result.items()if k!='courses'},indent=2))
