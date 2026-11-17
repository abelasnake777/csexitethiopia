#!/usr/bin/env python3
"""Build a readable review-status report from the final answer-review ledger."""
from collections import Counter
from html import escape as e
import json
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
LABELS={'answered':'Single answer','answered_open':'Written answer','multiple_answers':'Multiple valid choices','ambiguous':'Interpretation needed','no_valid_option':'No correct listed option','incomplete_question':'Missing question data','study_note_gap':'Additional reference needed'}
def main():
    data=json.loads((ROOT/'STUDY_NOTE_ANSWER_REVIEW.json').read_bytes())
    assert data['complete'],'Finish reviews before generating the release report'
    reviews={r['id']:r for r in data['reviews']};columns=list(LABELS);rows=[];details=[];supplements=[];clarifications=[]
    for c in data['courses']:
        s=c['slug'];p=ROOT/'Questions/Interactive_Study_Guides'/(s+'.html');m=json.loads(re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',p.read_text(),re.S)[1]);numbers={i['question']['id']:i['question']['question']for i in m['questions']}
        counts=Counter(r['status']for r in reviews.values()if r['id']in numbers)
        rows.append('<tr><th scope="row">'+e(c['course'])+'</th><td>'+str(len(numbers))+'</td><td>'+str(len(numbers)-c['reviewed'])+'</td>'+''.join('<td>'+str(counts[k])+'</td>'for k in columns)+'</tr>')
        items=[]
        for qid,n in numbers.items():
            r=reviews.get(qid)
            if not r:continue
            href='Questions/Interactive_Study_Guides/'+s+'.html#question-'+str(n)
            if r.get('question_revision'):clarifications.append('<li><a href="'+href+'">'+e(c['course'])+' · Q'+str(n)+' · '+e(qid)+'</a> — '+e(r['question_revision']['note'])+'</li>')
            if r.get('basis')=='supplementary_reference':supplements.append('<li><a href="'+href+'">'+e(c['course'])+' · Q'+str(n)+' · '+e(qid)+'</a> — '+e(r['answer_text'])+'</li>')
            if r['status']in ['answered','answered_open']:continue
            items.append('<li><a href="'+href+'">Q'+str(n)+' · '+e(qid)+'</a><span class="badge">'+e(LABELS[r['status']])+'</span><p>'+e(r['answer_text'])+'</p></li>')
        details.append('<details><summary>'+e(c['course'])+' · '+str(len(items))+' flagged source items</summary><ul class="items">'+(''.join(items)or'<li>No flagged items in the newly reviewed set.</li>')+'</ul></details>')
    total=Counter(data['statuses']);single=total['answered']+total['answered_open'];flagged=sum(total[k]for k in columns if k not in ['answered','answered_open'])
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Answer Review · CS Exit Ethiopia</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f7f8;color:#203440;font:16px/1.7 system-ui,sans-serif}main{max-width:1150px;margin:auto;padding:30px 22px 70px}nav{display:flex;flex-wrap:wrap;gap:20px}a{color:#17604f;text-underline-offset:3px}h1{font-size:clamp(27px,5vw,38px);line-height:1.25;margin:35px 0 16px}h2{font-size:22px;margin-top:38px}p{max-width:85ch}.intro{padding:22px;background:white;border-left:4px solid #467c69;border-radius:6px}.table-wrap{overflow:auto;background:white;border:1px solid #dce4e8;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:12px 14px;border-bottom:1px solid #e4e9ec;text-align:left;vertical-align:top}thead th{background:#eaf1ee}tbody td{text-align:center}tbody th{min-width:200px}details{background:white;border:1px solid #dce4e8;border-radius:7px;padding:15px 18px;margin:12px 0}summary{cursor:pointer;font-weight:650}.items{padding-left:22px}.items>li{padding:13px 0;border-bottom:1px solid #edf0f2}.items p{margin:9px 0 2px}.badge{display:inline-block;font-size:12px;color:#705212;background:#faf2dc;border-radius:4px;padding:2px 8px;margin-left:12px}.muted{font-size:14px;color:#5d6e77}dt{font-weight:650}dd{margin:3px 0 16px 20px}@media(max-width:600px){main{padding:22px 15px 50px}.intro{padding:17px}.badge{display:table;margin:7px 0}th,td{padding:10px}}
</style></head><body><main><nav><a href="index.html">Home</a><a href="Questions/Interactive_Study_Guides/index.html">Practice questions</a><a href="Complete_CS_Exit_Study_Guide.html">Complete study note</a></nav><h1>Question answer review</h1>'''
    html+='<div class="intro"><p><strong>Reference links and established answers are different checks.</strong> Every question has reading links, but a link alone does not prove that a source question has one defensible answer.</p><p>All '+format(data['reviewed'],',')+' previously unverified or limited reviews have been reassessed. '+format(data['prior_verified_unchanged'],',')+' earlier module-verified records are retained. Of the newly reviewed items, '+format(single,',')+' have a single or written answer; '+format(flagged,',')+' have a specific source or answer-certainty flag explained below.</p><p>The complete study note and imported source question data, images and provenance remain unchanged. User-approved clarified practice wording is labeled in the question readers; its original wording is retained in the audit. Current reviews appear first; earlier hint and answer reviews are in closed archives.</p></div>'
    html+='<h2>What the statuses mean</h2><dl><dt>Single answer / Written answer</dt><dd>A supported answer is supplied. Written questions do not need multiple-choice options.</dd><dt>Multiple valid choices</dt><dd>More than one offered choice satisfies the wording. Do not memorize an arbitrary single letter.</dd><dt>Interpretation needed</dt><dd>The conclusion changes with a missing assumption or a plausible reading. The answer explains those readings.</dd><dt>No correct listed option</dt><dd>The supported result or rule is supplied, but the source choices omit it or are malformed.</dd><dt>Missing question data</dt><dd>A necessary diagram, value or other premise is missing. Knowing the topic cannot recover unspecified data.</dd><dt>Additional reference needed</dt><dd>The unchanged complete note does not establish a fact needed to settle the item. This is an actual remaining limitation, not a broken link.</dd></dl>'
    html+='<h2>All 16 courses</h2><p class="muted">“Previously verified” means retained from the earlier module review, not independently re-reviewed in this repair.</p><div class="table-wrap"><table><thead><tr><th scope="col">Course</th><th scope="col">Questions</th><th scope="col">Previously verified</th>'+''.join('<th scope="col">'+e(LABELS[k])+'</th>'for k in columns)+'</tr></thead><tbody>'+''.join(rows)+'</tbody></table></div>'
    if supplements:html+='<h2>Explicit supplementary references</h2><p>These items needed a rule beyond the unchanged note. The answer supplies it with an authoritative reference, and the note is labeled as background.</p><ul>'+''.join(supplements)+'</ul>'
    if clarifications:html+='<h2>Clarified practice questions</h2><p>These formerly incomplete source questions now state the intended reading or missing assumptions explicitly. They have definite answers under that clarified wording.</p><ul>'+''.join(clarifications)+'</ul>'
    html+='<h2>Flagged questions by course</h2><p>Open a course, then follow a question link. Reveal its current answer for the reasoning and exact reading evidence.</p>'+''.join(details)
    html+='<p class="muted">Review ledger: <a href="STUDY_NOTE_ANSWER_REVIEW.json">STUDY_NOTE_ANSWER_REVIEW.json</a>. Completed '+e(data['updated_at_utc'][:10])+'. These checks do not guarantee an exam score or authenticate historical source keys.</p></main></body></html>'
    (ROOT/'ANSWER_REVIEW_SUMMARY.html').write_text(html)
    print('Wrote ANSWER_REVIEW_SUMMARY.html:',single,'single/written answers;',flagged,'flagged items')
if __name__=='__main__':main()
