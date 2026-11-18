/* Edit this one line, then run: python3 tools/build_site.py --metadata-only */
const SITE_URL = 'https://csexitethiopia.com';
const SITE_CONFIG = Object.freeze({
  SITE_URL,
  SITE_NAME: 'CS Exit Ethiopia',
  EMAIL: 'abelasnake2003@gmail.com',
  TELEGRAM: 'Abechu7',
  LANGUAGE: 'en',
  COUNTRY: 'Ethiopia'
});
if (typeof module !== 'undefined' && module.exports) module.exports = SITE_CONFIG;
else globalThis.CS_EXIT_CONFIG = SITE_CONFIG;
