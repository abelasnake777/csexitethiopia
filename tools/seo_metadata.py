"""Build-time SEO and search helpers; no hosting runtime or orchestration.

Integration API (all generators return data/text and never write files):
  generate_head(path, siteconfig, courses, metadata=None) -> str
  page_metadata(path, siteconfig, courses, metadata=None) -> dict
  public_page_paths(courses) -> list[str] (55 current pages)
  generate_sitemap(public_paths, siteconfig, courses=None) -> XML str
  generate_robots(public_paths, siteconfig, courses=None) -> str
  generate_search_index(courses, export_data) -> {records: [...], courses: [...]}
  render_public_faq('home'|'downloads') -> semantic HTML str

Main owns site.config.js parsing, file writes, head replacement and build order.
siteconfig accepts SITE_URL, SITE_NAME, EMAIL, LANGUAGE (lowercase keys also work).
SITE_URL is required; this module never substitutes a production hostname.
courses may be catalog['courses'] or that list, with {slug,title} or {slug,course}.
metadata supports title (55..60), description (150..160), h1, title_alias,
keywords, and faq=[{question,answer}]. FAQ schema is emitted ONLY when
metadata['faq_visible'] is True AND explicit nonempty faq content is provided.
For homepage/downloads: render_public_faq(kind), then pass the matching
PUBLIC_FAQ[kind] with faq_visible=True. Never mark an unrendered FAQ visible.
Use page_metadata()['h1'] for course pages to retain the complete catalog name.
The head output is only SEO tags; main retains charset, viewport, assets, shell.

export_data is a mapping {slug: clean_export_dict} or iterable of exports.
Index URLs preserve existing .html pages and section IDs; questions use their
public Questions/Interactive_Study_Guides/<slug>.html#question-<number> anchor,
unless a question has an explicit public 'url'. Note/outline section IDs are public anchors. The small
optional courses array preserves catalog spelling for standalone search UI.
Only public export text is indexed, never source manifests/editor history.

Progress: all six owned files ready for main integration. Verified 55 unique
titles/descriptions, length bounds, full course names, FAQ opt-in, JSON escaping,
config propagation and sitemap exclusion. Headless Chrome checks passed for
search, ranking, filters, pagination, clear, empty/error/retry, malformed indexes,
unsafe result URLs and narrow-screen layout. PNG verified at 1200 x 630.
No source, configuration, index file or orchestration edits.
Google references (checked 2026-11-18):
https://developers.google.com/search/docs/appearance/title-link
https://developers.google.com/search/docs/appearance/snippet
https://developers.google.com/search/updates (FAQ rich results retired May 2026)
https://developers.google.com/search/blog/2024/10/sitelinks-search-box
55..60 / 150..160 are project editorial requirements, not Google guarantees.
SearchAction and FAQPage remain semantic markup, with no rich-result promise.
"""
from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import quote, urlsplit, unquote
from xml.etree.ElementTree import Element, SubElement, tostring

TITLE_ALIASES = {
    'Fundamental_of_Database_Systems': 'Database Fundamentals',
    'Computer_Organization_and_Architecture': 'Computer Organization & Architecture',
    'Data_Communication_and_Computer_Networking': 'Data Communication & Networking',
    'Design_and_Analysis_of_Algorithms': 'Algorithm Design & Analysis',
    'Introduction_to_Artificial_Intelligence': 'Introduction to AI',
    'Network_and_System_Administration': 'Network & System Administration',
}
KINDS = {
    'module': ('Modules', 'Modules', 'course module'),
    'outlines': ('Outlines', 'Outlines', 'revision outline'),
    'questions': ('Questions/Interactive_Study_Guides', 'Questions', 'practice questions'),
}
PUBLIC_FAQ = {
    'home': (
        {'question': 'What can I study on CS Exit Ethiopia?',
         'answer': 'Study notes, practice questions, revision outlines and course modules cover 16 Computer Science courses for Ethiopian CS Exit Exam preparation.'},
        {'question': 'Do I need an account to use the study resources?',
         'answer': 'The public study resources are free to read without an account.'},
        {'question': 'How can I find a topic or question?',
         'answer': 'Use the Search page to enter a topic, keyword or question number, then narrow the results by course or resource type.'},
    ),
    'downloads': (
        {'question': 'Which study resources can I download?',
         'answer': 'The Downloads page provides PDFs of study notes, practice questions and revision outlines. Choose a single course, all courses or a custom selection.'},
        {'question': 'Can I combine selected courses into one PDF?',
         'answer': 'Choose a resource type and the courses you need on the Downloads page, then generate the combined PDF.'},
        {'question': 'Can I study a downloaded PDF offline?',
         'answer': 'After saving a PDF to your device, open it in a PDF reader to study offline.'},
    ),
}
HOMEPAGE_FAQ = PUBLIC_FAQ['home']
DOWNLOADS_FAQ = PUBLIC_FAQ['downloads']


