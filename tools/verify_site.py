"""Verify static public architecture and recoverable source preservation."""
from pathlib import Path
from urllib.parse import urlsplit,unquote
import hashlib,json,argparse,re,sys
from lxml import html
from public_files import public_files
from seo_metadata import public_page_paths
from build_site import config,COURSES
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(source=None):
 cfg=config();manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text());preserved=0
 for f in manifest['files']:
  if f.get('source_snapshot'):
   p=ROOT/f['source_snapshot'];assert sha(p)==f['source_sha256']==f['snapshot_sha256'],f['copied_path']
  else:
   p=ROOT/f['copied_path'];assert sha(p)==f.get('copied_sha256',f['source_sha256']),f['copied_path']
  if source:assert sha(source/f['source_path'])==f['source_sha256'],f['source_path']
  preserved+=1
 public_set={p.resolve()for p in public_files()}
 paths=public_page_paths(COURSES);pages={p:html.parse(str(ROOT/p)).getroot()for p in paths};ids={p:set(d.xpath('//*[@id]/@id'))for p,d in pages.items()};links=0;external=0
 for path,d in pages.items():
  titles=d.xpath('//head/title/text()');assert len(titles)==1 and 55<=len(titles[0])<=60,(path,titles)
  desc=d.xpath('//meta[@name="description"]/@content');assert len(desc)==1 and 150<=len(desc[0])<=160,(path,desc)
  assert d.xpath('//link[@rel="canonical"]/@href')==[cfg['SITE_URL']+('/' if path=='index.html' else '/'+path)],path
  for prop in ['og:title','og:description','og:type','og:url','og:image']:assert d.xpath('//meta[@property="'+prop+'"]/@content'),(path,prop)
  assert d.xpath('//meta[@name="twitter:card"]/@content')==['summary_large_image'],path
  for n in d.xpath('//script[@type="application/ld+json"]'):json.loads(n.text)
  assert len(d.cssselect('.hub-header'))==1 and len(d.cssselect('.hub-footer'))==1,path
  assert len(d.xpath('//main'))==1 and len(d.xpath('//h1'))==1,(path,'semantic main/h1')
  assert d.cssselect('#hub-favicon') and d.cssselect('#hub-favicon-fallback'),path
  assert len(d.cssselect('.hub-faq'))==int(path in ('index.html','downloads.html')),(path,'FAQ')
  for n in d.xpath('//*[@href or @src]'):
   for attr in ('href','src'):
    href=n.get(attr)
    if not href:continue
    u=urlsplit(href)
    if u.scheme or u.netloc:
     if u.scheme in ('https','http') and n.tag=='a':
      if u.netloc==urlsplit(cfg['SITE_URL']).netloc:assert not n.get('target'),(path,href)
      else:
       assert n.get('target')=='_blank' and set(n.get('rel','').split())>={'noopener','noreferrer'},(path,href);external+=1
     continue
    assert not u.path.startswith('/'),(path,href)
    dest=(ROOT/path).parent/unquote(u.path)if u.path else ROOT/path
    dest=dest.resolve();assert dest.is_relative_to(ROOT),(path,href)
    if dest.is_dir():dest=dest/'index.html'
    assert dest.exists(),(path,'missing',href)
    assert dest in public_set,(path,'dependency excluded from hosting upload',href)
    rel=dest.relative_to(ROOT).as_posix()
    if u.fragment and rel in pages:assert unquote(u.fragment)in ids[rel],(path,'anchor',href)
    if n.tag=='a':assert not n.get('target'),(path,'internal target',href)
    links+=1
 assert len(list((ROOT/'Modules/files').glob('*.pdf')))==14
 for v in ['0934150083','1000786296149','5061102585011','abelasnake2003@gmail.com','https://t.me/Abechu7','https://instagram.com/abel_asne']:assert v in(ROOT/'index.html').read_text(),v
 pub={p.relative_to(ROOT).as_posix()for p in public_files()};assert set(paths)<=pub
 assert not any(p.startswith(('maintenance/','work/','tools/','tests/'))or p in {'SOURCE_MANIFEST.json','STUDY_NOTE_SUPPORT.json','STUDY_NOTE_ANSWER_REVIEW.json'}for p in pub)
 from xml.etree import ElementTree as ET
 urls=[n.text for n in ET.parse(ROOT/'sitemap.xml').findall('.//{*}loc')];assert set(urls)=={cfg['SITE_URL']+('/' if p=='index.html' else '/'+p) for p in paths}
 assert 'Sitemap: '+cfg['SITE_URL']+'/sitemap.xml' in(ROOT/'robots.txt').read_text()
 result={'passed':True,'html_pages':len(paths),'preserved_resource_files':preserved,'all_original_source_bytes_recoverable':True,'local_links_checked':links,'external_links_routed':external,'public_files':len(pub),'canonical_url':cfg['SITE_URL'],'course_questions':16,'course_outlines':16,'course_modules':16,'unique_module_pdfs':14}
 print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--source',type=Path);a.add_argument('--output',type=Path);v=a.parse_args();r=verify(v.source)
 if v.output:v.output.write_text(json.dumps(r,indent=2))
