---
name: paper-search
description: Finds relevant research articles from keywords, a rough topic, or an unstructured description of what the user is thinking about. Expands vague ideas into academic search queries, searches OpenAlex, arXiv, PubMed and Crossref, deduplicates results, filters for high-quality venues (SSCI/SCIE-indexed journals plus Nature/Science/PNAS and credible preprints from reputable scholars or top institutions), judges relevance from titles and abstracts, and can export BibTeX or walk citations forward and backward. Also generates an interactive picker for choosing which results to keep, downloads open-access PDFs, and imports the chosen records into a Zotero subcollection. Use when the user asks to find papers, literature, references, related work, prior studies, or evidence; asks "what has been done on X", "is there research on...", 找论文, 查文献, 相关研究, 文献综述; or describes a half-formed research idea and wants to know what exists.
disable-model-invocation: false
---

# Paper Search

Turn a vague thought or a few keywords into a short list of genuinely relevant papers, with a reason attached to each one.

## Quick start

```bash
python scripts/paper_search.py search -q "query one" -q "query two" --year-from 2015 --save ./refs
```

Paths are relative to this skill's base directory. Then read the printed table, open the saved `.json` for abstracts, and do the relevance judgment yourself (Step 4). The script ranks by keyword overlap and citations; **that ranking is a starting order, not an answer.**

## Workflow

```
- [ ] 1. Turn the request into a search brief
- [ ] 2. Write 4-8 query variants
- [ ] 3. Run the script (wide net)
- [ ] 4. Judge relevance from abstracts
- [ ] 5. Report, grouped by role
- [ ] 6. Offer the next move
```

### Step 1 — Search brief

Extract, silently: **topic**, **population/context**, **discipline**, **time window**, **what the user actually wants** (evidence? a gap? a method? a citation for a claim?).

Write the brief as one line at the top of your answer. Do **not** interrogate the user first — infer and state assumptions.

Ask at most one clarifying question, and only when the word is genuinely ambiguous across fields ("attention", "alignment", "agency", "transfer"). Otherwise proceed.

If the user writes in Chinese, convert concepts to English academic terms — the databases are English-dominant.

### Step 2 — Query variants

One query is never enough. Produce 4–8, varying along these axes:

| Axis | Example (from "attention") |
|---|---|
| Core construct, academic phrasing | "sustained attention", "attentional control" |
| Synonyms / near-synonyms | "mind wandering", "vigilance decrement" |
| Theory or framework names | "load theory of attention", "resource depletion" |
| Method / instrument | "continuous performance task", "eye tracking" |
| Population / setting | "undergraduate students", "classroom" |
| Adjacent literature | "executive function", "self-regulation" |

Rules:
- Keyword phrases, not sentences. OpenAlex `search` is bag-of-words; "how do students feel about X" retrieves noise.
- Prefer the term the literature would use, not the term the user used.
- Every query should be independently meaningful — when a subject is new, do not stack five near-identical strings.

**Worked example.** User says: *"I'm thinking about how students react when AI grades their essays and whether they trust feedback less afterwards."*

Brief: learner trust in AI-generated feedback · higher education · applied linguistics + educational psychology · post-2018.

```
1. "automated writing evaluation learner trust feedback"
2. "AI-generated feedback credibility student perceptions writing"
3. "trust automated feedback higher education"
4. "feedback literacy artificial intelligence writing"
5. "student uptake automated corrective feedback"
6. "algorithmic grading acceptability fairness students"
```

### Step 3 — Run

```bash
python scripts/paper_search.py search \
  -q "automated writing evaluation learner trust" \
  -q "AI-generated feedback credibility student perceptions" \
  -q "feedback literacy artificial intelligence writing" \
  --year-from 2018 --limit 25 --top 30 --save ./refs \
  --bib "D:\path\to\references"
```

`--bib` appends to a `.bib` file — or, given a directory, writes `paper-search-YYYYMMDD.bib` there. Entries whose DOI or title already exist are skipped, so it is safe to re-run. It never overwrites.

Choose sources by field — trim the noisy ones:

| Field | Sources |
|---|---|
| Education, psychology, social science, management, humanities | `openalex,crossref` |
| CS, ML, physics, math, economics preprints | `openalex,arxiv` |
| Biomedicine, public health, neuroscience | `openalex,pubmed` |
| Maximum recall (best citation graph) | add `s2` — needs a key, see Notes |
| Unsure / interdisciplinary | all four (the default) |

