# CS Exit Ethiopia

A free static Ethiopian Computer Science Exit Exam preparation hub: 16 courses, 3,485 practice questions, complete notes, revision outlines and original PDF modules. No account, ads, analytics or server-side service.

## Preview

Use HTTP/HTTPS for search, PDF exports and embedded PDF viewing:

```sh
python3 tools/serve.py --port 8457
```

Open `http://127.0.0.1:8457/`. Hosting needs only static files; Python, Node.js and PDF libraries are development tools, not hosting requirements.

## Domain configuration

Edit **only `SITE_URL` in `site.config.js`**, then regenerate domain-derived metadata:

```sh
python3 tools/build_site.py --metadata-only
```

This updates canonical URLs, social tags, JSON-LD, sitemap, robots, browser configuration and footer branding. When changing the domain, regenerate prebuilt PDFs too, so printed attribution uses the new domain. The default is `https://csexitethiopia.com`; configuring it does not register a domain or set DNS.

## Public resources

- `index.html`: resources, study routine, optional support and contact.
- `Complete_CS_Exit_Study_Guide.html`: static, hierarchical notes with reading-section IDs and lazy question lookup.
- `Questions/Interactive_Study_Guides/`: 16 static course readers; independent hints and answers start closed.
- `Outlines/`: 16 interactive revision readers; progress stays in the browser, with import/export.
- `Modules/`: 16 course viewers and 14 unchanged original PDFs. Two pairs of courses share a PDF.
- `downloads.html`: select one, custom multiple or all 16 courses for each PDF resource.
- `search.html`: searchable notes, questions, outlines and modules, with course/type filters.
- `sitemap.xml`, `robots.txt`, favicons and self-hosted social preview assets.

All HTML navigation uses relative paths and stays in one tab. Third-party references have an external indicator and open a separate tab. The shared responsive menu switches below 992px. Course progress uses the existing version/source checksum format.

## PDF architecture

Single-course and all-course PDFs are prebuilt vector documents under `assets/pdf/`. They contain cover pages, course contents, course dividers, readable text, references and running attribution/page numbers. Custom selections are assembled in a Web Worker from vector PDF fragments using self-hosted pdf-lib. No screenshots, runtime CDN or server-side PDF generation is used. A browser download progress indicator supports cancellation and retry.

Question PDFs include current prompts, options, answers, explanations, choice contrasts, exact study-note evidence, and original module page/line excerpts where available. Module excerpts are identified as related reading; the current study-note evidence remains the answer proof when an old module did not cover that concept. Extended explanations can continue onto another page while short question blocks and prompt/choices are kept together.

Rebuild PDFs using the development environment with ReportLab, pypdf, PyMuPDF, svglib, Pillow and fontTools installed:

```sh
python3 tools/build_pdfs.py --validate
```

The generator reads `site.config.js` and `assets/export-data/`. See `--help` for course/type selection and resumable subset builds. PDF generation is optional maintenance; deployed downloads are already generated.

## Source preservation and maintenance

The public readers contain reviewed educational HTML directly, allowing reading and crawling without JavaScript. Lightweight scripts provide search and interaction. Large legacy review data is no longer duplicated inside every reader.

`maintenance/source-snapshots/` preserves the exact original imported educational HTML bytes; `maintenance/public-baseline/` preserves the reviewed student-facing DOM used to compile the static readers. `SOURCE_MANIFEST.json` records recovery hashes. The original workspace, 14 module PDFs and canonical answer/support ledgers are unchanged. These maintenance files are excluded from hosting.

`tools/build_site.py` rebuilds readers from the reviewed baseline and reapplies metadata, navigation and routing. After an intentional content update, review/update that baseline and export data before rebuilding. Earlier overlay scripts and historical audit files remain maintenance history; do not reapply those overlays to this static reader architecture.

## Verification

Development dependencies include Python lxml and Playwright/Chrome for browser checks. Use your Python/Node environment for these optional checks:

```sh
python3 tools/verify_site.py
python3 tools/verify_platform_content.py
node tests/platform.cjs
node tests/platform_all_courses.cjs
node tests/pdf_exports.cjs
```

The checks cover all public links and metadata, source recovery, 3,485 questions and 24 source variants, every note/proof, outline content/progress, responsive layout, routing, donation copying, search, PDF selection and persistent favicons. PDF generation validation checks exported item totals, text, page counts and font coverage; rendered PDF samples are reviewed visually.

See [DEPLOYMENT.md](DEPLOYMENT.md) for Yegara/cPanel upload instructions. No ZIP is produced automatically by a build or verification.
