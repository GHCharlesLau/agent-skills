# Zotero filing: metadata rules and local writes

Merged from the project fork at `Writing-Text-Effect/.cursor/skills/paper-search`.
Use this when the user wants clean, citable records — APA sentence-cased titles,
decoded entities, no duplicate parent items — rather than the script's default
bulk import.

The script's `zotero` subcommand handles bulk import. This file is for the case
where the *quality of each record* matters: a paper going into a manuscript.

## Metadata

Decode HTML entities on every text field before writing. Strip tags after
decoding. Write `&`, never `&amp;` — `New Media & Society` stays
`New Media & Society`.

| Field | Rule |
|---|---|
| `title` | APA sentence case. See below. |
| `publicationTitle` | Journal title case, full name. |
| `creators` | `firstName` / `lastName` from given / family. |
| `DOI` | Bare DOI, no `https://doi.org/` prefix. |
| `url` | `https://doi.org/` plus the DOI. |
| `date` | Year from Crossref `issued`, or fuller ISO date when the parts exist. |
| `abstractNote` | Decoded and tag-stripped. Omit if absent. |
| `collections` | Only the confirmed collection key. |

Volume, issue, pages, and ISSN are copied when the source has them.

Never copy Crossref's title case into `title`. Crossref capitalises almost every
word, so a mid-title capital is **not** evidence of a proper noun.

## APA sentence case

- Capitalise the first word, the first word after a colon, and proper nouns.
- Keep acronyms that are already all capitals (`AI`, `COVID-19`, `SMS`).
- Lowercase everything else.
- No italics or quotation marks in the field; citation styles add journal
  italics.

Lowercase a mid-title capital unless it is an acronym, the first word of the
title or subtitle, or a name you actually know (a platform, place, or person).
When a capital might be a proper noun and you cannot tell, keep it and record
the DOI under a "case uncertain" line in the log.

Example:

- Source: `The Role of AI Attribution in Feeling Heard: Evidence from Online News`
- Stored: `The role of AI attribution in feeling heard: Evidence from online news`

After a batch, generate one sample reference. If APA lowercases a proper noun
there, protect that word in Zotero instead of putting the whole title back into
title case.

## Zotero local API

Zotero must be open. Base URL `http://127.0.0.1:23119`.

Send on every request:

- `Zotero-API-Version: 3`
- `Zotero-Allowed-Request: 1`

Reads also need the server id: `GET` a known collection and copy
`Zotero-Server-ID` from the response. Do not reuse an id from an old session.

Writes need a local key: `POST /api/local/authorize` with
`{"appName":"paper-search"}`, then send the returned key only as
`Zotero-API-Key`. Never print, log, or store it in a project.

Failure codes worth knowing: `POST /items` without the key → 401; without
`appName` → 400; without `Zotero-Server-ID` → 428.

### Create without duplicating

Before creating, search `q=<doi>`, `qmode=everything`,
`itemType=journalArticle`, and keep a parent only when its DOI matches exactly.
If the item exists, add it to the target collection instead of creating a
second parent.

`POST /collections/{key}/items` returns 405. The call that works is
`PATCH /items/{key}` with `If-Unmodified-Since-Version` and
`{"collections":[...]}`.

### Attaching the PDF

Only after the bytes are known to be a PDF. Create a child with
`itemType: attachment`, `linkMode: imported_file`,
`contentType: application/pdf`, `parentItem`, and a filename built from the DOI
with every `/` replaced by `_`.

Then:

1. `POST /items/{attachmentKey}/file` as `application/x-www-form-urlencoded`
   with `md5`, `filename`, `filesize`, `mtime`, header `If-None-Match: *`.
2. `POST` the raw bytes to the `url` in that JSON response, using the returned
   `prefix`, `suffix`, `uploadKey`, `contentType`.
3. `POST` the same item file endpoint with `upload=<uploadKey>`.

Posting raw PDF bytes to the item file endpoint returns 400
(`MD5 hash not provided`). An attachment with no `md5` and no enclosure is not
a stored PDF.

Collection JSON that includes full attachments can time out while Zotero
indexes — retry a short item list before treating the write as failed.