Defaults: `--limit 25` per query per source, merged and capped at 60. That is a net, not a reading list. Expect to keep 10–20%.

Use `--min-cites 20` when the user needs established work rather than the newest preprints. Use `--oa-only` when they will want full text.

Read the JSON (`--format json`, or the saved `.json`) for abstracts. You need abstracts to judge; the brief table is not enough.

## Quality gate

Results are **filtered before they reach the user**. The default is `--quality balanced`; the policy comes from the user and is not negotiable:

| Tier | Tag | Meaning |
|---|---|---|
| flagship | `[FLAG]` | Nature / Science / PNAS / top field journals (Journal of Marketing, JCR, SMJ, ASQ, MISQ, AMJ…) |
| indexed | `[SSCI]`/`[SCIE]` | In the curated allowlist (`journals.csv`) |
| preprint-ok | `[PRE+]` | Preprint with a co-author whose h-index ≥ 20, or an affiliation at a top-tier university or major company |
| unverified | `[UNV]` | Real-looking journal from a reputable publisher, but not yet in the allowlist — balanced mode only |
| preprint / low | *(dropped)* | Preprint without reputable authors, or a venue with no ISSN / unknown publisher |

- `strict` keeps flagship + indexed + preprint-ok only. `off` disables the gate.
- Ranking is tier first, then relevance — so a 30-citation SSCI paper outranks a 2,000-citation conference paper.
- In the report, put the tag next to each paper and mention the tier so the user can see the policy applied.
- An `[UNV]` item is a judgement call: check the journal's current WoS status before recommending it as evidence; if it is genuinely SSCI/SCIE, add it so future searches classify it automatically:
  `python scripts/paper_search.py journals --add "Journal Title" --index SSCI`
- Preprints are labeled preprint in the report; do not present them as peer-reviewed.

### Step 4 — Judge

Group every surviving record into one of four roles:

- **Core** — studies the relation the user asked about, in a comparable population or setting. These are the answer.
- **Adjacent** — same construct, different outcome or population. Useful for framing and for showing the boundary of existing work.
- **Method / instrument** — measurement scales, coding schemes, study designs the user could reuse.
- **Landmark** — older, heavily cited, still defines the conversation. Label it as such; do not present it as current evidence.

Discard, without listing:
- Keyword collisions in the wrong discipline sense.
- Venue noise: predatory or pay-to-publish journals, conference abstracts, theses with no peer review. If the venue looks unrecognisable, verify before citing.
- Anything whose abstract does not actually support the relevance sentence you were about to write.

Never rank by citation count alone — a 900-citation 1998 paper can be off-topic. Never describe a paper's findings from its title. If the abstract is missing, say the abstract is unavailable rather than inferring.

Verify a DOI link resolves before recommending it, when the recommendation matters.

### Step 5 — Report

```markdown
**Brief:** <topic · population · window>

### Core (n)
| Paper | Why it matters |
|---|---|
| Author (Year). *Title*. Venue. [doi](...) | one sentence on the specific finding or argument |

### Adjacent / framing (n)
### Methods & instruments (n)
### Landmarks (n)

**Where the evidence converges**
- ...
**Where it conflicts or thins out**
- ...
**Gaps worth a study**
- ...
```

Keep "why it matters" to one line, specific, and about the user's question — not a generic summary of the paper. Cap each group at what is genuinely useful; five strong papers beat twenty padded ones.

If the result set is thin, say so plainly and name what you tried. A confident "there is very little direct work on this, the closest is X" is more useful than a padded list.

### Step 6 — Next move

Offer, don't perform unasked:

- **Snowball** from the best paper — the single highest-yield step for a real literature review.
- **Pick and download** — generate the interactive picker so the user chooses (see Stage 2).
- **Full text** — parse a local PDF with the `mineru-document-extractor` skill.
- **Library** — import the chosen records into a Zotero subcollection (see Stage 3).
- **Narrow** — re-run with a tighter population or a specific theory.

## Stage 2 — let the user choose, then download

Never download blindly and never assume which papers they want. Generate the picker:

```bash
python scripts/paper_search.py pick --from-json refs/<name>.json --open
```

