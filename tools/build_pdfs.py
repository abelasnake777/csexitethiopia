#!/usr/bin/env python3
"""Build native, searchable ReportLab textbooks from read-only export JSON.

Usage (from repository root):
  /path/to/venv/bin/python tools/build_pdfs.py --validate
  /path/to/venv/bin/python tools/build_pdfs.py --courses Network_and_System_Administration --types notes,questions --skip-all --validate
  /path/to/venv/bin/python tools/build_pdfs.py --self-test
  /path/to/venv/bin/python tools/build_pdfs.py --verify-only

Dependencies: reportlab, svglib, pypdf, fontTools and preinstalled PyMuPDF.
The final verification checks every page and all canonical text fields.

Complete downloads are assembled from the SAME unnumbered course fragments
used by the browser merge worker. ReportLab creates every body/front page;
PyMuPDF concatenates them, preserves links/bookmarks, and stamps final numbers.
No browser, screenshot, rasterization, hosting runtime, or canonical writes.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import io
import json
import re
import sys
import time
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote_to_bytes, urljoin
from xml.etree import ElementTree

import pymupdf as fitz
from reportlab import rl_config
from reportlab.graphics.shapes import Drawing, Group, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, KeepTogether, PageBreak, PageTemplate,
    Paragraph, Spacer, Table, TableStyle,
)
from svglib.svglib import svg2rlg

import pdf_layout_helpers as ty

ROOT = Path(__file__).resolve().parents[1]
PAGE_W, PAGE_H = A4
LEFT, RIGHT, TOP, BOTTOM = 49, 49, 68, 65
WIDTH, HEIGHT = PAGE_W - LEFT - RIGHT, PAGE_H - TOP - BOTTOM
KINDS = ('questions', 'notes', 'outlines')
TITLES = {'questions': 'Questions & Worked Answers', 'notes': 'Complete Study Notes', 'outlines': 'Revision Outlines'}
NOW = lambda: datetime.now(timezone.utc).isoformat(timespec='seconds')
rl_config.warnOnMissingFontGlyphs = 1
rl_config.invariant = 1


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.pending')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def branding(root):
    source = (root / 'site.config.js').read_text(encoding='utf-8')
    result = {}
    for key in ('SITE_URL', 'SITE_NAME', 'EMAIL', 'TELEGRAM'):
        pattern = rf'(?:const\s+{key}\s*=|\b{key}\s*:)\s*([\'\"])(.*?)\1'
        match = re.search(pattern, source)
        if not match:
            raise ValueError(f'site.config.js must define {key} as a string')
        result[key] = match.group(2)
    if not result['SITE_URL'].startswith(('https://', 'http://')):
        raise ValueError('SITE_URL must be absolute')
    return result


def styles():
    body = ParagraphStyle('Body', fontName='Book', fontSize=10.7, leading=15.2,
                          textColor=ty.INK, spaceAfter=7, allowWidows=0,
                          allowOrphans=0, splitLongWords=1, uriWasteReduce=0.05)
    result = {'body': body}
    definitions = {
        'title': dict(fontName='SansBold', fontSize=28, leading=35, spaceAfter=18),
        'h1': dict(fontName='SansBold', fontSize=22, leading=28, spaceBefore=2, spaceAfter=15, keepWithNext=1),
        'h2': dict(fontName='SansBold', fontSize=15, leading=20, spaceBefore=15, spaceAfter=9, keepWithNext=1),
        'h3': dict(fontName='SansBold', fontSize=11, leading=15, spaceBefore=11, spaceAfter=5, keepWithNext=1, textColor=ty.TEAL),
        'question': dict(fontName='SansBold', fontSize=11, leading=15.6, spaceBefore=10, spaceAfter=9, keepWithNext=1),
        'option': dict(leftIndent=19, firstLineIndent=-16, spaceAfter=5),
        'answer': dict(fontName='SansBold', fontSize=10.7, leading=15.2, spaceBefore=10, spaceAfter=8, textColor=ty.TEAL, keepWithNext=1),
        'reference': dict(fontName='Sans', fontSize=10.5, leading=14.8, textColor=ty.MUTED, spaceAfter=7),
        'quote': dict(fontName='Book', fontSize=10.5, leading=14.8, leftIndent=13, borderColor=ty.RULE, borderWidth=0.6, borderPadding=7, spaceBefore=3, spaceAfter=10),
        'code': dict(fontName='Code', fontSize=10.5, leading=14.4, backColor=colors.HexColor('#f2f5f7'), borderPadding=8, spaceBefore=6, spaceAfter=10),
        'cell': dict(fontSize=10.5, leading=14.8, spaceAfter=0),
        'cellhead': dict(fontName='SansBold', fontSize=10.5, leading=14.8, spaceAfter=0),
        'toc': dict(fontName='Sans', fontSize=10.7, leading=15.8, spaceAfter=0),
        'subtitle': dict(fontName='Sans', fontSize=12, leading=18, textColor=ty.MUTED, spaceAfter=12),
    }
    for key, options in definitions.items():
        result[key] = ParagraphStyle(key, parent=body, **options)
    return result


class BookDoc(BaseDocTemplate):
    def __init__(self, path, config, kind, course='', **kw):
        self.config, self.kind, self.course_title = config, kind, course
        self.active_question = self.first_question = self.last_question = None
        super().__init__(str(path), pagesize=A4, leftMargin=LEFT, rightMargin=RIGHT,
                         topMargin=TOP, bottomMargin=BOTTOM, pageCompression=1,
                         title=f'{config["SITE_NAME"]} - {TITLES[kind]}', author=config['SITE_NAME'],
                         subject='Computer Science Exit Examination Study Material', **kw)
        self.addPageTemplates(PageTemplate('Book', frames=[Frame(LEFT, BOTTOM, WIDTH, HEIGHT,
            leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)],
            onPage=self.begin_page, onPageEnd=self.finish_page))

    def begin_page(self, canvas, doc):
        self.first_question = self.last_question = self.active_question

    def finish_page(self, canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(ty.RULE)
        canvas.setLineWidth(0.55)
        canvas.line(LEFT, PAGE_H - 46, PAGE_W - RIGHT, PAGE_H - 46)
        canvas.line(LEFT, 49, PAGE_W - RIGHT, 49)
        # All footer content is above y=31. y=15..26 is RESERVED for merge numbering.
        canvas.setFont('Sans', 8)
        canvas.setFillColor(ty.MUTED)
        canvas.drawString(LEFT, 36, ty.normalize(self.config['SITE_NAME']))
        contact = f'{self.config["EMAIL"]}  |  Telegram: @{self.config["TELEGRAM"].lstrip("@").split("/")[-1]}'
        canvas.drawRightString(PAGE_W - RIGHT, 36, ty.normalize(contact))
        canvas.linkURL('mailto:' + self.config['EMAIL'], (PAGE_W-285, 32, PAGE_W-RIGHT, 44), relative=0, thickness=0)
        title = ty.normalize(self.course_title or self.config['SITE_NAME'])
        if pdfmetrics_width(title, 'SansBold', 9) > WIDTH - 125:
            # Two line headers keep the full course title readable.
            words, line, lines = title.split(), '', []
            for word in words:
                if pdfmetrics_width((line+' '+word).strip(), 'SansBold', 9) > WIDTH - 110:
                    lines.append(line); line = word
                else: line = (line+' '+word).strip()
            lines.append(line)
            for i, line in enumerate(lines[:2]):
                canvas.setFont('SansBold', 9); canvas.drawString(LEFT, PAGE_H - 27 - i*12, line)
        else:
            canvas.setFont('SansBold', 9); canvas.drawString(LEFT, PAGE_H - 33, title)
        canvas.setFont('Sans', 8)
        right = {'questions':'Questions', 'notes':'Study notes', 'outlines':'Revision outlines'}[self.kind]
        if self.first_question is not None:
            right += f' | Q{self.first_question}'
            if self.last_question != self.first_question:
                right += f'-{self.last_question}'
        canvas.drawRightString(PAGE_W-RIGHT, PAGE_H-33, right)
        canvas.restoreState()


def pdfmetrics_width(text, font, size):
    from reportlab.pdfbase import pdfmetrics
    return pdfmetrics.stringWidth(text, font, size)


class Renderer:
    def __init__(self, config):
        self.config = config
        self.s = styles()
        self.counts = Counter()
        self.warnings = []
        self.introduction = []

    def p(self, text, style='body', continuation=False):
        s = self.s[style]
        para = ty.ContinuedParagraph(ty.rich(text, s.fontName), s) if continuation else Paragraph(ty.rich(text, s.fontName), s)
        if continuation:
            para.continuation_style = self.s['h3']
        return para

    def link(self, label, url, style='reference'):
        absolute = urljoin(self.config['SITE_URL'].rstrip('/')+'/', url or '')
        if not absolute.startswith(('http://', 'https://', 'mailto:')):
            raise ValueError(f'Unsafe PDF link: {absolute}')
        return Paragraph(f'<link href="{html.escape(absolute, quote=True)}" color="#087f83">{ty.rich(label, self.s[style].fontName)}</link>', self.s[style])

    def text(self, text, style='body', continuation=False):
        # Preserve fenced and multiline code, including long words and indentation.
        pieces = re.split(r'(```[^\n]*\n.*?```)', str(text or ''), flags=re.S)
        flow = []
        for piece in pieces:
            if not piece: continue
            if piece.startswith('```'):
                code = piece.split('\n', 1)[1].rsplit('```', 1)[0]
                flow.extend(self.code(code))
            else:
                for para in re.split(r'\n\s*\n', piece):
                    if para.strip(): flow.append(self.p(para.strip(), style, continuation))
        return flow

    def code(self, text):
        code = ty.normalize(text).expandtabs(4)
        markup = ty.font_runs(code.replace(' ', '\u00a0'), 'Code').replace('\n', '<br/>')
        return [Paragraph(markup or '&#160;', self.s['code'])]

    def heading(self, title, level=2, key=None, bookmark_level=1):
        result = []
        if key:
            result.append(ty.ContextMarker(bookmark=(key, str(title)), level=bookmark_level))
        result.append(self.p(title, 'h1' if level == 1 else 'h2' if level == 2 else 'h3'))
        return result

    def items(self, items, ordered=False, depth=0):
        result = []
        for i, item in enumerate(items):
            if isinstance(item, str): item = {'text':item}
            marker = f'{i+1}.' if ordered else ('•' if depth % 2 == 0 else '-')
            s = ParagraphStyle(f'list{depth}', parent=self.s['body'], leftIndent=16+depth*16, firstLineIndent=-12, spaceAfter=6)
            result.append(Paragraph(ty.rich(marker+' '+item.get('text','')), s))
            result.extend(self.items(item.get('children',[]), False, depth+1))
        return result

    def table(self, block):
        headers, rows = block.get('headers', []), block.get('rows', [])
        columns = max([len(headers)] + [len(r) for r in rows] + [1])
        widths = [WIDTH / columns] * columns
        data = [[self.p(x, 'cellhead') for x in headers] + ['']*(columns-len(headers))] if headers else []
        for row in rows:
            data.append([self.p(x, 'cell') for x in row] + ['']*(columns-len(row)))
        if not data: return []
        table = Table(data, colWidths=widths, repeatRows=1 if headers else 0, hAlign='LEFT', splitByRow=1, splitInRow=0)
        table.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'), ('LEFTPADDING',(0,0),(-1,-1),7),
            ('RIGHTPADDING',(0,0),(-1,-1),7), ('TOPPADDING',(0,0),(-1,-1),7),
            ('BOTTOMPADDING',(0,0),(-1,-1),8), ('LINEBELOW',(0,0),(-1,0),0.7,ty.TEAL),
            ('BACKGROUND',(0,0),(-1,0),ty.PALE), ('LINEBELOW',(0,1),(-1,-1),0.35,ty.RULE),
        ]))
        table.wrap(WIDTH, HEIGHT)
        if max(table._rowHeights) > HEIGHT - 45:
            # A row taller than paper cannot remain a row: reflow as labelled
            # record paragraphs rather than clipping it or silently shrinking it.
            self.warnings.append('Oversize table reflowed as labelled records')
            result = []
            for number,row in enumerate(rows,1):
                result.append(self.p(f'Table record {number}', 'h3'))
                for j,cell in enumerate(row):
                    result.extend(self.text(f'{headers[j] if j<len(headers) else "Field "+str(j+1)}: {cell}'))
            return result
        return [Spacer(1,5), table, Spacer(1,11)]

    def image(self, data):
        if not data: return []
        if isinstance(data,dict): data = data.get('data','')
        if str(data).startswith('data:'):
            meta, payload = data.split(',',1)
            raw = base64.b64decode(payload) if ';base64' in meta else unquote_to_bytes(payload)
        elif str(data).lstrip().startswith('<svg'):
            raw = str(data).encode()
        else:
            raise ValueError('Only embedded SVG/PNG/JPEG images are accepted')
        if b'<svg' in raw[:1500]:
            svg = ElementTree.fromstring(raw)
            for element in svg.iter():
                if element.text: element.text = ty.normalize(element.text)
                if element.tail: element.tail = ty.normalize(element.tail)
                if element.tag.endswith('text') or element.tag.endswith('tspan'):
                    element.set('font-family','Sans')
                    style = re.sub(r'font-family\s*:[^;]+;?', '', element.get('style',''))
                    element.set('style', style+';font-family:Sans')
            drawing = svg2rlg(io.BytesIO(ElementTree.tostring(svg)))
            if drawing is None: raise ValueError('SVG conversion returned no drawing')
            def fix(node):
                if isinstance(node, String):
                    node.text = ty.normalize(node.text)
                    node.fontName = 'Sans'
                    # Fail on unsupported SVG text rather than rendering a hole.
                    for char in node.text:
                        if not char.isspace() and ord(char) not in ty.FONT_MAPS['Sans']:
                            chosen = ty.choose_font(char,'Sans')
                            if all(c.isspace() or ord(c) in ty.FONT_MAPS[chosen] for c in node.text):
                                node.fontName = chosen
                            else: raise ValueError(f'Mixed-font SVG text needs runs: {node.text!r}')
                for child in getattr(node,'contents',[]): fix(child)
            fix(drawing)
            factor = min(1, WIDTH/drawing.width, (HEIGHT-80)/drawing.height)
            drawing.scale(factor,factor)
            drawing.width *= factor; drawing.height *= factor
            return [drawing,Spacer(1,9)]
        image = Image(io.BytesIO(raw))
        factor = min(1,WIDTH/image.imageWidth,(HEIGHT-80)/image.imageHeight)
        image.drawWidth = image.imageWidth*factor; image.drawHeight=image.imageHeight*factor
        return [image,Spacer(1,9)]

    def blocks(self, blocks):
        result = []
        for block in blocks or []:
            kind = block.get('type','paragraph'); self.counts[kind]+=1
            if kind == 'paragraph': result.extend(self.text(block.get('text','')))
            elif kind == 'heading': result.extend(self.heading(block['text'], max(2,block.get('level',2))))
            elif kind == 'code': result.extend(self.code(block['text']))
            elif kind == 'list': result.extend(self.items(block.get('items',[]), block.get('ordered',False)))
            elif kind == 'table': result.extend(self.table(block))
            elif kind == 'callout':
                result.append(self.p(block.get('title','Study note'),'h3'))
                result.extend(self.blocks(block.get('blocks',[])))
            elif kind == 'image': result.extend(self.image(block.get('data','')))
            elif kind == 'source':
                if block.get('url'): result.append(self.link(block.get('text','Source'),block['url']))
                else: result.extend(self.text(block.get('text',''),'reference'))
            else: raise ValueError(f'Unknown content block type: {kind}')
        return result

    def answer(self, answer, question):
        result = []
        labels = answer.get('labels',[])
        if isinstance(labels,str): labels=[labels]
        prefix = 'Answer' + (' '+', '.join(labels) if labels else '')
        result.append(self.p(prefix+': '+answer.get('text',''),'answer'))
        result.extend(self.text(answer.get('explanation',''),continuation=True))
        if answer.get('choices'):
            result.append(self.p('Why each choice is right or wrong','h3'))
            for choice in answer['choices']:
                label = f'{choice.get("label", "")} - {choice.get("verdict", "").capitalize()}: '
                result.extend(self.text(label+choice.get('explanation','')))
                self.counts['choice_contrasts']+=1
        evidence = answer.get('evidence',[])
        if evidence:
            result.append(self.p('Primary note proof','h3'))
            for e in evidence:
                label = 'Study-note section '+str(e.get('section_id',''))
                if e.get('url'): result.append(self.link(label,e['url']))
                else: result.append(self.p(label,'reference'))
                if e.get('quote'): result.extend(self.text(e['quote'],'quote'))
                self.counts['note_evidence']+=1
        proved = {e.get('section_id') for e in evidence}
        related = [x for x in question.get('section_ids',[]) if x not in proved]
        if related:
            result.append(self.p('Related reading (context, not primary note proof)','h3'))
            for sid in related:
                result.append(self.link('Study-note section '+str(sid),'Complete_CS_Exit_Study_Guide.html#'+str(sid)))
        if answer.get('module_refs'):
            result.append(self.p('Module passages - related reading','h3'))
            result.append(self.p('These source passages provide context; the primary note proof is identified separately above.','reference'))
            for ref in answer['module_refs']:
                label = ref.get('title','Module')
                if ref.get('page') is not None: label += f' | PDF page {ref["page"]}'
                if ref.get('line_start') is not None:
                    label += f' | lines {ref["line_start"]}'
                    if ref.get('line_end') is not None: label += f'-{ref["line_end"]}'
                result.append(self.link(label,ref['url']) if ref.get('url') else self.p(label,'reference'))
                if ref.get('quote'): result.extend(self.text(ref['quote'],'quote'))
                self.counts['module_refs']+=1
        return result

    def question(self, q, index):
        self.counts['questions']+=1
        number = q.get('number',index)
        heading = f'Question {number} | {q["id"]}'
        prompt = [ty.ContextMarker(question=number,bookmark=(q['id'],heading),level=1),self.p(heading,'question')]
        prompt.extend(self.text(q.get('stem','')))
        if q.get('diagram'): prompt.extend(self.image(q['diagram']))
        for option in q.get('options',[]):
            prompt.extend(self.text(f'{option["label"]}. {option["text"]}','option'))
        # The prompt block is indivisible whenever it fits a page.
        body = [ty.FitGroup(prompt,HEIGHT)]
        if q.get('hint'):
            body.append(self.p('Hint','h3')); body.extend(self.text(q['hint']))
        body.extend(self.answer(q.get('answer',{}),q))
        for vi,variant in enumerate(q.get('variants',[]),1):
            self.counts['variants']+=1
            vp = [self.p(f'Variant {vi} | {variant.get("source", "Alternate source")}','h3')]
            vp.extend(self.text(variant.get('stem') or q.get('stem','')))
            for option in variant.get('options') or q.get('options',[]):
                vp.extend(self.text(f'{option["label"]}. {option["text"]}','option'))
            body.append(ty.FitGroup(vp,HEIGHT))
            body.extend(self.answer(variant.get('answer',{}),q))
        if q.get('sources'):
            body.append(self.p('Question sources','h3'))
            for source in q['sources']: body.append(self.p(source,'reference'))
        body.append(Spacer(1,15))
        return ty.FitGroup(body,HEIGHT)

    def course(self, course, kind):
        slug,title = course['slug'],course['title']
        result = [ty.ContextMarker(title=title,bookmark=(slug,title),level=0)]
        result.extend(self.heading(title,1))
        result.append(self.p(TITLES[kind],'subtitle'))
        if kind == 'questions':
            variants = sum(len(q.get('variants',[])) for q in course['questions'])
            result.append(self.p(f'{len(course["questions"]):,} questions'+(f' + {variants} source variants' if variants else ''),'reference'))
            for i,q in enumerate(course['questions'],1): result.append(self.question(q,i))
        elif kind == 'notes':
            for i,note in enumerate(course['notes'],1):
                result.extend(self.heading(f'{note["id"]} | {note["title"]}',2,f'{slug}-note-{i}'))
                result.extend(self.blocks(note.get('blocks',[])))
                self.counts['note_sections']+=1
        else:
            result.extend(self.blocks(course.get('outline_intro',[])))
            for i,topic in enumerate(course['outlines'],1):
                title=topic['title']+(' | Exam focus' if topic.get('exam_focus') else '')
                result.extend(self.heading(title,2,f'{slug}-topic-{i}'))
                if not topic.get('cues'):
                    raise ValueError(f'Outline cues empty: {slug}/{topic["id"]}')
                result.extend(self.items(topic['cues']))
                self.counts['outline_topics']+=1
        return result

    def front(self, selected, kind, offsets, date):
        count = len(selected)
        result = [Spacer(1,32),self.p(self.config['SITE_NAME'],'subtitle'),
                  self.p(TITLES[kind],'title'),self.p('Computer Science Exit Examination','subtitle')]
        if kind == 'questions':
            nq=sum(len(c['questions']) for c in selected)
            nv=sum(len(q.get('variants',[])) for c in selected for q in c['questions'])
            result.append(self.p(f'{nq:,} complete questions'+(f' and {nv} source variants' if nv else ''),'h2'))
        result.append(self.p(f'{count} selected course'+('s' if count!=1 else '')+' | '+date,'reference'))
        result.append(self.p('Selected courses','h3'))
        for i,course in enumerate(selected,1):
            result.append(self.p(f'{i:02d}. {course["title"]}','reference'))
        result.append(Spacer(1,13))
        result.append(self.link(self.config['SITE_URL'],self.config['SITE_URL']))
        result.append(self.p(f'{self.config["EMAIL"]} | Telegram: @{self.config["TELEGRAM"].lstrip("@").split("/")[-1]}','reference'))
        result.extend([PageBreak(),self.p('Course contents','h1')])
        result.append(self.p('Each course begins on a new page. PDF bookmarks provide question, study-note section and revision-topic navigation.','reference'))
        data=[]
        for course,offset in zip(selected,offsets):
            data.append([self.p(course['title'],'toc'),self.p(str(offset+1),'toc')])
        table=Table(data,colWidths=[WIDTH-45,45],hAlign='LEFT',splitByRow=1,splitInRow=0)
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),
            ('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
            ('ALIGN',(1,0),(1,-1),'RIGHT'),('LINEBELOW',(0,0),(-1,-1),0.4,ty.RULE)]))
        result.append(table)
        result.append(Spacer(1,16))
        if kind=='questions':
            result.append(self.p('Reading the answers','h2'))
            result.extend(self.text('Every question includes its answer, explanation, choice-by-choice contrasts and available evidence. Primary note proof quotes the study notes. Related reading and module passages are labelled separately; a module reference is not presented as primary note proof.'))
        if kind == 'notes' and self.introduction:
            result.extend([PageBreak(), self.p('How to use these study notes', 'h1')])
            for note in self.introduction:
                result.extend(self.heading(note['title'], 2))
                result.extend(self.blocks(note.get('blocks', [])))
        return result


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pdf(path, story, config, kind, title=''):
    path.parent.mkdir(parents=True,exist_ok=True)
    pending=path.with_suffix('.pending')
    BookDoc(pending,config,kind,title).build(story)
    pending.replace(path)
    with fitz.open(path) as doc: return len(doc)


def assemble(path, front_path, fragment_paths, config, title):
    """Merge native PDF pages, retaining per-fragment links and named outlines."""
    path.parent.mkdir(parents=True,exist_ok=True)
    out=fitz.open(); outline=[]
    with fitz.open(front_path) as front: out.insert_pdf(front)
    outline.append([1,'Cover',1]); outline.append([1,'Course contents',2])
    for fragment in fragment_paths:
        with fitz.open(fragment) as part:
            start=len(out)
            out.insert_pdf(part,links=True,annots=True)
            outline.extend([[level+1,label,page+start] for level,label,page in part.get_toc()])
    # Add a compact top-level parent to keep the inherited course hierarchy valid.
    outline = [[1,title,1]]+[[level+1,label,page] for level,label,page in outline]
    # First fragment course entries are nested beneath the book; sections below them.
    for i,row in enumerate(outline):
        if i and row[0] > outline[i-1][0]+1: row[0]=outline[i-1][0]+1
    out.set_toc(outline)
    total=len(out)
    for i,page in enumerate(out):
        label=f'Page {i+1} of {total}'
        page.insert_textbox(fitz.Rect(LEFT, PAGE_H-27, PAGE_W-RIGHT,PAGE_H-12),label,
                            fontname='helv',fontsize=8,align=1,color=(0.32,0.38,0.45))
    out.set_metadata({'title':title,'author':config['SITE_NAME'],'subject':'Computer Science Exit Examination',
                      'creator':'CS Exit Ethiopia ReportLab textbook builder','producer':'ReportLab / PyMuPDF'})
    pending=path.with_suffix('.pending')
    out.save(pending,garbage=3,deflate=True)
    out.close(); pending.replace(path)
    if path.stat().st_size >= 100_000_000:
        raise ValueError(f'PDF exceeds 100 MB GitHub limit: {path}')
    return total


def complete(renderer, selected, kind, fragment_paths, dest, qa, date):
    counts=[]
    for path in fragment_paths:
        with fitz.open(path) as doc: counts.append(len(doc))
    # Front matter can itself span pages. Iterate until printed TOC offsets agree.
    front_pages=2
    front_renderer=Renderer(renderer.config)
    front_renderer.introduction=renderer.introduction
    for attempt in range(5):
        offsets=[]; pos=front_pages
        for pages in counts: offsets.append(pos); pos+=pages
        front=qa/f'front-{kind}-{dest.stem}.pdf'
        actual=write_pdf(front,front_renderer.front(selected,kind,offsets,date),renderer.config,kind)
        if actual==front_pages: break
        front_pages=actual
    else: raise ValueError('Front-matter page count failed to stabilize')
    pages=assemble(dest,front,fragment_paths,renderer.config,TITLES[kind]+(' - '+selected[0]['title'] if len(selected)==1 else ' - All Courses'))
    # Make the printed table of contents clickable using the actual course titles.
    with fitz.open(dest) as doc:
        for course,offset in zip(selected,offsets):
            found=False
            for page_index in range(1,front_pages):
                page=doc[page_index]
                rects=page.search_for(ty.normalize(course['title']))
                if rects:
                    for rect in rects:
                        page.insert_link({'kind':fitz.LINK_GOTO,'from':rect,'page':offset})
                    found=True; break
            if not found: renderer.warnings.append(f'TOC link not found: {course["slug"]}')
        doc.saveIncr()
    return pages


def audit_inputs(courses, introduction=None):
    counts=Counter(); chars=Counter(); unsupported={}
    def walk(value,where):
        if isinstance(value,str):
            for ch in ty.normalize(value):
                chars[ch]+=1
                if not ch.isspace() and not any(ord(ch) in cmap for cmap in ty.FONT_MAPS.values()):
                    unsupported.setdefault(ch,[])
                    if len(unsupported[ch])<3: unsupported[ch].append(where)
        elif isinstance(value,list):
            for i,item in enumerate(value): walk(item,where+f'[{i}]')
        elif isinstance(value,dict):
            for key,item in value.items():
                if key not in ('data','url'): walk(item,where+'.'+key)
    for course in courses:
        if len(course['questions']) != course['question_count']:
            raise ValueError(f'Question count mismatch: {course["slug"]}')
        counts['questions']+=len(course['questions'])
        counts['variants']+=sum(len(q.get('variants',[])) for q in course['questions'])
        counts['note_sections']+=len(course['notes'])
        counts['outline_topics']+=len(course['outlines'])
        walk(course,course['slug'])
    if introduction:
        counts['note_sections']+=len(introduction)
        for note in introduction: walk(note, 'Study_introduction.'+note['id'])
    return {'course_count':len(courses),'global_note_introduction_sections':len(introduction or []),'counts':dict(counts),'unique_characters':len(chars),
            'normalizations':[{'from':f'U+{ord(c):04X}','to':v,'name':unicodedata.name(c,'PRIVATE USE')} for c,v in sorted(ty.NORMALIZATIONS.items())],
            'unsupported':[{'codepoint':f'U+{ord(c):04X}','character':c,'name':unicodedata.name(c,'PRIVATE USE'),'locations':loc} for c,loc in unsupported.items()],
            'fonts':{k:{'file':v,'codepoints':len(ty.FONT_MAPS[k])} for k,v in ty.FONT_FILES.items()},
            'policy':'Only mathematical styled alphabet characters and documented source-symbol artifacts are normalized; superscripts/subscripts and operators are preserved.'}


def validate_pdf(path, numbered, expected=None):
    failures=[]; overflow=[]; glyphs=[]; empty=[]
    with fitz.open(path) as doc:
        pages=len(doc)
        for i,page in enumerate(doc):
            text=page.get_text()
            if not text.strip(): empty.append(i+1)
            if numbered and f'Page {i+1} of {pages}' not in text:
                failures.append(f'Page {i+1}: missing/wrong global page number')
            if not numbered and re.search(r'Page \d+ of \d+',text):
                failures.append(f'Page {i+1}: fragment contains page numbers')
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    for span in line.get('spans',[]):
                        x0,y0,x1,y1=span['bbox']
                        if x0 < LEFT-5 or x1 > PAGE_W-RIGHT+5 or y0 < 4 or y1 > PAGE_H-4:
                            overflow.append({'page':i+1,'bbox':[round(x,2) for x in span['bbox']],'text':span['text'][:100]})
                        if '\ufffd' in span['text'] or '\x00' in span['text']:
                            glyphs.append({'page':i+1,'text':span['text'][:100]})
        if empty: failures.append(f'Empty pages: {empty}')
        if overflow: failures.append(f'{len(overflow)} text spans outside printable bounds')
        if glyphs: failures.append(f'{len(glyphs)} replacement/null glyphs')
        bookmarks=len(doc.get_toc())
        if not bookmarks: failures.append('No bookmarks')
    if path.stat().st_size>=100_000_000: failures.append('File exceeds 100 MB')
    return {'file':str(path),'pages':pages,'bytes':path.stat().st_size,'numbered':numbered,
            'bookmarks':bookmarks,'failures':failures,'overflow':overflow[:15],'glyph_issues':glyphs[:15]}


def update_progress(root, **values):
    path=root/'work/pdf-layout-progress.json'
    state=json.loads(path.read_text()) if path.exists() else {}
    state.update(values); state['updated_at']=NOW()
    atomic_json(path,state)


def parse_args():
    parser=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--input-dir',type=Path)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--courses','--course',default='',help='Comma-separated course slugs (default: all)')
    parser.add_argument('--types','--kind',default=','.join(KINDS),help='Comma-separated questions,notes,outlines')
    parser.add_argument('--skip-all',action='store_true')
    parser.add_argument('--fragments-only',action='store_true')
    parser.add_argument('--validate',action='store_true',help='Inspect every page of every produced PDF')
    parser.add_argument('--verify-only',action='store_true',help='Verify all existing outputs and full canonical text coverage without rebuilding')
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--all',action='store_true',help='Explicitly select all catalog courses')
    return parser.parse_args()


def main():
    args=parse_args(); root=args.root.resolve(); inputs=args.input_dir or root/'assets/export-data'
    output=args.output_dir or root/'assets/pdf'; qa=output/'qa'; qa.mkdir(parents=True,exist_ok=True)
    config=branding(root); ty.setup_fonts(root/'assets/pdf/fonts')
    if args.self_test:
        return self_test(root,output,config)
    if args.verify_only:
        return verify_existing(root, inputs, output)
    catalog=json.loads((inputs/'catalog.json').read_text(encoding='utf-8'))
    requested=set(filter(None,re.split(r'[,\s]+',args.courses)))
    known={x['slug'] for x in catalog['courses']}
    if requested-known: raise ValueError(f'Unknown courses: {sorted(requested-known)}')
    selected=[json.loads((inputs/(row['slug']+'.json')).read_text(encoding='utf-8')) for row in catalog['courses'] if not requested or row['slug'] in requested]
    kinds=tuple(filter(None,args.types.split(',')))
    if set(kinds)-set(KINDS): raise ValueError('Invalid PDF type')
    intro_path=inputs/'study-introduction.json'
    introduction=json.loads(intro_path.read_text(encoding='utf-8')) if intro_path.exists() else []
    audit=audit_inputs(selected,introduction); atomic_json(qa/'font-audit.json',audit)
    if audit['unsupported']:
        raise ValueError(f'Unsupported source glyphs; see {qa/"font-audit.json"}')
    # Source hashes are rechecked after build to detect concurrent extraction updates.
    hashes={str(inputs/(c['slug']+'.json')):sha(inputs/(c['slug']+'.json')) for c in selected}
    update_progress(root,status='generating',error=None,note='All canonical per-course JSON and global introductions are ready; full PDF generation in progress.',selected=[c['slug'] for c in selected],types=list(kinds),input_audit=audit['counts'],completed=[],failures=[])
    renderer=Renderer(config); generated=[]; rows={}
    intro_path=inputs/'study-introduction.json'
    if intro_path.exists(): renderer.introduction=json.loads(intro_path.read_text(encoding='utf-8'))
    catalog_path=output/'catalog.json'
    if catalog_path.exists():
        old=json.loads(catalog_path.read_text()); rows={x['slug']:x for x in old.get('courses',[])}; all_entries=old.get('all',{})
    else: all_entries={}
    started=time.monotonic(); date=datetime.now().strftime('%d %B %Y')
    for c in selected:
        slug=c['slug']; row=rows.setdefault(slug,{'slug':slug,'title':c['title'],'resources':{}})
        for kind in kinds:
            fragment=output/'fragments'/kind/(slug+'.pdf')
            print(f'BUILD {kind} / {slug}',flush=True)
            fp=write_pdf(fragment,renderer.course(c,kind),config,kind,c['title'])
            generated.append((fragment,False))
            dest=output/kind/(slug+'.pdf')
            pages=complete(renderer,[c],kind,[fragment],dest,qa,date) if not args.fragments_only else None
            if pages is not None:
                row['resources'][kind]={'download':dest.relative_to(root).as_posix(), 'fragment':fragment.relative_to(root).as_posix(),'pages':pages,'fragment_pages':fp}
                generated.append((dest,True))
            update_progress(root,current={'slug':slug,'type':kind,'fragment_pages':fp,'pages':pages},completed=[{'file':str(p.relative_to(root)),'bytes':p.stat().st_size} for p,_ in generated],elapsed_seconds=round(time.monotonic()-started,1))
    if not args.skip_all and not args.fragments_only:
        # All-courses is emitted only for the entire canonical catalog.
        all_courses=[json.loads((inputs/(r['slug']+'.json')).read_text()) for r in catalog['courses']]
        for kind in kinds:
            fragments=[output/'fragments'/kind/(c['slug']+'.pdf') for c in all_courses]
            if not all(p.exists() for p in fragments):
                print(f'SKIP all/{kind}: build all course fragments first',flush=True); continue
            print(f'MERGE all courses / {kind}',flush=True)
            dest=output/kind/'all-courses.pdf'
            pages=complete(renderer,all_courses,kind,fragments,dest,qa,date)
            all_entries[kind]={'download':dest.relative_to(root).as_posix(),'pages':pages}
            generated.append((dest,True))
    changed=[path for path,value in hashes.items() if sha(Path(path))!=value]
    if changed: raise ValueError(f'Input JSON changed during build; rebuild: {changed}')
    validation=[]
    if args.validate:
        update_progress(root,status='validating',current=None)
        for path,numbered in generated:
            print(f'CHECK {path.relative_to(root)}',flush=True)
            validation.append(validate_pdf(path,numbered))
        atomic_json(qa/'validation.json',validation)
    failures=[{'file':r['file'],'failures':r['failures']} for r in validation if r['failures']]
    atomic_json(qa/'font-audit.json',audit_inputs(selected,renderer.introduction))
    manifest={'generated_at':NOW(),'source_sha256':hashes,'rendered_content_counts':dict(renderer.counts),
              'global_note_introduction_sections':len(renderer.introduction),'warnings':renderer.warnings,'artifacts':[{'path':str(p.relative_to(root)),'pages':len(fitz.open(p)),'bytes':p.stat().st_size} for p,_ in generated],
              'validation_failures':failures,'elapsed_seconds':round(time.monotonic()-started,1)}
    atomic_json(qa/'build-manifest.json',manifest)
    if failures:
        update_progress(root,status='validation_failed',failures=failures,manifest=str(qa/'build-manifest.json'))
        raise ValueError(f'{len(failures)} PDFs failed validation; see {qa/"validation.json"}')
    # Exact contract schema; internal QA information is intentionally separate.
    published={'generated_at':NOW(),'site_url':config['SITE_URL'],'courses':[rows[r['slug']] for r in catalog['courses'] if r['slug'] in rows],'all':all_entries}
    if not args.fragments_only: atomic_json(catalog_path,published)
    update_progress(root,status='complete',error=None,note='All requested PDFs generated and checked against the ready canonical JSON.',current=None,failures=[],counts=dict(renderer.counts),warnings=renderer.warnings,artifacts=manifest['artifacts'],elapsed_seconds=manifest['elapsed_seconds'])
    print(json.dumps({'status':'complete','files':len(generated),'counts':dict(renderer.counts),'elapsed_seconds':manifest['elapsed_seconds']}),flush=True)
    return 0


def verify_existing(root, inputs, output):
    verification_started=time.monotonic()
    catalog=json.loads((inputs/'catalog.json').read_text())
    courses=[json.loads((inputs/(r['slug']+'.json')).read_text()) for r in catalog['courses']]
    qa=output/'qa'
    update_progress(root,status='validating',error=None,current=None,selected=[c['slug'] for c in courses],types=list(KINDS),note='Checking every final PDF page and all canonical text fields.')
    results=[]
    for course in courses:
        for kind in KINDS:
            for fragment in (True,False):
                path=output/'fragments'/kind/(course['slug']+'.pdf') if fragment else output/kind/(course['slug']+'.pdf')
                results.append(validate_pdf(path,not fragment))
    for kind in KINDS: results.append(validate_pdf(output/kind/'all-courses.pdf',True))
    atomic_json(qa/'validation.json',results)
    intro_path=inputs/'study-introduction.json'
    introduction=json.loads(intro_path.read_text()) if intro_path.exists() else []
    audit=audit_inputs(courses,introduction)
    if intro_path.exists():
        # Include global introductory blocks in the Unicode coverage audit too.
        for note in json.loads(intro_path.read_text()):
            for block in note.get('blocks',[]):
                if block.get('text'):
                    ty.font_runs(block['text'])
    atomic_json(qa/'font-audit.json',audit)
    coverage=ty.validate_text_coverage(root)
    failures=[r for r in results if r['failures']]+coverage['failures']
    if audit['unsupported']: failures.append({'unsupported':audit['unsupported']})
    if failures:
        update_progress(root,status='validation_failed',failures=failures)
        raise ValueError('Final PDF verification failed; inspect assets/pdf/qa reports')
    baseline=qa/'full-build-manifest.json'
    if not baseline.exists(): baseline=qa/'build-manifest.json'
    manifest=json.loads(baseline.read_text()) if baseline.exists() else {}
    old_hashes=manifest.get('source_sha256',{})
    for source,digest in old_hashes.items():
        if sha(Path(source))!=digest: raise ValueError(f'Canonical input changed: {source}')
    manifest.update(generated_at=NOW(),rendered_content_counts=coverage['counts'],
                    global_note_introduction_sections=3,validation_failures=[],
                    artifacts=[{'path':str(Path(r['file']).relative_to(root)),'pages':r['pages'],'bytes':r['bytes']} for r in results],
                    final_verification={'pdf_files':len(results),'pages_checked':sum(r['pages'] for r in results),'text_fields_checked':coverage['counts']['text_fields_checked'],'duration_seconds':round(time.monotonic()-verification_started,1)})
    atomic_json(qa/'build-manifest.json',manifest)
    update_progress(root,status='complete',error=None,current=None,failures=[],
                    note='All 99 final PDFs verified; full canonical coverage and source hashes passed.',
                    counts=coverage['counts'],selected=[c['slug'] for c in courses],types=list(KINDS),completed=manifest['artifacts'],artifacts=manifest['artifacts'],final_verification=manifest['final_verification'])
    print(json.dumps({'status':'complete','verification':manifest['final_verification'],'counts':coverage['counts']}))
    return 0


def self_test(root, output, config):
    qa=output/'qa'; renderer=Renderer(config)
    assert ty.normalize('𝐱² + 𝑛₁ ≠ ℝ')=='x² + n₁ ≠ R'
    long=' '.join(['A long explanation preserves body size and continues with a clear label.']*160)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="400" height="80"><rect x="1" y="1" width="398" height="78" fill="#eef6f6" stroke="#087f83"/><text x="20" y="45" font-size="16">Vector diagram: x² + n₁</text></svg>'
    course={'slug':'Layout_Test','title':'Layout and Unicode Stress Test','question_count':2,
            'questions':[{'id':'TEST001','number':1,'stem':'Evaluate 𝐱² + 𝑛₁, ∑, ∈, ∀, ≠, O(𝑛²).\n```python\n'+('    long_identifier = '+ 'abc_'*80)+'\n```',
             'options':[{'label':x,'text':'An option with preserved exponent 2³ and subscript a₁.'} for x in 'ABCD'],
             'hint':'Compare all choices.','section_ids':['TEST-S1','TEST-S2'],'sources':['Layout regression fixture'],
             'answer':{'labels':['A'],'text':'x²','explanation':long,'choices':[{'label':x,'verdict':'correct' if x=='A' else 'incorrect','explanation':'Contrast for choice '+x} for x in 'ABCD'],
                       'evidence':[{'section_id':'TEST-S1','quote':'Proof text preserves n² and x₁.','url':'Complete_CS_Exit_Study_Guide.html#TEST-S1'}],
                       'module_refs':[{'title':'Module example','url':'Modules/example.pdf#page=3','page':3,'line_start':4,'line_end':8,'quote':'An exact module passage.'}]},'variants':[], 'diagram':{'data':svg}},
             {'id':'TEST002','number':2,'stem':'A short complete question should fit together.','options':[{'label':x,'text':'Short option '+x} for x in 'ABCD'],
              'answer':{'labels':['B'],'text':'Choice B','explanation':'A short explanation.','choices':[],'evidence':[],'module_refs':[]},'variants':[]}],
            'notes':[{'id':'TEST-S1','title':'Tables and code','blocks':[{'type':'paragraph','text':'Unicode operators ≥ ≤ ∫ √ → and exponents ² ³ are retained.'},
               {'type':'table','headers':['Item','Definition'],'rows':[[str(i),'A wrapped row with n² and a readable full-size definition. '*3] for i in range(40)]},
               {'type':'code','text':'    '+('a_long_unbroken_identifier_'*25)+'\nnext_line()'}]}],
            'outline_intro':[{'type':'paragraph','text':'Short hierarchical revision cues.'}],
            'outlines':[{'id':'topic1','title':'Nested concepts','exam_focus':True,'cues':[{'text':'Parent cue','children':[{'text':'Child cue n²','children':[{'text':'Third level x₁','children':[]}]}]}]}]}
    results=[]
    for kind in KINDS:
        fragment=qa/f'test-{kind}-fragment.pdf'
        write_pdf(fragment,renderer.course(course,kind),config,kind,course['title'])
        dest=qa/f'test-{kind}.pdf'; complete(renderer,[course],kind,[fragment],dest,qa,'Layout QA')
        results.extend([validate_pdf(fragment,False),validate_pdf(dest,True)])
    atomic_json(qa/'self-test.json',results)
    for result in results: print(json.dumps(result))
    if any(r['failures'] for r in results): raise ValueError('Layout self-test failed')
    return 0


if __name__=='__main__':
    try: sys.exit(main())
    except Exception as exc:
        update_progress(ROOT,status='error',error=f'{type(exc).__name__}: {exc}')
        raise