def _config(config, key, default=None):
    return config.get(key, config.get(key.lower(), default))


def _base(config):
    value = str(_config(config, 'SITE_URL', '')).rstrip('/')
    parts = urlsplit(value)
    if parts.scheme != 'https' or not parts.netloc or parts.query or parts.fragment or parts.username or parts.password:
        raise ValueError('SITE_URL must be an absolute HTTPS site URL, without query or fragment')
    return value


def _courses(courses):
    if isinstance(courses, Mapping):
        courses = courses['courses']
    rows = []
    for course in courses:
        slug, title = course['slug'], course.get('title') or course.get('course')
        if not re.fullmatch(r'[A-Za-z0-9_-]+', slug) or not title:
            raise ValueError('Every course needs a safe slug and a full catalog title')
        rows.append({'slug': slug, 'title': title})
    if len({r['slug'] for r in rows}) != len(rows) or len({r['title'] for r in rows}) != len(rows):
        raise ValueError('Course slugs and titles must be unique')
    return rows


def _default_courses():
    return json.loads((Path(__file__).resolve().parents[1] / 'Modules/catalog.json').read_text(encoding='utf-8'))


def _path(path):
    value = str(path).replace('\\', '/')
    parts = urlsplit(value)
    if parts.scheme or parts.netloc:
        raise ValueError('Pass a site-relative public page path')
    value = unquote(parts.path).lstrip('/')
    if any(p in ('.', '..') for p in value.split('/')):
        raise ValueError('Relative traversal is not a public path')
    return value or 'index.html'


def _url(path, config):
    value = _path(path)
    return _base(config) + '/' + ('' if value == 'index.html' else quote(value, safe='/-._~'))


def public_page_paths(courses):
    """Explicit page allowlist: home, master, three selectors, 48 courses, search/downloads."""
    rows = _courses(courses)
    paths = ['index.html', 'Complete_CS_Exit_Study_Guide.html', 'search.html', 'downloads.html']
    for folder, _, _ in KINDS.values():
        paths.append(folder + '/index.html')
        paths.extend(folder + '/' + row['slug'] + '.html' for row in rows)
    return sorted(paths)


def _identify(path, rows):
    if path == 'index.html':
        return 'home', None
    if path == 'Complete_CS_Exit_Study_Guide.html':
        return 'notes', None
    if path in ('downloads.html', 'search.html'):
        return path[:-5], None
    for kind, (folder, _, _) in KINDS.items():
        if path == folder + '/index.html':
            return kind, None
        for row in rows:
            if path == folder + '/' + row['slug'] + '.html':
                return kind, row
    raise ValueError('Unknown public page: ' + path)


def _bounded(candidates, minimum, maximum, label):
    for candidate in candidates:
        if minimum <= len(candidate) <= maximum:
            return candidate
    raise ValueError(f'No {label} fits {minimum}..{maximum} characters; supply a metadata override')


