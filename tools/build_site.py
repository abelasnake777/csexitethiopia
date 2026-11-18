#!/usr/bin/env python3
"""Compile static public readers and metadata; hosting needs no build/runtime.

SITE_URL lives in site.config.js. Run --metadata-only after changing the domain.
Educational markup is preserved from the privately archived, reviewed public DOM.
"""
from pathlib import Path
import argparse,hashlib,html as H,json,re,sys
from urllib.parse import urlsplit
from lxml import html,etree
from seo_metadata import generate_head,generate_sitemap,generate_robots,public_page_paths,PUBLIC_FAQ,render_public_faq,generate_search_index
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'maintenance/public-baseline'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def config():
 s=(ROOT/'site.config.js').read_text();url=re.search(r"const SITE_URL\s*=\s*['\"]([^'\"]+)",s)[1].rstrip('/')
 if urlsplit(url).scheme!='https' or not urlsplit(url).hostname.endswith('.com'):raise ValueError('Configure an HTTPS .com SITE_URL')
 return dict(SITE_URL=url,SITE_NAME='CS Exit Ethiopia',EMAIL='abelasnake2003@gmail.com',TELEGRAM='Abechu7',LANGUAGE='en',COUNTRY='Ethiopia')
COURSES=json.loads((ROOT/'Modules/catalog.json').read_text())['courses']
COURSES=[dict(c,title=c['course']) for c in COURSES]
def root_for(p):return '../'*(len(Path(p).parts)-1) or './'
def page_info(p):
 slug=Path(p).stem if Path(p).stem in {c['slug'] for c in COURSES} else None
 typ='questions' if p.startswith('Questions/') else 'outlines' if p.startswith('Outlines/') else 'module' if p.startswith('Modules/') else 'notes' if p.startswith('Complete_') else 'downloads' if p=='downloads.html' else 'search' if p=='search.html' else 'home'
 return dict(course=slug,type=typ)
def shell(root,p,cfg):
 links=[('Home','index.html'),('Questions','Questions/Interactive_Study_Guides/index.html'),('Study Notes','Complete_CS_Exit_Study_Guide.html'),('Outlines','Outlines/index.html'),('Modules','Modules/index.html'),('Download PDFs','downloads.html'),('Search','search.html'),('Support','index.html#support')]
 nav=''.join(f'<a href="{root+url}"'+(' aria-current="page"' if url==p else '')+f'>{name}</a>' for name,url in links)
 return f'<a class="hub-skip" href="#hub-content">Skip to content</a><header class="hub-header"><div class="hub-nav-wrap"><a class="hub-brand" href="{root}index.html"><img src="{root}favicon.svg" alt="" width="30" height="30">CS Exit Ethiopia</a><button class="hub-toggle" id="hub-toggle" type="button" aria-label="Toggle navigation" aria-controls="hub-menu" aria-expanded="false">☰</button><nav class="hub-menu" id="hub-menu" aria-label="Main navigation" data-open="false">{nav}</nav></div></header>'
def footer(cfg,root):
 host=urlsplit(cfg['SITE_URL']).netloc
 return f'<footer class="hub-footer"><div class="hub-footer-inner"><div><strong>CS Exit Ethiopia</strong><p>Free Computer Science Exit Exam preparation.</p><a href="{root}index.html">{host}</a></div><div><a href="mailto:abelasnake2003@gmail.com">abelasnake2003@gmail.com</a><br><a href="https://t.me/Abechu7">Telegram @Abechu7</a><p>Prepared and shared by Abel Asnake Bekele.</p></div></div></footer>'
def faq_element(kind):
 n=html.fromstring(render_public_faq(kind));n.classes.add('hub-faq');return n
def export_bar(kind):
 name={'notes':'Study Notes','questions':'Questions','outlines':'Quick Revision Outlines'}[kind]
 return html.fromstring(f'<div class="hub-export-bar"><button type="button" data-pdf-kind="{kind}">Download {name} (PDF)</button></div>')
