# CS Exit Ethiopia

A free, buildless Computer Science Exit Exam study hub for Ethiopian students. Open `index.html` to choose the complete study guide, interactive questions, revision outlines or original course modules. No accounts, advertising, analytics, paywalls or backend services are used.

## Run locally

Open `index.html` directly, or use any static web server. For example:

```sh
python3 -m http.server 8000
```

Then visit `http://localhost:8000`. A server is useful for checking clipboard behavior. Python is a local preview option, not a hosting dependency.

## Project structure

- `index.html`: home, study routine, optional support and contact information.
- `assets/`: lightweight CSS, vanilla JavaScript and favicon.
- `Complete_CS_Exit_Study_Guide.html`: the complete study note.
- `Questions/Interactive_Study_Guides/`: 16 course readers and their course selector.
- `Outlines/`: 16 course revision readers, their selector and the earlier Word outlines.
- `Modules/`: 16 course entries, an embedded PDF reader and 14 original PDFs (two pairs of courses share files).
- `QUESTION_REFERENCE_AUDIT.json`: exhaustive per-question hint and answer reference-link checks.
- `STUDY_NOTE_ANSWER_REVIEW.json`: current review data and explicit answer-certainty statuses.
- `ANSWER_COMPLETENESS_AUDIT.json`: definite-answer coverage for all main questions and alternative source versions.
- `ANSWER_REVIEW_SUMMARY.html`: readable course counts and links to flagged source questions.
- `SOURCE_MANIFEST.json`: copied-resource hashes and content-preservation records.
- `VERIFICATION.json`: verification summary for this release.
- `tools/` and `tests/`: optional development checks and packaging tools; not required by the website.

Keep all four resource paths together. Existing reading-section links, practice-question lookups and Word-outline downloads depend on this structure. Paths work at a domain root or inside a subdirectory.

## Preserved educational content

Resources were copied from the existing Exit Study materials. Original source files and the complete study note were left untouched. Imported HTML has removable navigation additions; question readers also have a study-note reference insertion and a current-answer review overlay. Removing the three exact blocks recorded in `SOURCE_MANIFEST.json` recovers the original question reader byte for byte. The original embedded question JSON, stems, choices, provenance, images and historical reviews are unchanged.

Clarified practice versions use user-approved intended readings, including: restored aⁿbⁿcⁿ notation, permission mode -rwxr--r--, simultaneous FCFS arrivals, and an explicit two-path project network ending at day 9. Their displayed stems and cleaned choices are labeled as clarified practice versions; original imported JSON and source wording remain recoverable in the audit. The search index follows the clarified wording.

The current-answer overlay places new complete-note explanations and literal evidence before the older review. Historical hints and answers remain in independently collapsed archives, so old module-only limitations do not masquerade as current answers. Existing module-verified answers are retained. The imported content-security policy stays unchanged; the new code and review data are embedded inline for compatibility with that policy.
The shared navigation adds Home and resource links. The questions selector receives presentation-only responsive grid styling. Other resource layouts retain their existing styles. Non-HTML resources are identical copies. The manifest documents these checks.

## Optional support and contact

All study resources remain free. Support details are displayed on the home page with local clipboard buttons; the site does not process payments. Contact links open the visitor's email, phone or the requested social profile. No data is submitted to a server by this website.

Edit the home page only to change these details. Browser review progress is managed by the existing revision readers and stays in each student's browser. Students can use their readers' export/import controls to move progress.

## Deploy

See [DEPLOYMENT.md](DEPLOYMENT.md). Upload the static files to the chosen domain's document root on Yegara. No Node.js install, build command, database, API key or server process is required.

## Optional verification

Check all copied files and static local links using Python's standard library:

```sh
python3 tools/verify_site.py
```

To also verify against the untouched original materials on the author's machine:

```sh
python3 tools/verify_site.py --source ../Exit_Study
```

The browser regression test uses an externally installed Playwright package and Chrome. These are development tools only. For browser QA, start `python3 tools/serve.py` in a separate terminal. This serves port 8457 and a subdirectory alias for the relative-path check. Set `PLAYWRIGHT_MODULE` and `CHROME_BIN` for your environment, then run:

```sh
node tests/browser.cjs
```

It checks the home page at desktop, tablet and phone widths; every course reader at desktop and phone widths; home navigation; clipboard values and fallback; original question toggles; outline progress; and subdirectory hosting. Screenshots and detailed results go in ignored `.qa/`.