def _title(kind, course, alias=None):
    general = {
        'home': 'Ethiopian CS Exit Exam | Free Resources for All 16 Courses',
        'notes': 'Ethiopian CS Exit Exam Study Guide | Notes for 16 Courses',
        'module': 'Ethiopian CS Exit Exam Modules | Read All 16 Course Guides',
        'outlines': 'Ethiopian CS Exit Exam Revision Outlines | All 16 Courses',
        'questions': 'Ethiopian CS Exit Exam Practice Questions | All 16 Courses',
        'downloads': 'Ethiopian CS Exit Exam PDF Downloads | Choose Your Courses',
        'search': 'Search Ethiopian CS Exit Exam Resources | CS Exit Ethiopia',
    }
    if course is None:
        return _bounded([general[kind]], 55, 60, 'title')
    names = list(dict.fromkeys([alias or course['title'], TITLE_ALIASES.get(course['slug'], course['title'])]))
    resource = KINDS[kind][1]
    suffixes = ['Ethiopian CS Exit Exam', 'Ethiopia CS Exit Exam', 'CS Exit Ethiopia',
                'Ethiopian CS Exit', 'CS Exit Exam', 'CS Exit',
                'Ethiopian CS Exit Exam Study Resources', 'Ethiopian CS Exit Exam Preparation',
                'Ethiopian CS Exit Exam Study Guide', 'Ethiopia CS Exit Exam Preparation',
                'Ethiopian CS Exit Exam Prep', 'Ethiopia CS Exit Exam Guide',
                'Ethiopian CS Exit Exam Study', 'Ethiopian CS Exit Exam Review']
    return _bounded([f'{name} {resource} | {suffix}' for name in names for suffix in suffixes], 55, 60, 'title')


def _description(kind, course):
    if course:
        resource = KINDS[kind][2]
        starts = [f'Prepare for the Ethiopian CS Exit Exam with {course["title"]} {resource}.',
                  f'Read {course["title"]} {resource} for the Ethiopian CS Exit Exam.']
        ends = [' Build understanding and review key concepts at your own pace.',
                ' Review key concepts and plan your next study session.',
                ' Study key concepts and prepare at your own pace.',
                ' Review key concepts with free study resources.',
                ' Study online at your own pace, with no account needed.',
                ' Free resources help you review concepts at your own pace.',
                ' Build your understanding with free course resources.',
                ' Free online resources for focused course revision.',
                ' Review the course and study online for free.',
                ' Free online resources, with no account needed.',
                ' Build your understanding and review course concepts online at your own pace.',
                ' Study course concepts online, review what you have learned and plan your revision.',
                ' Use free course resources to build your understanding and plan your next study session.',
                ' Use free study resources to review course concepts and prepare at your own pace.']
        return _bounded([s + e for s in starts for e in ends], 150, 160, 'description')
    values = {
        'home': 'Prepare for the Ethiopian CS Exit Exam with free study notes, practice questions, revision outlines and modules for all 16 courses. No account is required.',
        'notes': 'Study for the Ethiopian CS Exit Exam with a complete guide covering all 16 courses. Read concepts, examples and explanations, then revisit topics at your pace.',
        'module': 'Read course modules for Ethiopian CS Exit Exam preparation across all 16 courses. Choose a subject, explore learning material and review concepts at your pace.',
        'outlines': 'Revise for the Ethiopian CS Exit Exam with outlines for all 16 courses. Choose a course, review topic cues and connect your revision to the full study notes.',
        'questions': 'Practice for the Ethiopian CS Exit Exam with questions across all 16 courses. Choose a subject, try questions and use explanations to review your understanding.',
        'downloads': 'Download Ethiopian CS Exit Exam study notes, questions and revision outlines as PDFs. Choose one course, all 16 courses or a custom set for offline study.',
        'search': 'Search Ethiopian CS Exit Exam notes, questions, outlines and modules. Find a topic across all 16 courses and filter results by course or resource type online.',
    }
    return _bounded([values[kind]], 150, 160, 'description')


