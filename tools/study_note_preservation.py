"""Recover the pre-expansion study guide by removing authorized additive blocks."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE_SHA256='03aa84b65bad3099e42f64357392887c2981cd4e19d210044e2a25b255544c3c'
def without_public_block(raw,manifest=None):
    if manifest is None:manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
    entry=next(f for f in manifest['files'] if f['copied_path']=='Complete_CS_Exit_Study_Guide.html')
    public=entry.get('public_reader_integration_block')
    if public:
        assert raw.count(public)==1,'Missing/repeated public reader block'
        raw=raw.replace(public,'',1)
    return raw

def strip_additions(raw,manifest=None):
    if manifest is None:manifest=json.loads((ROOT/'SOURCE_MANIFEST.json').read_text())
    entry=next(f for f in manifest['files'] if f['copied_path']=='Complete_CS_Exit_Study_Guide.html')
    raw=without_public_block(raw,manifest)
    for block in entry.get('study_note_addition_blocks',[]):
        assert raw.count(block)==1,'Missing/repeated study-note addition block'
        raw=raw.replace(block,'',1)
    return raw

def verify_base(raw):
    restored=strip_additions(raw)
    assert hashlib.sha256(restored.encode()).hexdigest()==BASE_SHA256,'Existing study-guide bytes changed beyond authorized additions'
    return restored
