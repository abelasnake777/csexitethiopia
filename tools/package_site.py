"""Create a cPanel-ready ZIP from existing static files; no build is performed."""
from pathlib import Path
import argparse,zipfile,hashlib
ROOT=Path(__file__).resolve().parent.parent
parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT.parent/'csexitethiopia-upload.zip');args=parser.parse_args()
files=[ROOT/n for n in ['index.html','Complete_CS_Exit_Study_Guide.html','.htaccess','robots.txt','SOURCE_MANIFEST.json','QUESTION_REFERENCE_AUDIT.json','STUDY_NOTE_ANSWER_REVIEW.json','ANSWER_REVIEW_SUMMARY.html','VERIFICATION.json','ANSWER_COMPLETENESS_AUDIT.json','STUDY_NOTE_SUPPORT.json','STUDY_NOTE_SUPPORT_AUDIT.json']]
for folder in ['assets','Questions/Interactive_Study_Guides','Outlines','Modules']:
 files.extend(p for p in(ROOT/folder).rglob('*')if p.is_file()and not p.name.startswith('.~lock'))
assert all(p.exists()for p in files);args.output.parent.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED)as archive:
 for p in sorted(set(files)):archive.write(p,p.relative_to(ROOT))
 assert 'index.html'in archive.namelist()and not archive.testzip()
print('Archive:',args.output);print('Files:',len(set(files)));print('SHA256:',hashlib.sha256(args.output.read_bytes()).hexdigest())