def page_metadata(path, siteconfig, courses, metadata=None):
    """Return title, description, keywords, canonical, image, h1, kind and course."""
    path = _path(path)
    rows, override = _courses(courses), dict(metadata or {})
    kind, course = _identify(path, rows)
    title = override.get('title') or _title(kind, course, override.get('title_alias'))
    description = override.get('description') or _description(kind, course)
    _bounded([title], 55, 60, 'title')
    _bounded([description], 150, 160, 'description')
    names = [course['title']] if course else [row['title'] for row in rows]
    keywords = ['Ethiopian CS Exit Exam', 'Ethiopian Computer Science Exit Exam',
                {'home': 'study resources', 'notes': 'study notes', 'module': 'course modules',
                 'questions': 'practice questions', 'outlines': 'revision outlines',
                 'downloads': 'PDF downloads', 'search': 'site search'}[kind], *names]
    extra = override.get('keywords', [])
    keywords.extend([extra] if isinstance(extra, str) else extra)
    h1 = course['title'] if course else {
        'home': 'Ethiopian CS Exit Exam Study Resources', 'notes': 'Complete CS Exit Exam Study Guide',
        'module': 'Course Modules', 'outlines': 'Revision Outlines', 'questions': 'Practice Questions',
        'downloads': 'Download Study Resources', 'search': 'Search Study Resources'}[kind]
    return {'title': title, 'description': description, 'keywords': ', '.join(dict.fromkeys(keywords)),
            'canonical': _url(path, siteconfig), 'image': _base(siteconfig) + '/assets/social-preview.png',
            'h1': override.get('h1', h1), 'kind': kind, 'course': course}


def generate_head(path, siteconfig, courses, metadata=None):
    """Return escaped SEO markup, including a safe Schema.org JSON-LD graph."""
    data = page_metadata(path, siteconfig, courses, metadata)
    base, canonical = _base(siteconfig), data['canonical']
    name = _config(siteconfig, 'SITE_NAME', 'CS Exit Ethiopia')
    language = _config(siteconfig, 'LANGUAGE', 'en')
    organization = {'@type': 'EducationalOrganization', '@id': base + '/#organization',
                    'name': name, 'url': base + '/', 'logo': base + '/assets/favicon.svg',
                    'description': 'Independent Computer Science study resources for Ethiopian CS Exit Exam preparation.'}
    if _config(siteconfig, 'EMAIL'):
        organization['email'] = _config(siteconfig, 'EMAIL')
    website = {'@type': 'WebSite', '@id': base + '/#website', 'url': base + '/', 'name': name,
               'publisher': {'@id': organization['@id']}, 'inLanguage': language,
               'potentialAction': {'@type': 'SearchAction',
                                   'target': {'@type': 'EntryPoint', 'urlTemplate': base + '/search.html?q={search_term_string}'},
                                   'query-input': 'required name=search_term_string'}}
    page = {'@type': 'WebPage', '@id': canonical + '#webpage', 'url': canonical, 'name': data['h1'],
            'description': data['description'], 'isPartOf': {'@id': website['@id']},
            'publisher': {'@id': organization['@id']}, 'inLanguage': language,
            'primaryImageOfPage': {'@type': 'ImageObject', 'url': data['image'], 'width': 1200, 'height': 630}}
    graph = [organization, website, page]
    if data['course']:
        course = data['course']
        course_id = _url('Modules/' + course['slug'] + '.html', siteconfig) + '#course'
        graph.append({'@type': 'Course', '@id': course_id, 'name': course['title'],
                      'description': f'{course["title"]} study resources for Ethiopian CS Exit Exam preparation.',
                      'provider': {'@id': organization['@id']}, 'inLanguage': language})
        resource_id = canonical + '#resource'
        graph.append({'@type': 'LearningResource', '@id': resource_id, 'url': canonical,
                      'name': course['title'] + ' — ' + KINDS[data['kind']][2],
                      'description': data['description'], 'learningResourceType': KINDS[data['kind']][2],
                      'about': {'@id': course_id}, 'isPartOf': {'@id': course_id},
                      'inLanguage': language, 'isAccessibleForFree': True})
        page['mainEntity'] = {'@id': resource_id}
    override = metadata or {}
    if override.get('faq_visible') is True and override.get('faq'):
        questions = []
        for item in override['faq']:
            if not item.get('question', '').strip() or not item.get('answer', '').strip():
                raise ValueError('Visible FAQ requires a nonempty question and answer')
            questions.append({'@type': 'Question', 'name': item['question'],
                              'acceptedAnswer': {'@type': 'Answer', 'text': item['answer']}})
        graph.append({'@type': 'FAQPage', '@id': canonical + '#faq', 'url': canonical + '#faq',
                      'isPartOf': {'@id': page['@id']}, 'mainEntity': questions})
    esc = lambda v: html.escape(str(v), quote=True)
    lines = [f'<title>{esc(data["title"])}</title>',
             f'<meta name="description" content="{esc(data["description"])}">',
             f'<meta name="keywords" content="{esc(data["keywords"])}">',
             f'<link rel="canonical" href="{esc(canonical)}">',
             '<meta name="robots" content="index,follow,max-image-preview:large">']
    for key, value in {'og:type': 'website', 'og:site_name': name, 'og:title': data['title'],
                       'og:description': data['description'], 'og:url': canonical,
                       'og:locale': 'en_ET' if language == 'en' else language.replace('-', '_'),
                       'og:image': data['image'], 'og:image:secure_url': data['image'],
                       'og:image:type': 'image/png', 'og:image:width': '1200', 'og:image:height': '630',
                       'og:image:alt': 'CS Exit Ethiopia — free study resources for all 16 courses'}.items():
        lines.append(f'<meta property="{key}" content="{esc(value)}">')
    for key, value in {'twitter:card': 'summary_large_image', 'twitter:title': data['title'],
                       'twitter:description': data['description'], 'twitter:url': canonical,
                       'twitter:image': data['image'],
                       'twitter:image:alt': 'CS Exit Ethiopia — free study resources for all 16 courses'}.items():
        lines.append(f'<meta name="{key}" content="{esc(value)}">')
    payload = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, separators=(',', ':'))
    payload = payload.replace('&', '\\u0026').replace('<', '\\u003c').replace('>', '\\u003e').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')
    lines.append('<script type="application/ld+json">' + payload + '</script>')
    return '\n'.join(lines)