def make_static(p,cfg):
 src=BASE/p
 if not src.exists():return # New standalone search/downloads are authored separately.
 d=html.fromstring(src.read_text());body=d.find('body');head=d.find('head');pi=page_info(p)
 # Keep only reader behavior needed by the static educational markup.
 preserved=[]
 if pi['type']=='outlines' and pi['course']:
  for s in d.xpath('//script'):
   if s.get('id')=='outline-config' or (s.text and "const config=JSON.parse(document.getElementById('outline-config')" in s.text):preserved.append(etree.tostring(s,encoding='unicode',method='html'))
 if pi['type']=='module' and pi['course']:
  for s in d.xpath('//script'):
   if s.get('id')=='module-config' or s.get('src','').endswith('module-loader.js'):preserved.append(etree.tostring(s,encoding='unicode',method='html'))
 for n in d.xpath('//script|//nav[contains(@class,"resource-hub-nav")]|//a[contains(@class,"skip-link")]|//header[contains(@class,"site-header")]'):
  n.getparent().remove(n)
 # Retain original reader typography; remove only obsolete hub styles and metadata.
 styles=[etree.tostring(n,encoding='unicode',method='html') for n in head.xpath('./style|./link[@rel="stylesheet"]') if 'resource-nav' not in n.get('href','')]
 if pi['type']=='questions' and not pi['course']:styles=['<style>body{margin:0;background:#f7f9fa;font:16px/1.7 system-ui,sans-serif;color:#183242}</style>']
 for n in d.xpath('//details[@open]'):n.attrib.pop('open',None)
 for n in d.xpath('//details/summary[@aria-expanded]'):n.set('aria-expanded','false')
 # No internal navigation opens a new tab. External routing is also static.
 route_links(d,cfg)
 content=html.Element('div',id='hub-content',attrib={'class':'hub-page'})
 if pi['type']=='questions' and not pi['course']:content.classes.add('hub-course-selector')
 for n in list(body):
  if isinstance(n.tag,str):content.append(n)
 for n in content.xpath('.//*[@onclick or @onchange or @onload]'):
  for attr in ['onclick','onchange','onload']:n.attrib.pop(attr,None)
 if pi['type']=='questions' and not pi['course']:
  for li in content.cssselect('ul.resource-hub-course-grid > li'):
   a=li.find('a')
   if a is not None and a.tail:
    count=html.Element('span',attrib={'class':'hub-course-count'});count.text=a.tail.strip().lstrip('— ');a.tail=None;a.append(count)
 if pi['type'] in ('notes','questions','outlines'):
  target=content.cssselect('main') or [content]
  target[0].insert(0,export_bar(pi['type']))
 # Only add visible FAQ markup where its exact schema is included.
 if p=='index.html':content.append(faq_element('home'))
 # No hidden duplicate data feeds are shipped; every question is real static HTML.
 root=root_for(p);extra=''
 if pi['type']=='questions' and pi['course']:extra=f'<script defer src="{root}assets/questions-reader.js"></script>'
 if pi['type']=='home':extra=f'<script defer src="{root}assets/site.js"></script>'
 if pi['type']=='notes':extra=f'<script defer src="{root}assets/book-reader.js"></script>'
 body_text=etree.tostring(content,encoding='unicode',method='html')+''.join(preserved)+extra
 (ROOT/p).write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+''.join(styles)+'</head><body>'+body_text+'</body></html>')
def route_links(d,cfg):
 for a in d.xpath('//a[@href]'):
  u=urlsplit(a.get('href'))
  if u.scheme in ('https','http') and u.netloc!=urlsplit(cfg['SITE_URL']).netloc:
   a.set('target','_blank');a.set('rel','noopener noreferrer')
   for span in a.xpath('.//span[@aria-hidden="true" and not(@class)]'):
    if (span.text or '').strip()=='↗':span.getparent().remove(span)
   if not a.cssselect('.hub-external'):
    x=html.Element('span',attrib={'class':'hub-external','aria-hidden':'true'});x.text='↗';a.append(x)
  elif u.scheme not in ('mailto','tel'):
   a.attrib.pop('target',None);a.attrib.pop('rel',None)
   for span in a.xpath('.//span[@aria-hidden="true"]'):
    if (span.text or '').strip()=='↗':span.text='→'
def direct_pdf_links(d,root):
 for old in d.xpath('//*[@id="direct-pdfs"]'):old.getparent().remove(old)
 labels={'questions':'Questions & answers','notes':'Study notes','outlines':'Revision outlines'}
 section=html.Element('section',id='direct-pdfs',attrib={'class':'hub-direct-pdfs'})
 h=etree.SubElement(section,'h2');h.text='Ready-made PDFs'
 p=etree.SubElement(section,'p');p.text='Download a complete collection or a single course directly. Use the selectors above to combine your own courses.'
 allrow=etree.SubElement(section,'div',attrib={'class':'hub-pdf-links'})
 for kind,label in labels.items():
  a=etree.SubElement(allrow,'a',href=root+f'assets/pdf/{kind}/all-courses.pdf',download='');a.text='All 16 · '+label
 details=etree.SubElement(section,'details');summary=etree.SubElement(details,'summary');summary.text='Single-course PDFs'
 ul=etree.SubElement(details,'ul',attrib={'class':'hub-pdf-courses'})
 for course in COURSES:
  li=etree.SubElement(ul,'li');h=etree.SubElement(li,'h3');h.text=course['title'];row=etree.SubElement(li,'div',attrib={'class':'hub-pdf-links'})
  for kind,label in labels.items():
   a=etree.SubElement(row,'a',href=root+f'assets/pdf/{kind}/{course["slug"]}.pdf',download='');a.text=label;a.set('aria-label',course['title']+' · '+label+' PDF')
 main=d.cssselect('main')[0];faq=main.cssselect('.hub-faq')
 if faq:faq[0].addprevious(section)
 else:main.append(section)
