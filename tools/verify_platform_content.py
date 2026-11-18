"""Full educational-content parity checks for the static-reader migration."""
from pathlib import Path
from lxml import html
import re,json,hashlib
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'maintenance/public-baseline'
def text(n):return re.sub(r'\s+',' ',n.text_content().replace('↗','')).strip()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
 assert sha(ROOT/'STUDY_NOTE_SUPPORT.json')=='ecd43e3088a4daa89f54643d9963485743aa0121134e835d97dc843d7d28c850'
 assert sha(ROOT/'STUDY_NOTE_ANSWER_REVIEW.json')=='2faa09ba8a8e9393f7453a344783d4a4abd71d230ee3bc599a04dc9a84c0d28a'
 book=html.parse(str(ROOT/'Complete_CS_Exit_Study_Guide.html')).getroot();prior=html.parse(str(BASE/'Complete_CS_Exit_Study_Guide.html')).getroot();notes=prior.cssselect('section.note');book_ids={n.get('id'):n for n in book.xpath('//*[@id]')};note_ids={n.get('id') for n in notes}
 for n in notes:assert text(n)==text(book_ids[n.get('id')]),('note content',n.get('id'))
 totals=dict(questions=0,variants=0,note_sections=len(notes),outline_topics=0,note_proofs=0,module_proofs=0)
 for course in json.loads((ROOT/'assets/export-data/catalog.json').read_text())['courses']:
  slug=course['slug'];data=json.loads((ROOT/'assets/export-data'/f'{slug}.json').read_text());qpath=f'Questions/Interactive_Study_Guides/{slug}.html';old=html.parse(str(BASE/qpath)).getroot();new=html.parse(str(ROOT/qpath)).getroot();old_ids={n.get('id'):n for n in old.xpath('//*[@id]')};questions=new.cssselect('article.question');assert len(questions)==data['question_count']==course['questions']
  for q in questions:
   assert text(q)==text(old_ids[q.get('id')]),('question parity',slug,q.get('id'))
   reveals=q.cssselect(':scope>details.reveal');assert len(reveals)==2 and all(not n.get('open') for n in reveals),(slug,q.get('id'))
   assert reveals[0].cssselect('a[href*="Complete_CS_Exit_Study_Guide.html#"]') and reveals[1].cssselect('a[href*="Complete_CS_Exit_Study_Guide.html#"]')
   assert q.cssselect('.current-answer-title') and q.cssselect('.current-answer-explanation') and q.cssselect('.current-note-evidence')
  for q in data['questions']:
   assert q['stem'] and q['hint'] and q['section_ids'] and q['answer']['text'] and q['answer']['explanation'] and q['answer']['evidence'],q['id']
   assert len(q['answer']['choices'])==len(q['options']),q['id']
   assert q['answer']['labels'] or not q['options'],q['id']
   for ans in [q['answer']]+[v['answer'] for v in q['variants']]:
    for e in ans['evidence']:
     assert e['section_id'] in q['section_ids'] or e['section_id'] in note_ids,q['id']
     assert ' '.join(e['quote'].split()) in ' '.join(book_ids[e['section_id']].text_content().split()),('proof mismatch',q['id'],e['section_id'])
     totals['note_proofs']+=1
   totals['module_proofs']+=len(q['answer']['module_refs']);totals['variants']+=len(q['variants'])
  totals['questions']+=len(questions)
  opath=f'Outlines/{slug}.html';old=html.parse(str(BASE/opath)).getroot();new=html.parse(str(ROOT/opath)).getroot()
  assert json.loads(old.get_element_by_id('outline-config').text)==json.loads(new.get_element_by_id('outline-config').text)
  for card in old.cssselect('.topic-card'):
   assert text(card)==text(new.get_element_by_id(card.get('id'))),('outline content',slug,card.get('id'));totals['outline_topics']+=1
  assert len(data['outlines'])==len(old.cssselect('.topic-card')) and all(t['cues']for t in data['outlines']),slug
 assert totals['questions']==3485 and totals['variants']==24
 print(json.dumps({'passed':True,**totals},indent=2));return totals
if __name__=='__main__':verify()