def render_public_faq(kind):
    """Render the same plain text used by PUBLIC_FAQ; main inserts it visibly."""
    items = PUBLIC_FAQ[kind]
    parts = ['<section id="faq" class="hub-faq" aria-labelledby="faq-heading"><h2 id="faq-heading">Frequently asked questions</h2>']
    for item in items:
        parts.append('<details><summary>' + html.escape(item['question']) + '</summary><p>' + html.escape(item['answer']) + '</p></details>')
    return '\n'.join(parts + ['</section>'])


def _allowed_paths(public_paths, courses):
    allowed = set(public_page_paths(courses if courses is not None else _default_courses()))
    result = set()
    for path in public_paths:
        try:
            path = _path(path)
        except ValueError:
            continue
        if path in allowed:
            result.add(path)
    return sorted(result)


def generate_sitemap(public_paths, siteconfig, courses=None):
    """Include only supplied allowlisted public pages, never guessed lastmod dates."""
    root = Element('urlset', {'xmlns': 'http://www.sitemaps.org/schemas/sitemap/0.9'})
    for path in _allowed_paths(public_paths, courses):
        SubElement(SubElement(root, 'url'), 'loc').text = _url(path, siteconfig)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + tostring(root, encoding='unicode') + '\n'


def generate_robots(public_paths, siteconfig, courses=None):
    """Return crawler guidance; publishing must also exclude private build artifacts.

    public_paths uses the same explicit allowlist as sitemap. A sitemap reference is
    included only when at least one public page is present. robots is not access control.
    """
    paths = _allowed_paths(public_paths, courses)
    lines = ['User-agent: *', 'Allow: /', 'Disallow: /tools/', 'Disallow: /tests/',
             'Disallow: /.git/', 'Disallow: /.platform_upgrade_work/',
             'Disallow: /maintenance/', 'Disallow: /work/',
             'Disallow: /assets/export-data/', 'Disallow: /assets/pdf/fragments/',
             'Disallow: /Modules/catalog.json', 'Disallow: /*_AUDIT.json$',
             'Disallow: /*_REVIEW.json$', 'Disallow: /SOURCE_MANIFEST.json',
             'Disallow: /VERIFICATION.json', 'Disallow: /PUBLIC_READER_COPY.json',
             'Disallow: /STUDY_NOTE_SUPPORT.json', 'Disallow: /ANSWER_REVIEW_SUMMARY.html']
    if paths:
        lines.extend(['', 'Sitemap: ' + _base(siteconfig) + '/sitemap.xml'])
    return '\n'.join(lines) + '\n'


