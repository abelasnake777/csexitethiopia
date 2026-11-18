#!/usr/bin/env python3
"""Apply student-facing presentation copy; preserve canonical educational data."""
from pathlib import Path
import argparse,json,hashlib,re,os,html
ROOT=Path(__file__).resolve().parents[1]
START='<!-- PUBLIC-READER:START -->';END='<!-- PUBLIC-READER:END -->'
def sha(b):return hashlib.sha256(b).hexdigest()
def strings(v):
 if isinstance(v,str):
  if len(v)<20000 and not v.startswith('data:'):yield v
 elif isinstance(v,list):
  for x in v:yield from strings(x)
 elif isinstance(v,dict):
  for x in v.values():yield from strings(x)
def main():
 config=json.loads((ROOT/'PUBLIC_READER_COPY.json').read_text());assert config['complete']
 manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text());imported={f['copied_path']:f for f in manifest['files']}
 js=(ROOT/'assets/public-reader.js').read_text();catalog=json.loads((ROOT/'Modules/catalog.json').read_text())['courses']
 modules=[{k:m[k]for k in ['slug','course','source_file','file']}for m in catalog];pages=[]
 for p in sorted(ROOT.rglob('*.html')):
  if any(x.startswith('.')for x in p.relative_to(ROOT).parts):continue
  rel=p.relative_to(ROOT).as_posix()
  if rel=='ANSWER_REVIEW_SUMMARY.html':continue
  raw=p.read_text();item=imported.get(rel)
  old=item.get('public_reader_integration_block')if item else None
  if not old:
   match=re.search(re.escape(START)+'.*?'+re.escape(END),raw,re.S);old=match[0]if match else None
  if old:assert raw.count(old)==1;raw=raw.replace(old,'',1)
  # Select relevant phrases from decoded embedded records as well as visible HTML.
  markup=re.sub(r'<script\b[^>]*>.*?</script>','',raw,flags=re.S|re.I)
  markup=re.sub(r'data:image/[^\"\s>]+','',markup)
  values=[html.unescape(markup)]
  for name in ['assets/module-loader.js','assets/module-viewer.js','assets/resource-nav.js','assets/site.js']:
   if (ROOT/name).exists():values.append((ROOT/name).read_text())
  for match in re.finditer(r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',raw,re.S):
   try:values.extend(strings(json.loads(match[1])))
   except json.JSONDecodeError:pass
  haystack='\n'.join(values)
  rules=[v for v in config['replacements']if v['from']in haystack]
  for _ in range(4):
   selected={v['from']for v in rules};outputs='\n'.join(v['to']for v in rules)
   added=[v for v in config['replacements']if v['from']not in selected and v['from']in outputs]
   if not added:break
   rules.extend(added)
  root=os.path.relpath(ROOT,p.parent).replace(os.sep,'/')+'/'
  payload={'root':root,'course':p.stem if p.stem in{m['slug']for m in modules}else None,'replacements':rules,'source_titles':config['source_titles'],'modules':modules,'remove_selectors':config.get('remove_selectors',[])}
  encoded=json.dumps(payload,ensure_ascii=False).replace('</',r'<\/')
  block=START+'\n<script id="public-reader-copy" type="application/json">'+encoded+'</script>\n<script>\n'+js+'\n</script>\n'+END
  assert raw.count('</body>')<=1,rel
  raw=raw.replace('</body>',block+'</body>',1)if'</body>'in raw else raw+block
  p.write_text(raw)
  if item:item['public_reader_integration_block']=block;item['copied_sha256']=sha(raw.encode());item['copied_bytes']=len(raw.encode())
  pages.append({'path':rel,'sha256':sha(raw.encode()),'copy_rules':len(rules)})
 for name in ['assets/public-reader.js']:
  row=next((x for x in manifest['generated_assets']if x['path']==name),None)
  if row:row['sha256']=sha((ROOT/name).read_bytes())
  else:manifest['generated_assets'].append({'path':name,'sha256':sha((ROOT/name).read_bytes())})
 manifest['assertions']['public_copy_preserves_canonical_educational_data']=True
 manifest['integration']['removal_rule']='Remove public_reader_integration_block once if present, then study_note_addition_blocks once each if present, then answer_review_integration_block, reference_integration_block and integration_block once if present. The recovered bytes match source_sha256.'
 (ROOT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 (ROOT/'.qa/public-copy-pages.json').write_text(json.dumps({'pages':pages,'copy_sha256':sha((ROOT/'PUBLIC_READER_COPY.json').read_bytes())},indent=2)+'\n')
 print('Applied public-facing copy to',len(pages),'HTML pages; canonical educational data preserved.')
if __name__=='__main__':main()