def decorate(p,cfg):
 path=ROOT/p
 if not path.exists():raise FileNotFoundError(p)
 d=html.fromstring(path.read_text());head=d.find('head');body=d.find('body');root=root_for(p);pi=page_info(p)
 if p=='downloads.html' and not d.xpath('//*[@id="downloads"]'):d.cssselect('main')[0].set('id','downloads')
 # Idempotent platform and SEO replacement.
 for n in d.xpath('//*[@data-platform="true"]|//header[contains(@class,"hub-header")]|//footer[contains(@class,"hub-footer")]|//a[contains(@class,"hub-skip")]'):
  n.getparent().remove(n)
 for n in head.xpath('./title|./meta[not(@charset) and not(@name="viewport")]|./link[@rel="canonical" or @rel="icon" or @rel="shortcut icon" or @rel="apple-touch-icon"]|./script[@type="application/ld+json"]'):
  head.remove(n)
 metadata={}
 kind='home' if p=='index.html' else 'downloads' if p=='downloads.html' else None
 if kind:
  if not d.cssselect('.hub-faq'):
   (d.cssselect('main') or [body])[0].append(faq_element(kind))
  metadata={'faq':PUBLIC_FAQ[kind],'faq_visible':True}
 for n in html.fragments_fromstring(generate_head(p,cfg,COURSES,metadata)):
  if isinstance(n,str):continue
  n.set('data-platform','true');head.append(n)
 favicon=(ROOT/'favicon.svg').read_text().strip()
 from urllib.parse import quote
 favs=f'<link id="hub-favicon-fallback" rel="icon" type="image/svg+xml" href="data:image/svg+xml,{quote(favicon,safe="")}"><link rel="shortcut icon" href="{root}favicon.ico"><link rel="apple-touch-icon" sizes="180x180" href="{root}apple-touch-icon.png"><link id="hub-favicon" rel="icon" type="image/svg+xml" href="{root}favicon.svg">'
 for n in html.fragments_fromstring(favs):head.append(n)
 for url in ['assets/platform.css','assets/pdf-controls.css']:
  n=html.Element('link',rel='stylesheet',href=root+url,attrib={'data-platform':'true'});head.append(n)
 # Expose the same parsed one-line domain configuration to the browser.
 state={'root':root,'config':cfg,'page':pi,'courses':[{'slug':c['slug'],'title':c['title']} for c in COURSES]}
 s=html.Element('script',attrib={'data-platform':'true'});s.text='window.CSExitSite='+json.dumps(state,ensure_ascii=False).replace('</','<\\/')+';';head.append(s)
 for src in ['assets/platform.js','assets/pdf-controls.js']:
  n=html.Element('script',src=root+src,defer='defer',attrib={'data-platform':'true'});head.append(n)
 for n in reversed(html.fragments_fromstring(shell(root,p,cfg))):body.insert(0,n)
 body.append(html.fromstring(footer(cfg,root)))
 if not d.cssselect('#hub-content'):
  main=d.cssselect('main')
  if main:
   if main[0].get('id'):
    anchor=html.Element('span',id='hub-content');main[0].insert(0,anchor)
   else:main[0].set('id','hub-content')
   main[0].classes.add('hub-page')
 if p=='downloads.html':direct_pdf_links(d,root)
 route_links(d,cfg)
 # Semantic main for the original question selector which was only a fragment.
 if not d.cssselect('main'):
  wrap=html.Element('main');content=d.cssselect('#hub-content')
  if content:
   el=content[0];el.getparent().replace(el,wrap);wrap.append(el)
 for t in d.xpath('//table'):
  if t.getparent().get('class')=='hub-scroll':continue
  w=html.Element('div',attrib={'class':'hub-scroll','tabindex':'0','role':'region','aria-label':'Scrollable table'});t.getparent().replace(t,w);w.append(t)
 path.write_text('<!doctype html>\n'+etree.tostring(d,encoding='unicode',method='html'))
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--metadata-only',action='store_true');args=parser.parse_args();cfg=config();paths=public_page_paths(COURSES)
 if not args.metadata_only:
  for p in paths:make_static(p,cfg)
 for p in paths:decorate(p,cfg)
 exports={c['slug']:json.loads((ROOT/'assets/export-data'/f"{c['slug']}.json").read_text())for c in COURSES}
 (ROOT/'assets/search-index.json').write_text(json.dumps(generate_search_index(COURSES,exports),ensure_ascii=False))
 (ROOT/'sitemap.xml').write_text(generate_sitemap(paths,cfg,COURSES));(ROOT/'robots.txt').write_text(generate_robots(paths,cfg,COURSES))
 manifest=json.loads((ROOT/'maintenance/SOURCE_MANIFEST.pre-platform.json').read_text());entries=[]
 for f in manifest['files']:
  if f['copied_path'].endswith('.html'):
   src=ROOT/'maintenance/source-snapshots'/f['copied_path'];entries.append({'source_path':f['source_path'],'copied_path':f['copied_path'],'source_sha256':f['source_sha256'],'source_snapshot':str(src.relative_to(ROOT)),'snapshot_sha256':digest(src)})
  else:entries.append(f)
 (ROOT/'SOURCE_MANIFEST.json').write_text(json.dumps({'schema_version':2,'preservation':'Original educational source bytes archived privately; published readers are semantic static presentations.','files':entries},indent=2))
 print('Built',len(paths),'public HTML pages for',cfg['SITE_URL'])
if __name__=='__main__':main()
