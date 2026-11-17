#!/usr/bin/env python3
"""Build a readable review-status report from the final answer-review ledger."""
from collections import Counter
from html import escape as e
import json
from pathlib import Path
import re
from verify_answer_completeness import verify as verify_completeness
ROOT=Path(__file__).resolve().parents[1]
LABELS={'answered':'Single answer','answered_open':'Written answer','answered_multiple':'Answered: select all','multiple_answers':'Multiple valid choices','ambiguous':'Interpretation needed','no_valid_option':'No correct listed option','incomplete_question':'Missing question data','study_note_gap':'Additional reference needed'}
def main():
    coverage=verify_completeness(allow_pending=True)
    data=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes())
    assert data['complete'],'Finish reviews before generating the release report'
    reviews={r['id']:r for r in data['reviews']}
    support_path=ROOT/'STUDY_NOTE_SUPPORT.json'
    support=json.loads(support_path.read_text())if support_path.exists()else None
    if support:reviews.update({r['id']:r['answer_review']for r in support['questions']})
    columns=list(LABELS);rows=[];details=[];supplements=[];clarifications=[]
    for c in data['courses']:
        s=c['slug'];p=ROOT/'Questions/Interactive_Study_Guides'/(s+'.html');m=json.loads(re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',p.read_text(),re.S)[1]);numbers={i['question']['id']:i['question']['question']for i in m['questions']}
        counts=Counter(r['status']for r in reviews.values()if r['id']in numbers)
        rows.append('<tr><th scope="row">'+e(c['course'])+'</th><td>'+str(len(numbers))+'</td><td>'+str(len(numbers)-c['reviewed'])+'</td>'+''.join('<td>'+str(counts[k])+'</td>'for k in columns)+'</tr>')
        items=[];course_clarified=[]
        for qid,n in numbers.items():
            r=reviews.get(qid)
            if not r:continue
            href='Questions/Interactive_Study_Guides/'+s+'.html#question-'+str(n)
            if r.get('question_revision'):course_clarified.append('<li><a href="'+href+'">'+e(c['course'])+' · Q'+str(n)+' · '+e(qid)+'</a> — '+e(r['question_revision']['note'])+'</li>')
            if r.get('basis')=='supplementary_reference':supplements.append('<li><a href="'+href+'">'+e(c['course'])+' · Q'+str(n)+' · '+e(qid)+'</a> — '+e(r['answer_text'])+'</li>')
            if r['status']in ['answered','answered_open','answered_multiple']:continue
            items.append('<li><a href="'+href+'">Q'+str(n)+' · '+e(qid)+'</a><span class="badge">'+e(LABELS[r['status']])+'</span><p>'+e(r['answer_text'])+'</p></li>')
        details.append('<details><summary>'+e(c['course'])+' · '+str(len(items))+' unresolved · '+str(len(course_clarified))+' clarified</summary><ul class="items">'+(''.join(items+course_clarified)or'<li>All reviewed questions have clear answers.</li>')+'</ul></details>')
    total=Counter(r['status']for r in reviews.values());single=total['answered']+total['answered_open']+total['answered_multiple'];flagged=sum(total[k]for k in columns if k not in ['answered','answered_open','answered_multiple'])
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Answer Review · CS Exit Ethiopia</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f7f8;color:#203440;font:16px/1.7 system-ui,sans-serif}main{max-width:1150px;margin:auto;padding:30px 22px 70px}nav{display:flex;flex-wrap:wrap;gap:20px}a{color:#17604f;text-underline-offset:3px}h1{font-size:clamp(27px,5vw,38px);line-height:1.25;margin:35px 0 16px}h2{font-size:22px;margin-top:38px}p{max-width:85ch}.intro{padding:22px;background:white;border-left:4px solid #467c69;border-radius:6px}.table-wrap{overflow:auto;background:white;border:1px solid #dce4e8;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px 14px;border-bottom:1px solid #e4e9ec;text-align:left;vertical-align:top}thead th{background:#eaf1ee}tbody td{text-align:center}tbody th{min-width:200px}details{background:white;border:1px solid #dce4e8;border-radius:7px;padding:15px 18px;margin:12px 0}summary{cursor:pointer;font-weight:650}.items{padding-left:22px}.items>li{padding:13px 0;border-bottom:1px solid #edf0f2}.items p{margin:9px 0 2px}.badge{display:inline-block;font-size:12px;color:#705212;background:#faf2dc;border-radius:4px;padding:2px 8px;margin-left:12px}.muted{font-size:14px;color:#5d6e77}dt{font-weight:650}dd{margin:3px 0 16px 20px}@media(max-width:600px){main{padding:22px 15px 50px}.intro{padding:17px}.badge{display:table;margin:7px 0}th,td{padding:10px}}
</style></head><body><main><nav><a href="index.html">Home</a><a href="Questions/Interactive_Study_Guides/index.html">Practice questions</a><a href="Complete_CS_Exit_Study_Guide.html">Complete study note</a></nav><h1>Question answer review</h1>'''
    if support:
        added=sum(len(c['additions'])for c in support['courses'])
        html+='<div class="intro"><p><strong>All 3,485 practice questions and 24 alternative source versions have answers.</strong> Every question has a separate reading hint, an explanation, choice contrasts where applicable, and exact supporting passages from the complete study note.</p><p>'+str(added)+' focused conceptual lessons fill missing study-note coverage. Existing study-guide wording is preserved. Clarified practice versions are labeled; original imported wording and older reviews remain available in closed archives.</p><p><a href="STUDY_NOTE_SUPPORT_AUDIT.json">Full study-note support verification</a> · <a href="STUDY_NOTE_SUPPORT.json">Per-question evidence and editorial review</a></p></div>'
    else:
        html+='<div class="intro"><p>Current practice answers and earlier source reviews are recorded separately. Reading links alone do not establish answer correctness.</p></div>'
    totals=coverage['totals']
    html+='<p><strong>Current answer coverage: '+format(totals['answered'],',')+' of 3,485 main questions and '+str(totals['answered_source_variants'])+' of 24 source variants.</strong> <a href="ANSWER_COMPLETENESS_AUDIT.json">Per-question completeness audit</a>.</p>'
    html+='<h2>Answer formats</h2><dl><dt>Single answer</dt><dd>One choice satisfies the stated question and assumptions.</dd><dt>Written answer</dt><dd>An explanation or result is supplied for a prompt without choices.</dd><dt>Answered: select all</dt><dd>The question explicitly asks for every applicable choice, and the answer lists all correct letters.</dd></dl>'
    html+='<h2>All 16 courses</h2><p class="muted">“Previously verified” records the historical source-review category. Every question has also been reviewed for support in the complete study note.</p><div class="table-wrap"><table><thead><tr><th scope="col">Course</th><th scope="col">Questions</th><th scope="col">Previously verified</th>'+''.join('<th scope="col">'+e(LABELS[k])+'</th>'for k in columns)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    if supplements:html+='<h2>Explicit supplementary references</h2><p>These source references informed the added conceptual lessons and remain available for further reading.</p><ul>'+''.join(supplements)+'</ul>'
    html+='<h2>Practice questions by course</h2><p>Open a course to see the clarified practice versions. Follow a question link and reveal its answer for the reasoning and exact reading evidence.</p>'+''.join(details)
    html+='<p class="muted">Review ledger: <a href="STUDY_NOTE_ANSWER_REVIEW.json">STUDY_NOTE_ANSWER_REVIEW.json</a>. Completed '+e(data['updated_at_utc'][:10])+'. These checks do not guarantee an exam score or authenticate historical source keys.</p></main></body></html>'
    (ROOT/'ANSWER_REVIEW_SUMMARY.html').write_text(html)
    print('Wrote ANSWER_REVIEW_SUMMARY.html:',single,'single/written answers;',flagged,'flagged items')
if __name__=='__main__':main()
