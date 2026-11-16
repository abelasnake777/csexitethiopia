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
- `ANSWER_REVIEW_SUMMARY.html`: readable course counts and links to flagged source questions.
- `SOURCE_MANIFEST.json`: copied-resource hashes and content-preservation records.
- `VERIFICATION.json`: verification summary for this release.
- `tools/` and `tests/`: optional development checks and packaging tools; not required by the website.

Keep all four resource paths together. Existing reading-section links, practice-question lookups and Word-outline downloads depend on this structure. Paths work at a domain root or inside a subdirectory.

## Preserved educational content

Resources were copied from the existing Exit Study materials. Original source files and the complete study note were left untouched. Imported HTML has removable navigation additions; question readers also have a study-note reference insertion and a current-answer review overlay. Removing the three exact blocks recorded in `SOURCE_MANIFEST.json` recovers the original question reader byte for byte. The original embedded question JSON, stems, choices, provenance, images and historical reviews are unchanged.

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

## Question reference coverage

Every one of the 3,485 questions has links to its mapped study-note sections in both the hint and answer blocks. The full reference audit checks actual rendered links, intended course sections, IDs/order and independent default-hidden controls. It checks **reference-link coverage**, not answer correctness. A working reference does not prove that a damaged or ambiguous question has one answer.

All 2,164 records previously marked module-insufficient, source-gap, source-unverified or ambiguous have separate current reviews. The 1,321 previously module-verified records remain unchanged. Open-ended prompts receive written answers; missing options alone do not make a prompt incomplete. Multiple valid choices, assumptions that change the answer, absent correct options, missing data and genuine note gaps remain distinct. Where an authoritative supplementary rule is supplied, the answer explicitly labels the complete note as background instead of claiming the missing rule is already there.

`ANSWER_REVIEW_SUMMARY.html` and `STUDY_NOTE_ANSWER_REVIEW.json` record the current counts and remaining limitations. No check guarantees a score or authenticates a source key. `QUESTION_REFERENCE_AUDIT.json` contains the separate per-question link results.

Portable current-answer checks, using the question files and actual unchanged note HTML:

```sh
python3 tools/verify_study_note_answers.py
node tests/study_note_answers.cjs
```

The second command checks every current answer at desktop and phone widths, rendered choice analysis, evidence, archived legacy content and default-hidden behavior. Reapply reviewed data or regenerate the readable report after an intentional review update with:

```sh
python3 tools/apply_study_note_answers.py
python3 tools/build_answer_review_summary.py
```

The exhaustive reference helper under `tools/` uses the author's saved baseline in `.qa/` and original Exit_Study workspace. These are development inputs, not hosting dependencies. Portable copied-resource and local-link checks remain available through `tools/verify_site.py`.
