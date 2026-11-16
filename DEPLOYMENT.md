# Deploy to Yegara

This project is ordinary static HTML, CSS and JavaScript. The repository root is the web root: `index.html` must sit directly inside your chosen domain's document root. There is no build step.

## Upload an archive through cPanel

1. Generate the upload archive from this project folder:

   ```sh
   python3 tools/package_site.py
   ```

   This creates `../csexitethiopia-upload.zip`. It contains runtime files with `index.html` at the archive root, and excludes Git metadata, development tests and local verification screenshots.

2. In Yegara cPanel, check the document root assigned to the domain you want to use. It is commonly `public_html` for the primary domain; an additional domain may have its own folder. Select the correct domain's folder.
3. Back up any existing website in that folder before replacing its files.
4. Upload and extract the ZIP there. Confirm the result is `DOCUMENT_ROOT/index.html`, rather than `DOCUMENT_ROOT/csexitethiopia/index.html`.
5. Keep `assets/`, `Questions/` and `Outlines/` beside the complete guide. Keep hidden `.htaccess` with the upload.
6. Open the domain over HTTPS and try all three study options and a Copy button. HTTPS supports the normal Clipboard API; a local-copy fallback is also included.
7. Remove the uploaded ZIP from the public folder after extraction. The local archive remains available.

Official instructions: [Yegara File Manager and FTP guide](https://yegara.com/en/guide/how-to-upload-your-website-files-to-your-cpanel-using-file-manager-and-ftp/).

## GitHub updates

After the GitHub remote is configured, use this workflow for later changes:

```sh
git pull --ff-only
# Make and verify your changes.
python3 tools/verify_site.py
git add .
git commit -m "Describe the update"
git push
python3 tools/package_site.py
```

Upload the refreshed archive to the same document root. If you use cPanel Git Version Control instead, clone the repository using an authorized GitHub connection and configure deployment to that domain's document root. No GitHub Actions build is needed. This project does not assume a cPanel username or a specific server path.

## Hosting notes

- File names are case-sensitive on typical Linux hosting. Keep their existing capitalization.
- Existing educational HTML contains inline styles, scripts and data images. Do not add a restrictive content-security policy that blocks them without testing the readers.
- The supplied `.htaccess` sets the home page, disables directory listings, enables compression/cache settings when their Apache modules exist, and prevents Git metadata from being served. No SPA rewrite rule is needed.
- Donations are optional displayed account details, not a checkout integration. Study resources are available immediately regardless of support.
