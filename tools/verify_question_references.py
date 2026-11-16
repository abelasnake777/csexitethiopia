#!/usr/bin/env python3
"""Verify preservation, reading-map targets, and exhaustive rendered hint/answer links.

Usage:
  python3 tools/verify_question_references.py --base-url http://127.0.0.1:8457
  python3 tools/verify_question_references.py --static-only

The default command runs tests/question_references.cjs and writes
QUESTION_REFERENCE_AUDIT.json plus .qa/ref-dom-evidence.json. Static-only does
not replace a completed DOM audit. No source, master, index, or manifest is written.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
START = '/* STUDY-NOTE-ANSWER-REFERENCES:START */'
END = '/* STUDY-NOTE-ANSWER-REFERENCES:END */'
NAV_START = b'<!-- RESOURCE-HUB-INTEGRATION:START -->'
NAV_END = b'<!-- RESOURCE-HUB-INTEGRATION:END -->'
PAYLOAD = re.compile(rb'<script id="guide-data" type="application/json">(.*?)</script>', re.S)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class MasterSections(HTMLParser):
    def __init__(self):
        super().__init__()
        self.articles = []
        self.ids = {}

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'article':
            self.articles.append(attrs.get('id'))
        if 'id' in attrs:
            self.ids.setdefault(attrs['id'], []).append({
                'tag': tag.upper(),
                'course_ancestor': next((x for x in reversed(self.articles) if x and x.startswith('course-')), None),
            })

    def handle_endtag(self, tag):
        if tag == 'article' and self.articles:
            self.articles.pop()


def inventory(base):
    files = {}
    for folder, dirs, names in os.walk(base):
        dirs[:] = sorted(n for n in dirs if not n.startswith('.') and n not in ('node_modules', '__pycache__'))
        for name in sorted(names):
            p = Path(folder) / name
            if p.is_file():
                files[str(p.relative_to(base))] = sha(p.read_bytes())
    return files


def static_checks():
    baseline_path = ROOT / '.qa/ref-baseline.json'
    baseline = json.loads(baseline_path.read_bytes())
    source = Path(baseline['source_root'])
    reading_path = Path(baseline['reading_map_path'])
    reading_bytes = reading_path.read_bytes()
    require(sha(reading_bytes) == baseline['reading_map_sha256'], 'Authoritative reading map changed')
    rows = json.loads(reading_bytes)
    require(len(rows) == 3485, 'Expected 3485 reading-map rows')
    require(len({r['id'] for r in rows}) == 3485, 'Duplicate reading-map stable ID')
    slugs = sorted({r['slug'] for r in rows})
    require(len(slugs) == 16, 'Expected 16 courses')
    require(set(slugs) == set(baseline['courses']), 'Course inventory changed')
    by_id = {r['id']: r for r in rows}
    master_path = ROOT / 'Complete_CS_Exit_Study_Guide.html'
    master_bytes = master_path.read_bytes()
    parser = MasterSections()
    parser.feed(master_bytes.decode('utf-8'))
    block = baseline['insertion']['block'].encode('utf-8')
    require(block.startswith(START.encode()) and block.endswith(END.encode()), 'Incorrect baseline markers')
    require(sha(block) == baseline['insertion']['sha256'], 'Insertion baseline hash mismatch')
    manifest = json.loads((ROOT / 'SOURCE_MANIFEST.json').read_bytes())
    manifest_files = {f['copied_path']: f for f in manifest['files']}
    courses, questions, seen = [], [], set()
    for slug in slugs:
        before = baseline['courses'][slug]
        raw = (ROOT / before['path']).read_bytes()
        require(raw.count(START.encode()) == raw.count(END.encode()) == raw.count(block) == 1, slug + ': insertion markers/block changed')
        restored = raw.replace(block, b'', 1)
        # Navigation may include the authorized Modules link; original educational bytes are checked below.
        matches = PAYLOAD.findall(raw)
        require(len(matches) == 1 and sha(matches[0]) == before['payload_sha256'], slug + ': embedded JSON changed')
        navs = re.findall(re.escape(NAV_START) + rb'.*?' + re.escape(NAV_END), raw, re.S)
        require(len(navs) == 1 and navs[0] == manifest_files[before['path']]['integration_block'].encode(), slug + ': navigation block differs from approved current manifest')
        require(restored.replace(navs[0], b'', 1) == (source / before['path']).read_bytes(), slug + ': bytes outside both insertions differ from original source')
        model = json.loads(matches[0])
        expected = [r for r in rows if r['slug'] == slug]
        require(model['course'] == expected[0]['course'], slug + ': course name mismatch')
        require([q['question']['id'] for q in model['questions']] == [r['id'] for r in expected], slug + ': stable IDs/order mismatch')
        for item in model['questions']:
            q = item['question']
            qid = q['id']
            require(qid not in seen, 'Repeated stable ID: ' + qid)
            seen.add(qid)
            row = by_id[qid]
            require(q['course'] == row['course'] and q['question'] == row['number'], qid + ': course/number mismatch')
            ids = item['guide']['section_ids']
            require(ids and ids == row['section_ids'], qid + ': section IDs mismatch')
            require(len(ids) == len(set(ids)), qid + ': duplicate reference')
            for sid in ids:
                targets = parser.ids.get(sid, [])
                require(len(targets) == 1, qid + ': missing/duplicate master target ' + sid)
                require(targets[0]['tag'] == 'SECTION' and targets[0]['course_ancestor'] == 'course-' + slug, qid + ': incorrect master section/course ' + sid)
                require(bool(model['section_titles'].get(sid)), qid + ': missing link title ' + sid)
            questions.append({'id': qid, 'slug': slug, 'number': row['number'], 'section_ids': ids})
        courses.append({**before, 'slug': slug, 'after_sha256': sha(raw), 'after_bytes': len(raw),
                        'questions': len(expected), 'json_unchanged': True, 'navigation_updated_only_with_modules_link': True,
                        'exact_previous_bytes_after_removing_answer_block': sha(restored) == before['before_sha256'],
                        'exact_source_bytes_after_removing_answer_and_navigation_blocks': True})
    require(seen == set(by_id), 'Missing/extra stable IDs')
    source_changed = [rel for rel, digest in baseline['source_files'].items() if not (source / rel).is_file() or sha((source / rel).read_bytes()) != digest]
    require(not source_changed, 'Protected source changed: ' + repr(source_changed))
    allowed = {v['path'] for v in baseline['courses'].values()} | {'QUESTION_REFERENCE_AUDIT.json', 'tools/verify_question_references.py', 'tests/question_references.cjs'}
    website_now = inventory(ROOT)
    website_changed = [rel for rel, digest in baseline['website_files'].items() if rel not in allowed and website_now.get(rel) != digest]
    website_added = sorted(set(website_now) - set(baseline['website_files']) - allowed)
    # Other website workers may add/update their own files while this scoped audit runs.
    # Record these observations without attributing them to this task or overwriting them.
    require(sha(master_bytes) == baseline['website_files']['Complete_CS_Exit_Study_Guide.html'], 'Website master changed')
    return baseline, rows, courses, questions, parser, {
        'source_files_hashed': len(baseline['source_files']), 'source_changed': source_changed,
        'website_files_hashed_before': len(baseline['website_files']), 'observed_parallel_website_changes': website_changed,
        'observed_parallel_website_additions': website_added,
        'parallel_work_note': 'Observed differences outside this task scope are recorded, not attributed to this task. This verifier writes only its authorized audit/evidence files.',
        'website_master_sha256': sha(master_bytes), 'source_master_sha256': sha((source / 'Complete_CS_Exit_Study_Guide.html').read_bytes()),
        'source_manifest_sha256': sha((ROOT / 'SOURCE_MANIFEST.json').read_bytes()),
        'reading_map_sha256': sha(reading_bytes),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base-url', default=os.environ.get('BASE_URL', 'http://127.0.0.1:8457'))
    ap.add_argument('--static-only', action='store_true', help='Check source preservation and mappings without replacing the DOM audit')
    args = ap.parse_args()
    audit = {'schema_version': 1, 'passed': False, 'generated_at': datetime.now(timezone.utc).isoformat(),
             'scope_note': 'Reference coverage only. Original answers and ambiguity/clarification guidance are preserved; this audit does not assert unique answers for ambiguous questions.',
             'errors': []}
    try:
        baseline, rows, courses, static_questions, parser, preservation = static_checks()
        print('PASS static: 3485 stable IDs, 16 courses, all master sections/course ancestors, exact byte preservation', flush=True)
        if args.static_only:
            return 0
        env = dict(os.environ, BASE_URL=args.base_url, SOURCE_ROOT=baseline['source_root'], READING_MAP=baseline['reading_map_path'])
        proc = subprocess.run(['node', str(ROOT / 'tests/question_references.cjs')], cwd=ROOT, env=env, check=False)
        evidence_path = ROOT / '.qa/ref-dom-evidence.json'
        evidence = json.loads(evidence_path.read_bytes())
        audit['dom_evidence'] = {'path': str(evidence_path.relative_to(ROOT)), 'sha256': sha(evidence_path.read_bytes()),
                                 'browser': evidence['browser'], 'started_at': evidence['started_at'], 'finished_at': evidence['finished_at'], 'base_url': evidence['base_url']}
        require(proc.returncode == 0 and evidence['passed'], 'DOM verification failed: ' + repr(evidence['errors']))
        # Recheck preserved files after the browser run and reject stale/mismatched evidence.
        baseline, rows, courses, static_questions, parser, preservation = static_checks()
        require(evidence['reading_map_sha256'] == preservation['reading_map_sha256'], 'DOM reading-map hash mismatch')
        by_id = {r['id']: r for r in rows}
        counts = Counter(q['id'] for q in evidence['questions'])
        require(set(counts) == set(by_id) and all(n == 1 for n in counts.values()), 'DOM evidence must cover every stable ID exactly once')
        course_evidence = {c['slug']: c for c in evidence['courses']}
        require(len(course_evidence) == 16, 'Missing DOM course evidence')
        for course in courses:
            observed_course = course_evidence[course['slug']]
            require(observed_course['sha256'] == course['after_sha256'], course['slug'] + ': stale DOM page hash')
            require(observed_course['questions'] == course['questions'], course['slug'] + ': DOM count mismatch')
            require(observed_course['hide_all_closes'] and observed_course['reload_defaults_closed'], course['slug'] + ': default closed behavior')
            course['browser_checks'] = observed_course
        for q in evidence['questions']:
            row = by_id[q['id']]
            require(q['slug'] == row['slug'] and q['model_section_ids'] == row['section_ids'], q['id'] + ': DOM map mismatch')
            require(q['initially_closed'] and q['block_count'] == 2, q['id'] + ': initial toggle state')
            require(q['toggle_states'] == [[True, False], [True, True], [False, True], [False, False]], q['id'] + ': independent toggles')
            require(q['answer_container_count'] == 1 and q['answer_container_follows_guidance'], q['id'] + ': answer container')
            require(q['hint_links_visible_when_open'] and q['answer_links_visible_when_open'], q['id'] + ': links not visible')
            for kind in ('hint', 'answer'):
                links = q[kind + '_links']
                expected = ['../../Complete_CS_Exit_Study_Guide.html#' + quote(sid, safe="~()*!.'-_") for sid in row['section_ids']]
                require([a['href'] for a in links] == expected, q['id'] + ': ' + kind + ' DOM href mismatch')
                for sid, link in zip(row['section_ids'], links):
                    require(link['target'] == '_blank' and 'noopener' in link['rel'].split(), q['id'] + ': link target/rel')
                    require(link['in_answer_container'] == (kind == 'answer'), q['id'] + ': QA container mismatch')
                    target = evidence['master_sections'][sid]
                    require(target == {'count': 1, 'tag': 'SECTION', 'course_ancestor': 'course-' + row['slug']}, q['id'] + ': DOM target/course mismatch')
                    require(parser.ids[sid][0]['course_ancestor'] == target['course_ancestor'], q['id'] + ': static/DOM master disagreement')
        require(not evidence['errors'] and not evidence['script_errors'] and not evidence['network_errors'], 'Browser errors')
        audit.update(passed=True, totals={'courses': 16, 'questions': 3485, 'unique_stable_ids': 3485,
                      'hint_blocks_with_valid_links': 3485, 'answer_blocks_with_valid_links': 3485,
                      'hint_section_links': sum(len(q['hint_links']) for q in evidence['questions']),
                      'answer_section_links': sum(len(q['answer_links']) for q in evidence['questions']),
                      'questions_tested_for_independent_toggles': 3485,
                      'missing_ids': 0, 'duplicate_ids': 0, 'missing_hint_links': 0, 'missing_answer_links': 0,
                      'mismatched_links': 0, 'missing_master_sections': 0, 'incorrect_course_ancestors': 0,
                      'script_errors': 0, 'network_errors': 0},
                     insertion={**baseline['insertion'], 'qa_container_class': 'study-note-answer-references',
                                'insertion_point': "Immediately after answer.body.append(el('h3','','Unified note guidance')); inside the existing item.guide branch."},
                     preservation=preservation, courses=courses, questions=evidence['questions'], master_sections=evidence['master_sections'],
                     usage={'full_audit': 'python3 tools/verify_question_references.py --base-url http://127.0.0.1:8457',
                            'static_only': 'python3 tools/verify_question_references.py --static-only',
                            'dom_only': 'BASE_URL=http://127.0.0.1:8457 node tests/question_references.cjs',
                            'baseline': '.qa/ref-baseline.json'})
    except (AssertionError, OSError, ValueError, KeyError) as exc:
        if args.static_only:
            print('FAIL: ' + str(exc), file=sys.stderr)
            return 1
        audit['errors'].append(str(exc))
    (ROOT / 'QUESTION_REFERENCE_AUDIT.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n')
    if audit['passed']:
        print('PASS full audit: all 3485 hint and answer blocks; zero missing/mismatched references; QUESTION_REFERENCE_AUDIT.json')
        return 0
    print('FAIL: ' + '; '.join(audit['errors']), file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main())
