# Deploy on Yegara / cPanel

This is a pure static website. Put `index.html` at the domain's document root, preserving all filename capitalization and relative folders. No Node.js build, database, API key or running server is required.

1. Register/connect your chosen `.com` domain, set its DNS to your hosting account, and enable HTTPS in cPanel.
2. If the domain differs from `https://csexitethiopia.com`, edit `SITE_URL` in `site.config.js`, run `python3 tools/build_site.py --metadata-only`, and regenerate the prebuilt PDFs to update their printed attribution.
3. Verify with `python3 tools/verify_site.py` and the documented content/browser/PDF checks.
4. Upload only the public allowlist from `tools/public_files.py`. It includes all public HTML, favicon files, `site.config.js`, robots/sitemap, runtime assets, PDF downloads/fragments, original module PDFs and course readers. It excludes authoring ledgers, source snapshots, tests, tools, QA images and old Word outlines.
5. Open the HTTPS home page on phone and desktop. Test one internal course link, a reading reference, an original module PDF, a single-course PDF, a custom selection, optional support copy buttons and the favicon after navigation.
6. Submit `https://YOUR-DOMAIN.com/sitemap.xml` to the domain's verified Search Console property. Structured data and metadata support discovery; search placement and rich display are controlled by search engines.

Use cPanel File Manager or an authorized Git checkout/deployment that copies the public allowlist into the correct document root. The repository is private; no repository visibility change is needed. Do not expose the entire repository as downloadable files. Apache rules deny access to Git metadata and maintenance records as an additional safeguard.

The owner has deferred archive generation until final corrections are complete. When explicitly requested, `python3 tools/package_site.py` can generate the public upload ZIP; it is not part of verification or normal builds.

## Server configuration

Keep `.htaccess`: directory index, no directory listings, compression, static caching, `.mjs`/`.wasm`/PDF MIME types and private-path blocks are included. Do not add SPA rewrites: real `.html` files and section anchors are used throughout. The site works at a domain root or subdirectory; canonical URLs describe the configured production root.

Keep the full `assets/pdfjs/`, `assets/vendor/pdf-lib/`, `assets/pdf/` and all `Modules/files/` assets. Search and PDF assembly use same-origin fetch, so preview over HTTP/HTTPS rather than opening files directly from disk. The embedded original-module reader is loaded only on module pages; pdf-lib loads only when combining a custom PDF.

Single/all-course PDF cover dates record their generated edition. A custom selection uses the current download date. Regenerate PDFs when publishing an educational-content update.
