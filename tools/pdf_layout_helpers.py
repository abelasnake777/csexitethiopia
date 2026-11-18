"""Typography and flowables shared only by the static PDF builder.

No global compatibility normalization: ², ₁, mathematical operators and code
are retained. Only mathematical alphabet presentation letters are de-styled.
"""
from __future__ import annotations

import html
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from fontTools.ttLib import TTFont as FontToolsFont
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Flowable, Paragraph
from reportlab.platypus.flowables import _listWrapOn
from reportlab.platypus.doctemplate import NullActionFlowable

INK = colors.HexColor('#162b3c')
TEAL = colors.HexColor('#087f83')
MUTED = colors.HexColor('#526273')
PALE = colors.HexColor('#eef6f6')
RULE = colors.HexColor('#cbd9df')
FONT_FILES = {
    'Book': 'NotoSerif-Regular.ttf',
    'BookBold': 'NotoSerif-Bold.ttf',
    'BookItalic': 'NotoSerif-Italic.ttf',
    'Sans': 'NotoSans-Regular.ttf',
    'SansBold': 'NotoSans-Bold.ttf',
    'Code': 'NotoSansMono-Regular.ttf',
    'Math': 'NotoSansMath-Regular.ttf',
    'Symbols': 'NotoSansSymbols2-Regular.ttf',
    'Wide': 'DejaVuSans.ttf',
    'Ethiopic': 'NotoSansEthiopic-Regular.ttf',
}
FONT_MAPS: dict[str, set[int]] = {}
NORMALIZATIONS: dict[str, str] = {}
SEEN: set[str] = set()
MISSING: set[str] = set()
# Explicit legacy font encodings found in extracted module quotations. Symbol
# mathematical glyphs retain their meanings; decorative list markers become •.
SOURCE_SYMBOLS = {
    '\uf020':' ', '\uf03d':'=', '\uf02d':'-', '\uf051':'Θ', '\uf057':'Ω',
    '\uf064':'δ', '\uf077':'ω', '\uf0b9':'≠', '\uf0ce':'∈', '\uf0e5':'∑',
    '\uf0e0':'→', '\uf0e8':'→', '\uf0f0':'⇒', '\uf0fc':'✓',
    '\uf0a7':'•', '\uf06c':'•', '\uf0b7':'•', '\uf071':'•', '\uf0d8':'•',
    '\uf046':'•', '\uf076':'•', '\uf07d':'•', '\uf0a8':'•', '\uf06e':'•',
    '\uf0c6':'•', '\uf097':'•', '\uf096':'•', '\uf043':'•', '\uf040':'•',
    '\uf0a2':'•', '：':':', '\U0001f784':'•',
}


def setup_fonts(directory: Path):
    for name, filename in FONT_FILES.items():
        path = directory / filename
        if not path.is_file():
            raise FileNotFoundError(f'Embedded PDF font missing: {path}')
        with FontToolsFont(path) as font:
            FONT_MAPS[name] = set(font.getBestCmap())
        pdfmetrics.registerFont(TTFont(name, str(path)))
    pdfmetrics.registerFontFamily('Book', normal='Book', bold='BookBold', italic='BookItalic', boldItalic='BookBold')
    pdfmetrics.registerFontFamily('Sans', normal='Sans', bold='SansBold', italic='Sans', boldItalic='SansBold')
    pdfmetrics.registerFontFamily('Code', normal='Code', bold='Code', italic='Code', boldItalic='Code')


def normalize(text: object) -> str:
    text = '' if text is None else str(text)
    result = []
    for char in text:
        cp = ord(char)
        name = unicodedata.name(char, '')
        replacement = char
        if char in SOURCE_SYMBOLS:
            replacement = SOURCE_SYMBOLS[char]
        elif (0x1D400 <= cp <= 0x1D7FF or 0x2100 <= cp <= 0x214F) and (
            'MATHEMATICAL' in name or any(x in name for x in ('SCRIPT', 'DOUBLE-STRUCK', 'BLACK-LETTER'))
        ):
            # Compatibility decomposition is applied to this ONE alphabet glyph.
            # It is never applied to the surrounding mathematical expression.
            replacement = unicodedata.normalize('NFKC', char)
        elif char in '\u2010\u2011\u2012\u2013\u2014':
            replacement = '-'
        elif char in '\u200b\ufeff\u00ad':
            replacement = ''
        elif cp < 32 and char not in '\n\t\r':
            replacement = ' '
        if replacement != char:
            NORMALIZATIONS[char] = replacement
        result.append(replacement)
    return ''.join(result).replace('\r\n', '\n').replace('\r', '\n')


@lru_cache(maxsize=8192)
def choose_font(char: str, preferred: str) -> str:
    if char.isspace():
        return preferred
    for font in (preferred, 'Math', 'Wide', 'Symbols', 'Ethiopic', 'Sans'):
        if ord(char) in FONT_MAPS[font]:
            return font
    MISSING.add(char)
    raise ValueError(f'Unsupported visible glyph U+{ord(char):04X} {unicodedata.name(char, "UNKNOWN")}: {char!r}')