## Course modules

The Modules catalog offers online viewing and PDF downloads for all 16 courses. Database Fundamentals and Advanced Database use the same complete PDF; Networking and System Administration share another. Course viewers start at the verified physical PDF page for the relevant course. Downloads retain the complete original PDF.

The embedded viewer uses self-hosted Mozilla PDF.js, loaded only on module viewer pages. Page controls and zoom work on desktop and phones; Open PDF supports browser search, selection and printing. PDF.js, its fonts and decoders are static files under assets/pdfjs/; no CDN or build is needed. Its license and version/integrity record are included.

If opening HTML directly from disk, use Open PDF or Download PDF. The embedded viewer needs HTTP/HTTPS; use the local QA server for preview. Apache MIME types for .mjs and .wasm are included in .htaccess.

## Question answers and study-note support

Every one of the 3,485 main practice questions and 24 alternative source versions has an explicit answer. Each question has an independent, default-hidden reading hint and answer/explanation block, including choice-by-choice reasoning and exact supporting study-note passages. The study-note lookup uses the current clarified practice wording.

The bank contains 3,026 single-answer questions, 199 explicit select-all questions and 260 written prompts. 1,060 adapted question records retain their editorial history for maintenance; students see concise source attribution. The global exact stem-and-options duplicate check found zero duplicate groups. Original imported question data and historical reviews are retained.

The full grounding review added 86 focused conceptual lessons to fill missing coverage. All existing guide text is preserved byte for byte, recoverable by removing the exact additive blocks in `SOURCE_MANIFEST.json`. The original materials in Exit_Study are untouched. Module PDF bytes and the underlying revision-outline data are unchanged; public wording is presented through a reversible display layer.

`ANSWER_REVIEW_SUMMARY.html` is an author-only course overview, excluded from hosting. `STUDY_NOTE_SUPPORT.json` records every active answer, reading hint, exact evidence and editorial resolution; `STUDY_NOTE_SUPPORT_AUDIT.json` verifies its coverage and actual note passages. `ANSWER_COMPLETENESS_AUDIT.json` checks definite answers and exact duplicate prompts. `QUESTION_REFERENCE_AUDIT.json` separately records every rendered reference link and independent toggle. Editorial relevance review and automated coverage checks are distinct; these records do not authenticate an imported exam key or predict a score.

Portable verification (no build step for hosting):

```sh
python3 tools/verify_site.py
python3 tools/verify_study_note_support.py
python3 tools/verify_study_note_answers.py
python3 tools/verify_answer_completeness.py
```

With the local QA server running, browser checks cover all questions and source versions, detailed explanations and choice contrasts, exact note proof, hidden controls, the active reading lookup and added lessons on desktop and phones:

```sh
node tests/study_note_answers.cjs
node tests/answer_completeness.cjs
node tests/study_note_support.cjs
node tests/public_copy.cjs
```

To reapply an intentionally reviewed update, apply `tools/apply_study_note_support.py`, then `tools/apply_study_note_answers.py` and `tools/apply_public_copy.py`, regenerate audits and run `tools/build_answer_review_summary.py`. The exhaustive reference helper additionally uses the author's saved baseline in `.qa/` and the original workspace. These are development inputs, not hosting dependencies. ZIP generation remains deferred at the owner's request.

## Public presentation

The public readers show academic source names, study instructions and useful references. Local filenames, editorial notices, earlier answer-review panels and internal audit links are omitted from the student interface. The study guide bibliography links to accessible course modules and public references. Question text, choices, keys, diagrams and section IDs are retained. Generic copy edits do not apply to question stems, choices or code blocks.

`PUBLIC_READER_COPY.json` records reviewed wording changes and source titles for maintenance. `tools/apply_public_copy.py` embeds the relevant presentation rules into the existing static readers, including pages with restrictive inline-only script policies. The exact removable block is recorded in `SOURCE_MANIFEST.json`; all original imported source bytes remain recoverable. Run the public-copy helper after regenerating any course or guide page.

`tools/public_files.py` is the public upload allowlist used by the archive helper. Authoring ledgers, audit reports, development tools and screenshots are excluded. Apache rules also deny access to those maintenance files if a full checkout is uploaded. No archive is created by verification or by applying copy changes.

```sh
python3 tools/apply_public_copy.py
node tests/public_copy.cjs
```
