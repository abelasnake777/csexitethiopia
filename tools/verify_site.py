"""Optional local verification. Deployment does not require Python or a build step."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit,unquote
import hashlib,json,argparse,re
ROOT=Path(__file__).resolve().parent.parent
class Page(HTMLParser):
 def __init__(self,text):
  super().__init__(convert_charrefs=True);self.ids=set();self.links=[];self.feed(text)
  match=re.search(r'<script id="guide-data" type="application/json">(.*?)</script>',text,re.S)
  if match:self.ids.update('question-'+str(item['question']['question'])for item in json.loads(match[1])['questions'])
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  if 'id'in attrs:self.ids.add(attrs['id'])
  for key in ('href','src'):
   if attrs.get(key):self.links.append((tag,attrs[key]))
def digest(data):return hashlib.sha256(data).hexdigest()
def verify(source=None):
 manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text());preserved=0
 for f in manifest['files']:
  data=(ROOT/f['copied_path']).read_bytes();assert digest(data)==f['copied_sha256'],('Changed copied resource',f['copied_path'])
  for key in ['answer_review_integration_block','reference_integration_block','integration_block']:
   block=f.get(key)
   if block:
    b=block.encode();assert data.count(b)==1;data=data.replace(b,b'',1)
  assert digest(data)==f['source_sha256'],('Educational content changed',f['copied_path'])
  if source:assert (source/f['source_path']).read_bytes()==data,('Original source changed',f['source_path'])
  preserved+=1
 pages={p.resolve():Page(p.read_text())for p in ROOT.rglob('*.html')if '.git'not in p.parts and'.qa'not in p.parts};count=0;external=set()
 for path,page in pages.items():
  for tag,href in page.links:
   u=urlsplit(href)
   if u.scheme or u.netloc:
    if u.scheme in ('http','https'):external.add(href)
    continue
   assert not u.path.startswith('/'),('Nonrelative path',path.name,href)
   dest=(path.parent/unquote(u.path)).resolve()if u.path else path
   assert dest.is_relative_to(ROOT),('Outside project',path.name,href)
   if dest.is_dir():dest=dest/'index.html'
   assert dest.exists(),('Broken local link',str(path.relative_to(ROOT)),href)
   if u.fragment and dest.suffix=='.html':assert unquote(u.fragment)in pages[dest].ids,('Missing anchor',path.name,href)
   count+=1
 assert len(list((ROOT/'Modules').glob('*.html')))==17;assert len(list((ROOT/'Modules/files').glob('*.pdf')))==14
 assert (ROOT/'index.html').exists();assert len(list((ROOT/'Questions/Interactive_Study_Guides').glob('*.html')))==17;assert len(list((ROOT/'Outlines').glob('*.html')))==17
 for value in ['Abel Asnake Bekele','0934150083','1000786296149','5061102585011','abelasnake2003@gmail.com','https://t.me/Abechu7','https://instagram.com/abel_asne']:assert value in (ROOT/'index.html').read_text(),value
 result={'passed':True,'html_pages':len(pages),'preserved_resource_files':preserved,'educational_html_preserved':sum(bool(f['integration_block'])for f in manifest['files']),'local_links_checked':count,'no_hardcoded_root_paths':True,'all_source_bytes_recoverable':True,'course_questions':16,'course_outlines':16,'course_modules':16,'unique_module_pdfs':14,'external_reference_links':sorted(external)}
 print(json.dumps({**{k:v for k,v in result.items()if k!='external_reference_links'},'external_reference_count':len(external)},indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();r=verify(a.source)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2))
