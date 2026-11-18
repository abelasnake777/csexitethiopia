"""Static files suitable for the public hosting upload."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PRIVATE_NAMES={'SOURCE_MANIFEST.json','QUESTION_REFERENCE_AUDIT.json','STUDY_NOTE_ANSWER_REVIEW.json','VERIFICATION.json','ANSWER_COMPLETENESS_AUDIT.json','STUDY_NOTE_SUPPORT.json','STUDY_NOTE_SUPPORT_AUDIT.json','PUBLIC_READER_COPY.json','PUBLIC_COPY_AUDIT.json','Outline_Coverage_Audit.json','ANSWER_REVIEW_SUMMARY.html'}
PRIVATE_PATHS={'Modules/catalog.json','assets/public-reader.js','assets/resource-nav.js','assets/resource-nav.css','assets/study-note-answers.js','assets/study-note-answers.css'}
def public_files():
 files=[ROOT/n for n in ['index.html','Complete_CS_Exit_Study_Guide.html','.htaccess','robots.txt','sitemap.xml','site.config.js','downloads.html','search.html','favicon.ico','favicon.svg','apple-touch-icon.png']]
 for folder in ['assets','Questions/Interactive_Study_Guides','Outlines','Modules']:
  files.extend(p for p in(ROOT/folder).rglob('*')if p.is_file()and not (folder=='assets' and ('qa' in p.relative_to(ROOT/'assets').parts or p.relative_to(ROOT).as_posix().startswith(('assets/pdf/fonts/','assets/export-data/'))))and not p.name.startswith('.')and p.name not in PRIVATE_NAMES and p.relative_to(ROOT).as_posix()not in PRIVATE_PATHS and not(folder=='Outlines'and p.suffix=='.docx'))
 return sorted(set(files))