def _block_text(block):
    """Extract only explicitly student-facing clean export fields (never SVG/image data)."""
    if isinstance(block, str):
        return block
    if not isinstance(block, Mapping):
        return ''
    parts = [str(block.get(key, '')) for key in ('title', 'text') if block.get(key)]
    for key in ('blocks', 'items', 'children'):
        parts.extend(_block_text(child) for child in block.get(key, []))
    parts.extend(str(v) for v in block.get('headers', []))
    parts.extend(str(v) for row in block.get('rows', []) for v in row)
    return ' '.join(parts)


def _search_url(value):
    parts = urlsplit(str(value))
    path = _path(parts.path)
    if parts.scheme or parts.netloc or not path.endswith('.html'):
        raise ValueError('Search results must point to internal HTML pages')
    return quote(path, safe='/-._~') + ('?' + parts.query if parts.query else '') + ('#' + parts.fragment if parts.fragment else '')


def generate_search_index(courses, export_data):
    """Create {records:[{title,text,url,course,type}],courses:[{slug,title}]}.

    Types are notes/questions/outlines/module. Uses only exported public text,
    preserves Unicode/math/code, excludes variants/source/evidence internals.
    Question IDs and section IDs are searchable; question records also retain
    section_ids for main's related-question readers.
    Caller writes UTF-8 JSON to assets/search-index.json after clean extraction.
    """
    rows = _courses(courses)
    exports = export_data if isinstance(export_data, Mapping) else {x['slug']: x for x in export_data}
    records = []
    def add(title, text, url, course, kind):
        records.append({'title': title, 'text': re.sub(r'\s+', ' ', text).strip(),
                        'url': _search_url(url), 'course': course['slug'], 'type': kind})
    for course in rows:
        slug, title = course['slug'], course['title']
        if slug not in exports:
            raise ValueError('Missing clean export for ' + slug)
        data = exports[slug]
        add(title + ' — Course module', title, 'Modules/' + slug + '.html', course, 'module')
        add(title + ' — Study notes', title + ' ' + ' '.join(_block_text(b) for b in data.get('note_intro', [])),
            'Complete_CS_Exit_Study_Guide.html#course-' + slug, course, 'notes')
        add(title + ' — Practice questions', title, 'Questions/Interactive_Study_Guides/' + slug + '.html', course, 'questions')
        add(title + ' — Revision outline', title + ' ' + ' '.join(_block_text(b) for b in data.get('outline_intro', [])),
            'Outlines/' + slug + '.html', course, 'outlines')
        for note in data.get('notes', []):
            add(title + ' — ' + note['title'], ' '.join(_block_text(b) for b in note.get('blocks', [])),
                'Complete_CS_Exit_Study_Guide.html#' + quote(str(note['id']), safe=''), course, 'notes')
        for outline in data.get('outlines', []):
            add(title + ' — ' + outline['title'], ' '.join(_block_text(b) for b in outline.get('cues', [])),
                'Outlines/' + slug + '.html#' + quote(str(outline['id']), safe=''), course, 'outlines')
        for question in data.get('questions', []):
            answer = question.get('answer') or {}
            text = ' '.join([str(question['id']), 'Question ' + str(question['number']),
                             *[str(sid) for sid in question.get('section_ids', [])],
                             question.get('stem', ''), question.get('hint', ''),
                             *[str(o.get('label', '')) + ' ' + str(o.get('text', '')) for o in question.get('options', [])],
                             str(answer.get('text', '')), str(answer.get('explanation', '')),
                             *[str(choice.get('label', '')) + ' ' + str(choice.get('verdict', '')) + ' ' + str(choice.get('explanation', ''))
                               for choice in answer.get('choices', [])]])
            url = question.get('url') or ('Questions/Interactive_Study_Guides/' + slug + '.html#question-' + quote(str(question['number']), safe=''))
            add(title + ' — Question ' + str(question['number']) + ' · ' + str(question['id']), text, url, course, 'questions')
            records[-1]['section_ids'] = list(question.get('section_ids', []))
    return {'records': records, 'courses': rows}