def font_runs(text: str, preferred='Book') -> str:
    text = normalize(text)
    SEEN.update(text)
    runs = []
    current_font, buf = None, []
    for char in text:
        font = choose_font(char, preferred)
        if font != current_font:
            if buf:
                runs.append(f'<font name="{current_font}">{html.escape("".join(buf))}</font>')
            current_font, buf = font, []
        buf.append(char)
    if buf:
        runs.append(f'<font name="{current_font}">{html.escape("".join(buf))}</font>')
    return ''.join(runs)


def rich(text: object, preferred='Book') -> str:
    """Small, escaped Markdown subset; source HTML can never become PDF markup."""
    text = normalize(text)
    token_re = r'(`[^`\n]+`|\*\*[^*\n]+\*\*|\[[^\]\n]+\]\(https?://[^)\s]+\))'
    parts = re.split(token_re, text)
    result = []
    for part in parts:
        if part.startswith('`') and part.endswith('`') and len(part) > 1:
            result.append(font_runs(part[1:-1], 'Code'))
        elif part.startswith('**') and part.endswith('**') and len(part) > 3:
            result.append(font_runs(part[2:-2], 'SansBold' if preferred.startswith('Sans') else 'BookBold'))
        elif re.fullmatch(r'\[[^\]\n]+\]\(https?://[^)\s]+\)', part):
            label, url = re.match(r'\[([^]]+)\]\((.+)\)', part).groups()
            result.append(f'<link href="{html.escape(url, quote=True)}" color="#087f83">{font_runs(label, preferred)}</link>')
        else:
            result.append(font_runs(part, preferred).replace('\n', '<br/>'))
    return ''.join(result)


class FitGroup(Flowable):
    """Keep a logical unit intact if it fits a full page; otherwise release it.

    Unlike shrinking containers this never reduces the 10.5-11 pt body/code.
    An over-page question releases its separately grouped stem and options.
    """
    def __init__(self, content, page_height):
        super().__init__()
        self.content = content
        self.page_height = page_height

    def measured_content(self):
        result = []
        for flow in self.content:
            result.extend(flow.measured_content() if isinstance(flow, FitGroup) else [flow])
        return result

    def wrap(self, width, height):
        self.width, self.height = _listWrapOn(self.measured_content(), width, self.canv)
        # Always split: nested FitGroups must expose their content to Platypus.
        return self.width, 0xffffff

    def split(self, width, height):
        self.width, self.height = _listWrapOn(self.measured_content(), width, self.canv)
        if self.height <= height + 0.01 or self.height > self.page_height:
            return [NullActionFlowable()] + self.content[:]
        return []

    def draw(self):
        raise RuntimeError('FitGroup must release its flowables before drawing')


class ContextMarker(Flowable):
    def __init__(self, title=None, question=None, bookmark=None, level=0):
        super().__init__()
        self.title, self.question = title, question
        self.bookmark, self.level = bookmark, level
        self.width = self.height = 0

    def draw(self):
        doc = self.canv._doctemplate
        if self.title is not None:
            doc.course_title = self.title
        if self.question is not None:
            doc.active_question = self.question
            if doc.first_question is None:
                doc.first_question = self.question
            doc.last_question = self.question
        if self.bookmark:
            key, title = self.bookmark
            self.canv.bookmarkPage(key)
            self.canv.addOutlineEntry(normalize(title), key, self.level, closed=self.level > 0)


class ContinuedParagraph(Paragraph):
    """A long explanation gains an explicit label on its next page."""
    def split(self, width, height):
        pieces = super().split(width, height)
        if len(pieces) == 2 and getattr(self, 'continuation_style', None):
            pieces[0].continuation_style = self.continuation_style
            pieces[1].continuation_style = self.continuation_style
            label = Paragraph(rich('Explanation continued', 'SansBold'), self.continuation_style)
            # Force the continuation label and at least two text lines to move together.
            pieces[1].spaceBefore = 0
            return [pieces[0], label, pieces[1]]
        return pieces