A self-contained `.pick.html` opens locally: filter by text/year/open-access, sort, tick boxes, expand abstracts. It shows `N selected` and a **Copy selection** button producing `2,5,9-11`, which the user pastes back into the chat. It also offers `selection.json`.

Wait for the user. If they reply "the OA ones" or "top 5", translate that into indices yourself and read the list back to them for confirmation before downloading.

Then download:

```bash
python scripts/paper_search.py fetch --from-json refs/<name>.json --select "2,5,9-11" --out refs/pdfs
```

Each paper is tried via OpenAlex's best OA PDF, Unpaywall (needs `PAPER_SEARCH_MAILTO`), arXiv, then the publisher's `citation_pdf_url`. Statuses: `OK` downloaded, `have` already there, `!!` tried and failed, `--` no open-access copy, `?` dry run. A `fetch-manifest.json` records every attempt.

Be honest about the failures. Paywalled papers legitimately cannot be fetched — report them and suggest the user pull them through the university library. Do not attempt to bypass paywalls, and do not invent a PDF that was not downloaded.

## Stage 3 — import into a Zotero subcollection

```bash
python scripts/paper_search.py zotero --from-json refs/<name>.json \
  --select "2,5,9-11" --collection "CSR skepticism" --pdf-dir refs/pdfs
```

Add `--dry-run` first: it reports, per paper, whether it would import or just link an existing library item, and writes nothing. Use it whenever the collection name or selection is new.

Three backends, chosen automatically:

- **Local Zotero (preferred)** — detected when `http://localhost:23119/api` responds. No keys to configure, but Zotero must be running. Writes need a one-time grant: run with `--authorize` and approve the dialog in Zotero; the key is cached in `~/.cache/paper-search/zotero-local.json`.
- **Web API** — if `ZOTERO_API_KEY` and `ZOTERO_LIBRARY_ID` are set (and nothing is listening locally). Works with Zotero closed. `ZOTERO_LIBRARY_TYPE=group` for a group library.
- **File mode** — no Zotero reachable, no key, or `--offline`. Writes `<collection>-for-zotero.bib` plus `HOW-TO-IMPORT.txt` to drag onto the collection.

Before creating anything it searches the library by DOI. A paper already in the library is **added to the target collection instead of duplicated**, which matters in a large library. It creates the collection if the name does not exist, then attaches any matching PDF from `--pdf-dir` as a child item.

Stage 3 writes to the user's library: run `--dry-run`, state the collection name and item count, and get a yes before the real import. Never import without being asked.

## Snowball

```bash
python scripts/paper_search.py snowball --id 10.1037/bul0000352 --direction both --limit 50
```

`--direction cites` = papers that cite it (newer work, follow-ups, critiques). `--direction refs` = its intellectual base (foundational work). Accepts a DOI, a doi.org URL, or an OpenAlex id (`W...`). Use `both` when building a reading list around one anchor paper.

## Notes

- OpenAlex: broadest coverage, includes abstracts, citation counts, open-access links.
- arXiv: preprints, no citation counts, not peer reviewed — label as preprint.
- PubMed: biomedical only; returns nothing useful for other fields.
- Crossref: metadata and DOIs; abstracts are frequently missing.
- The SSCI/SCIE allowlist (`journals.csv`) is a curated seed, not a licensed Web of Science dump. Treat `SSCI`/`SCIE` labels as "high confidence, verify if it matters", and check genuinely borderline venues against the current Master Journal List before a submission depends on it. Extend it freely with `journals --add`.
- Semantic Scholar (`--sources s2`): best citation graph and TLDR summaries, but unauthenticated calls are rate-limited hard and often return nothing. If the user wants it, ask them for a free API key from semanticscholar.org and set `S2_API_KEY`; do not silently retry without one. Not in the default source list for this reason.
- Results are cached for 7 days in `~/.cache/paper-search`; `--no-cache` forces fresh calls.
- Optional: set `PAPER_SEARCH_MAILTO=you@example.com` for OpenAlex's polite pool (faster, more reliable) and to enable Unpaywall PDF lookup.
- PDFs come from legitimate open-access sources only. Coverage is partial: expect roughly half to download, fewer in the humanities.
- Zotero: the local API is read-only until granted; `--authorize` shows a permission dialog and caches the key. Web API keys come from zotero.org/settings/keys. The `.bib` fallback needs neither and always works.

Run `python scripts/paper_search.py search --help` for the full flag list.
