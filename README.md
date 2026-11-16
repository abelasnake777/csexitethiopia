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
- `QUESTION_REFERENCE_AUDIT.json`: exhaustive per-question hint and answer reference checks.
- `SOURCE_MANIFEST.json`: copied-resource hashes and content-preservation records.
- `VERIFICATION.json`: verification summary for this release.
- `tools/` and `tests/`: optional development checks and packaging tools; not required by the website.

Keep all four resource paths together. Existing reading-section links, practice-question lookups and Word-outline downloads depend on this structure. Paths work at a domain root or inside a subdirectory.

## Preserved educational content

Resources were copied from the existing Exit Study materials. Original source files were left untouched. Each copied HTML page has one marked, removable head block that loads shared navigation. Question readers retain their original content-security policy; their navigation is embedded inline because those pages already allow inline code and block external scripts. Question readers also contain a marked, authorized addition that puts the mapped study-note links inside each answer block as well as the hint. Removing both marked additions recovers each original file byte for byte. Original educational text, embedded questions, answer choices, explanations, tables, images and scripts have not been rewritten.

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

Every one of the 3,485 questions has links to its mapped study-note sections in both the hint and answer blocks. The full audit checks actual rendered links, course ownership of target sections, IDs/order and independent default-hidden controls. Existing question data, historical answers and ambiguity guidance remain unchanged. Reference coverage does not turn an ambiguous source item into a uniquely answerable question.

QUESTION_REFERENCE_AUDIT.json contains the per-question results. The detailed audit helper under tools/ uses the author's saved baseline in .qa/ and original Exit_Study workspace; those are development inputs, not hosting dependencies. Portable copied-resource and local-link checks remain available through tools/verify_site.py.