def validate_text_coverage(root):
    """Compare every canonical text field and every merged native body page."""
    import json
    import pymupdf as fitz
    import pdf_layout_helpers as ty
    ROOT = Path(root)
    def plain(value):
        s=ty.normalize(value)
        s=re.sub(r'```[^\n]*\n(.*?)```',r'\1',s,flags=re.S)
        s=re.sub(r'\[([^]]+)\]\(https?://[^)\s]+\)',r'\1',s)
        s=re.sub(r'`([^`\n]+)`',r'\1',s)
        s=re.sub(r'\*\*([^*\n]+)\*\*',r'\1',s)
        return re.sub(r'\s+','',s)
    
    
    def fields(blocks):
        for b in blocks:
            if b['type'] in ('paragraph','heading','code','source'):
                yield b.get('text','')
            elif b['type']=='table':
                yield from b.get('headers',[])
                for r in b.get('rows',[]):yield from r
            elif b['type']=='list': yield from cues(b.get('items',[]))
            elif b['type']=='callout':
                yield b.get('title','');yield from fields(b.get('blocks',[]))
    
    
    def cues(items):
        for c in items:
            yield c['text'];yield from cues(c.get('children',[]))
    
    
    def answer(a):
        yield a.get('text','');yield a.get('explanation','')
        for choice in a.get('choices',[]):yield choice.get('explanation','')
        for e in a.get('evidence',[]):yield e.get('section_id','');yield e.get('quote','')
        for ref in a.get('module_refs',[]):yield ref.get('title','');yield ref.get('quote','')
    
    
    def qfields(q):
        yield q['id'];yield q.get('stem','');yield q.get('hint','')
        for o in q.get('options',[]):yield o['text']
        yield from answer(q.get('answer',{}));yield from q.get('sources',[])
        for v in q.get('variants',[]):
            yield v.get('source','');yield v.get('stem','')
            for o in v.get('options',[]):yield o['text']
            yield from answer(v.get('answer',{}))
    
    
    def bodytext(page):
        return re.sub(r'Page \d+ of \d+\s*$', '',page.get_text()).strip()
    
    catalog=json.loads((ROOT/'assets/export-data/catalog.json').read_text())
    report={'courses':[],'counts':{},'failures':[]};allseq={k:[] for k in ['questions','notes','outlines']};counts={k:0 for k in ['questions','variants','note_evidence','module_refs','choice_contrasts','note_sections','outline_topics','outline_cues','text_fields_checked']}
    for row in catalog['courses']:
        c=json.loads((ROOT/'assets/export-data'/(row['slug']+'.json')).read_text());entry={'slug':c['slug'],'resources':{}}
        counts['questions']+=len(c['questions']);counts['variants']+=sum(len(q.get('variants',[])) for q in c['questions'])
        counts['note_sections']+=len(c['notes']);counts['outline_topics']+=len(c['outlines'])
        for q in c['questions']:
            for a in [q['answer']]+[v.get('answer',{}) for v in q.get('variants',[])]:
                for key in ['note_evidence','module_refs','choice_contrasts']:
                    counts[key]+=len(a.get({'note_evidence':'evidence','module_refs':'module_refs','choice_contrasts':'choices'}[key],[]))
        for kind in allseq:
            f=ROOT/'assets/pdf/fragments'/kind/(c['slug']+'.pdf')
            with fitz.open(f) as doc:
                texts=[bodytext(p) for p in doc];text=plain('\n'.join(p.get_text(clip=fitz.Rect(40,63,555,787)).replace('Explanation continued','') for p in doc));n=len(doc)
                allseq[kind].extend(texts)
            expected=[]
            if kind=='questions':
                for q in c['questions']:expected.extend(qfields(q))
            elif kind=='notes':
                for note in c['notes']:expected.extend([note['id'],note['title'],*fields(note['blocks'])])
            else:
                expected.extend(fields(c.get('outline_intro',[])))
                for o in c['outlines']:
                    expected.append(o['title']); cc=list(cues(o['cues'])); counts['outline_cues']+=len(cc);expected.extend(cc)
            misses=[]
            for value in expected:
                if not value:continue
                counts['text_fields_checked']+=1
                if plain(value) not in text:misses.append(str(value)[:160])
            single=ROOT/'assets/pdf'/kind/(c['slug']+'.pdf')
            with fitz.open(single) as doc:
                body=[bodytext(p) for p in list(doc)[-n:]]
                if body!=texts:report['failures'].append({'slug':c['slug'],'kind':kind,'issue':'single body differs from fragment'})
            entry['resources'][kind]={'pages':n,'fields_checked':len(expected),'missing':misses}
            if misses:report['failures'].append({'slug':c['slug'],'kind':kind,'missing':misses})
        report['courses'].append(entry)
        print('COVERAGE',c['slug'],flush=True)
    for kind,expected in allseq.items():
        with fitz.open(ROOT/'assets/pdf'/kind/'all-courses.pdf') as doc:
            got=[bodytext(p) for p in list(doc)[-len(expected):]]
            if got!=expected:report['failures'].append({'kind':kind,'issue':'all-course body differs from fragments'})
            if kind=='notes':
                text=plain('\n'.join(p.get_text(clip=fitz.Rect(40,63,555,787)).replace('Explanation continued','') for p in doc))
                intro=json.loads((ROOT/'assets/export-data/study-introduction.json').read_text())
                for note in intro:
                    counts['note_sections']+=1
                    for value in [note['id'],note['title'],*fields(note['blocks'])]:
                        counts['text_fields_checked']+=1
                        if plain(value) not in text:report['failures'].append({'introduction':note['id'],'missing':value})
    report['counts']=counts
    (ROOT/'assets/pdf/qa/content-coverage.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'counts':counts,'failures':report['failures']}))
    return report
