# PDF sources: one legal copy per paper

Merged from the project fork at `Writing-Text-Effect/.cursor/skills/paper-search`.

Applies when the user is at CUHK or another institution with a proxied
subscription, and wants a readable full text rather than a DOI link.

## The rule

One stored PDF, on the Zotero item (or in one download folder if the user is
not using Zotero). Check for a real file first — `data.md5` or an enclosure
link. Stop when one exists. Never keep a copy in `references/` *and* attach it
in Zotero.

Never use Sci-Hub, LibGen, or another grey source unless the user explicitly
chooses that source for that run.

## Ladder

Try these in order for items that still have no file. Stop at the first source
that returns a PDF larger than 10 KB beginning with `%PDF-`.

1. **Zotero.** If Find Available PDF or the user's own retrieval is already
   running, wait and recheck. Do not start a parallel download of the same DOI.
2. **Open access.** Unpaywall, using the email already configured for
   `PAPER_SEARCH_MAILTO`. Do not invent an address. arXiv for preprints.
3. **Elsevier (`10.1016`).** Check entitlement before downloading; a valid key
   returning `403` / `NOT_ENTITLED` is not entitlement. Do not set an
   institutional token you were not given. Proxy cookies do not fix this API.
4. **Other publishers via CUHK Easy Access.** Use a browser the user has
   already signed into (CUHK Login and 2FA). Do not drive the login with
   automation. Read the PDF from that signed-in session:
   - Off-campus prefix: `https://login.easyaccess1.lib.cuhk.edu.hk/login?url={url}`
   - Taylor & Francis and Sage: proxied `/doi/pdf/{doi}`
   - Wiley: `/doi/pdfdirect/` then `/doi/pdf/`
   - Emerald: the page's `citation_pdf_url`
   - ScienceDirect: the article's own View PDF link (`/pdfft?md5=...`) for that
     article's PII
   A link that returns HTML, a challenge page, or a purchase box is a miss.
5. **Still missing.** Record the DOI URL and the last miss, and tell the user
   plainly. They can pull it through the library. Do not substitute a grey
   source and do not claim a PDF you did not get.

CUHK Library forbids bulk downloading. Fallback downloads are sequential, one
DOI at a time.

The script's `fetch` command already covers steps 1–2 (OpenAlex best OA,
Unpaywall, arXiv, publisher `citation_pdf_url`). Use this ladder for what it
reports as `--` (no open-access copy) or `!!` (tried and failed).
