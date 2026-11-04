#!/usr/bin/env python3
"""paper-search: multi-source academic literature search.

Zero third-party dependencies (stdlib only). Designed to be driven by an agent:
it returns structured JSON with titles + abstracts so the caller can make the
final relevance judgment.

Usage examples:
  python paper_search.py search --query "growth mindset intervention achievement"
  python paper_search.py search --query "a" --query "b" --year-from 2015 --oa-only --save out/
  python paper_search.py snowball --id 10.1037/a0030133 --direction both
"""

import argparse
import difflib
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

VERSION = "1.0"
CACHE_TTL_DAYS = 7
UA_FMT = "paper-search/%s (academic literature review)"

STOP = set(
    """a an the of for and or in on to with by from at as is are was were be been
    this that these those using use used toward towards into about via study studies
    research effect effects role impact new between among its their our""".split()
)

DEFAULT_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "paper-search")


# --------------------------------------------------------------------------
# plumbing
# --------------------------------------------------------------------------

def eprint(*a):
    print(*a, file=sys.stderr)


VERBOSE = False


def log(*a):
    if VERBOSE:
        eprint(*a)


def http_get(url, timeout=30, retries=3, cache_dir=None, extra_headers=None):
    """GET with on-disk cache and backoff. Returns bytes."""
    key = None
    if cache_dir:
        key = os.path.join(cache_dir, hashlib.sha1(url.encode()).hexdigest() + ".cache")
        try:
            if os.path.getmtime(key) > time.time() - CACHE_TTL_DAYS * 86400:
                with open(key, "rb") as f:
                    return f.read()
        except OSError:
            pass

    mailto = os.environ.get("PAPER_SEARCH_MAILTO", "")
    headers = {
        "User-Agent": UA_FMT % VERSION + (f" mailto:{mailto}" if mailto else ""),
        "Accept": "application/json, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    }
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    last = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read()
            if cache_dir and body:
                os.makedirs(cache_dir, exist_ok=True)
                try:
                    with open(key, "wb") as f:
                        f.write(body)
                except OSError:
                    pass
            return body
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as e:  # timeouts, DNS, connection reset
            last = e
            time.sleep(1.5 * (attempt + 1))
    raise last


def get_json(url, cache_dir, timeout=30):
    return json.loads(http_get(url, timeout=timeout, cache_dir=cache_dir).decode("utf-8", "replace"))


# --------------------------------------------------------------------------
# normalisation / merging
# --------------------------------------------------------------------------

def norm_title(t):
    if not t:
        return ""
    t = unicodedata.normalize("NFKD", t).lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def norm_doi(d):
    if not d:
        return ""
    d = str(d).strip().lower()
    d = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", d)
    return d.strip(" .;")


def clean_text(s):
    """Strip JATS/HTML tags and collapse whitespace."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", str(s))
    s = (s.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
          .replace("&quot;", '"').replace("&#x2019;", "'"))
    return re.sub(r"\s+", " ", s).strip()


def clean_venue(v):
    """OpenAlex sometimes returns 'Journal Name/Journal Name' duplicates."""
    v = clean_text(v)
    if "/" not in v:
        return v
    parts = [p.strip() for p in v.split("/") if p.strip()]
    if len(parts) < 2:
        return v
    a, b = parts[0].lower(), parts[-1].lower()
    if difflib.SequenceMatcher(None, a, b).ratio() > 0.8:
        return min(parts, key=len)
    return v


def new_record(**kw):
    r = {
        "title": "", "year": None, "authors": [], "venue": "", "doi": "",
        "url": "", "abstract": "", "citations": 0, "type": "", "oa_url": "",
        "pdf_url": "", "sources": [], "openalex_id": "",
        "issn": [], "publisher": "", "institutions": [], "author_ids": [],
        "quality": None,
    }
    r.update({k: v for k, v in kw.items() if v is not None})
    return r


def _merge(a, b):
    if len(b.get("abstract") or "") > len(a.get("abstract") or ""):
        a["abstract"] = b["abstract"]
    if len(b.get("authors") or []) > len(a.get("authors") or []):
        a["authors"] = b["authors"]
    for f in ("venue", "doi", "url", "oa_url", "pdf_url", "type", "year", "openalex_id"):
        if not a.get(f) and b.get(f):
            a[f] = b[f]
    a["citations"] = max(a.get("citations") or 0, b.get("citations") or 0)
    for f in ("issn", "institutions", "author_ids"):
        a[f] = list(dict.fromkeys((a.get(f) or []) + (b.get(f) or [])))
    if b.get("publisher") and not a.get("publisher"):
        a["publisher"] = b["publisher"]
    for s in b.get("sources") or []:
        if s not in a["sources"]:
            a["sources"].append(s)
    # re-key under any new identifiers
    for k in b.get("_keys", []):
        if k not in a.get("_keys", []):
            a.setdefault("_keys", []).append(k)


def add_all(records, store, idx):
    for rec in records:
        doi = norm_doi(rec.get("doi"))
        tkey = norm_title(rec.get("title"))
        if len(tkey) < 12:
            tkey = ""
        hit = None
        if doi and ("doi", doi) in idx:
            hit = idx[("doi", doi)][0]
        elif tkey and ("title", tkey) in idx:
            hit = idx[("title", tkey)][0]
        if hit:
            _merge(hit, rec)
            for k in rec.get("_keys", []):
                if k not in hit.setdefault("_keys", []):
                    hit["_keys"].append(k)
                    idx.setdefault(k, []).append(hit)
            continue
        rec["_keys"] = [k for k in (("doi", doi), ("title", tkey)) if k[1]]
        store.append(rec)
        for k in rec["_keys"]:
            idx.setdefault(k, []).append(rec)


# --------------------------------------------------------------------------
# sources
# --------------------------------------------------------------------------

def search_openalex(query, limit, yfrom, yto, cache_dir):
    params = {
        "search": query,
        "per-page": str(max(1, min(limit, 200))),
        "select": ("id,doi,title,publication_year,publication_date,cited_by_count,"
                   "primary_location,authorships,abstract_inverted_index,type,"
                   "open_access,referenced_works,best_oa_location"),
        "filter": "is_retracted:false",
    }
    flt = [params["filter"]]
    if yfrom:
        flt.append(f"from_publication_date:{yfrom}-01-01")
    if yto:
        flt.append(f"to_publication_date:{yto}-12-31")
    params["filter"] = ",".join(flt)
    mt = os.environ.get("PAPER_SEARCH_MAILTO")
    if mt:
        params["mailto"] = mt

    url = "https://api.openalex.org/works?" + urllib.parse.urlencode(params)
    data = get_json(url, cache_dir)
    out = []
    for w in data.get("results", []):
        inv = w.get("abstract_inverted_index")
        abstract = ""
        if inv:
            pos = []
            for word, places in inv.items():
                for p in places:
                    pos.append((p, word))
            pos.sort()
            abstract = " ".join(wd for _, wd in pos)
        loc = w.get("primary_location") or {}
        src = (loc.get("source") or {}) if isinstance(loc, dict) else {}
        best = w.get("best_oa_location") or {}
        issns = list(dict.fromkeys([str(x) for x in (src.get("issn") or [])] + ([src["issn_l"]] if src.get("issn_l") else [])))
        insts, aids = [], []
        for au in w.get("authorships", []):
            for inst in au.get("institutions") or []:
                nm = (inst.get("display_name") or "").strip()
                if nm and nm not in insts:
                    insts.append(nm)
            aid = (au.get("author") or {}).get("id") or ""
            if aid:
                aids.append(aid.rsplit("/", 1)[-1])
        out.append(new_record(
            title=clean_text(w.get("title") or w.get("display_name")),
            year=w.get("publication_year"),
            authors=[(a.get("author") or {}).get("display_name", "") for a in w.get("authorships", [])][:12],
            venue=clean_venue(src.get("display_name")),
            doi=norm_doi(w.get("doi")),
            url=w.get("doi") or w.get("id") or "",
            abstract=clean_text(abstract),
            citations=w.get("cited_by_count") or 0,
            type=w.get("type") or "",
            oa_url=(w.get("open_access") or {}).get("oa_url") or "",
            pdf_url=(best.get("pdf_url") if isinstance(best, dict) else "") or "",
            issn=issns, publisher=clean_text(src.get("host_organization_name") or ""),
            institutions=insts, author_ids=aids,
            sources=["openalex"],
            openalex_id=(w.get("id") or "").rsplit("/", 1)[-1],
        ))
    return out


ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"


def search_arxiv(query, limit, yfrom, yto, cache_dir):
    q = f"all:{query}"
    url = ("https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
        {"search_query": q, "start": 0, "max_results": min(limit, 100),
         "sortBy": "relevance", "sortOrder": "descending"}))
    body = http_get(url, cache_dir=cache_dir)
    root = ET.fromstring(body)
    out = []
    for e in root.findall(f"{ATOM}entry"):
        published = (e.findtext(f"{ATOM}published") or "")
        year = int(published[:4]) if published[:4].isdigit() else None
        if yfrom and year and year < yfrom:
            continue
        if yto and year and year > yto:
            continue
        link = e.findtext(f"{ATOM}id") or ""
        doi = (e.findtext(f"{ARXIV}doi") or "").strip()
        out.append(new_record(
            title=clean_text(e.findtext(f"{ATOM}title")),
            year=year,
            authors=[a.findtext(f"{ATOM}name") for a in e.findall(f"{ATOM}author")][:12],
            venue=clean_text(e.findtext(f"{ARXIV}journal_ref") or "arXiv preprint"),
            doi=norm_doi(doi),
            url=link,
            abstract=clean_text(e.findtext(f"{ATOM}summary")),
            citations=0,
            type="preprint",
            oa_url=link.replace("/abs/", "/pdf/"),
            sources=["arxiv"],
        ))
    return out


def search_pubmed(query, limit, yfrom, yto, cache_dir):
    term = query
    if yfrom or yto:
        term += f' AND ("{yfrom or 1900}"[PDAT] : "{yto or 2100}"[PDAT])'
    ids_url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "term": term, "retmax": min(limit, 100), "retmode": "json", "sort": "relevance"}))
    ids = get_json(ids_url, cache_dir).get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    fetch_url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?" + urllib.parse.urlencode(
        {"db": "pubmed", "id": ",".join(ids), "retmode": "xml"}))
    root = ET.fromstring(http_get(fetch_url, cache_dir=cache_dir))
    out = []
    for art in root.findall(".//PubmedArticle"):
        title = clean_text("".join(art.find(".//ArticleTitle").itertext())) if art.find(".//ArticleTitle") is not None else ""
        abst = " ".join(
            clean_text("".join(a.itertext())) for a in art.findall(".//Abstract/AbstractText")
        )
        journal = art.findtext(".//Journal/Title") or ""
        year = None
        y = art.findtext(".//JournalIssue/PubDate/Year")
        if y and y.isdigit():
            year = int(y)
        else:
            md = art.findtext(".//JournalIssue/PubDate/MedlineDate") or ""
            m = re.search(r"(1[89]|20)\d{2}", md)
            if m:
                year = int(m.group(0))
        doi = ""
        for aid in art.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = (aid.text or "").strip()
        authors = []
        for a in art.findall(".//AuthorList/Author"):
            ln, fn = a.findtext("LastName") or "", a.findtext("ForeName") or ""
            if ln:
                authors.append(f"{fn} {ln}".strip())
        pmid = art.findtext(".//PMID") or ""
        out.append(new_record(
            title=title, year=year, authors=authors[:12], venue=journal,
            doi=norm_doi(doi), url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            abstract=abst, citations=0, type="article", sources=["pubmed"],
        ))
    return out


def search_crossref(query, limit, yfrom, yto, cache_dir):
    params = {
        "query": query, "rows": str(min(limit, 100)),
        "select": "DOI,title,author,issued,container-title,abstract,is-referenced-by-count,URL,type",
        "filter": "type:journal-article",
    }
    if yfrom:
        params["filter"] += f",from-pub-date:{yfrom}-01-01"
    if yto:
        params["filter"] += f",until-pub-date:{yto}-12-31"
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    out = []
    for it in get_json(url, cache_dir).get("message", {}).get("items", []):
        title = clean_text((it.get("title") or [""])[0])
        issued = (it.get("issued") or {}).get("date-parts") or [[None]]
        year = issued[0][0] if issued and issued[0] else None
        authors = []
        for a in it.get("author") or []:
            nm = " ".join(x for x in [a.get("given"), a.get("family")] if x)
            if nm:
                authors.append(nm)
        out.append(new_record(
            title=title, year=year, authors=authors[:12],
            venue=clean_text((it.get("container-title") or [""])[0]),
            doi=norm_doi(it.get("DOI")), url=it.get("URL") or "",
            abstract=clean_text(it.get("abstract")),
            citations=it.get("is-referenced-by-count") or 0,
            type=it.get("type") or "", sources=["crossref"],
        ))
    return out


S2_FIELDS = ("title,abstract,year,venue,citationCount,authors,externalIds,"
             "openAccessPdf,publicationTypes,url,publicationDate")


def search_semanticscholar(query, limit, yfrom, yto, cache_dir):
    """Optional: set S2_API_KEY for reliable access. Without it, 429s are common."""
    apikey = os.environ.get("S2_API_KEY", "").strip()
    params = {
        "query": query,
        "limit": str(max(1, min(limit, 100))),
        "fields": S2_FIELDS,
    }
    if yfrom and yto:
        params["year"] = f"{yfrom}-{yto}"
    elif yfrom:
        params["year"] = f"{yfrom}-"
    elif yto:
        params["year"] = f"-{yto}"

    url = "https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)
    headers = {"x-api-key": apikey} if apikey else {}
    try:
        body = http_get(url, cache_dir=cache_dir, extra_headers=headers,
                        retries=2 if apikey else 1, timeout=25)
    except urllib.error.HTTPError as e:
        if e.code == 429 and not apikey:
            log("[s2] rate limited (set S2_API_KEY to fix); skipping")
            return []
        raise

    out = []
    for p in json.loads(body.decode("utf-8", "replace")).get("data", []):
        year = p.get("year")
        if yfrom and year and year < yfrom:
            continue
        if yto and year and year > yto:
            continue
        ext = p.get("externalIds") or {}
        doi = norm_doi(ext.get("DOI"))
        types = p.get("publicationTypes") or []
        out.append(new_record(
            title=clean_text(p.get("title")),
            year=year,
            authors=[a.get("name", "") for a in (p.get("authors") or [])][:12],
            venue=clean_venue(p.get("venue")),
            doi=doi,
            url=p.get("url") or (f"https://doi.org/{doi}" if doi else ""),
            abstract=clean_text(p.get("abstract")),
            citations=p.get("citationCount") or 0,
            type=types[0] if types else "",
            oa_url=(p.get("openAccessPdf") or {}).get("url") or "",
            sources=["semanticscholar"],
        ))
    return out


SOURCES = {
    "openalex": search_openalex,
    "arxiv": search_arxiv,
    "pubmed": search_pubmed,
    "crossref": search_crossref,
    "s2": search_semanticscholar,
    "semanticscholar": search_semanticscholar,
}


# --------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------

def toks(s):
    return {w for w in re.findall(r"[a-z]{3,}", (s or "").lower()) if w not in STOP}


def score(rec, qset, now_year):
    tt = toks(rec.get("title"))
    at = toks(rec.get("abstract")) | tt
    tcos = len(tt & qset) / math.sqrt(len(tt) * len(qset)) if tt and qset else 0.0
    acos = len(at & qset) / math.sqrt(len(at) * len(qset)) if at and qset else 0.0
    cites = rec.get("citations") or 0
    yr = rec.get("year") or now_year
    rec_bonus = max(0.0, 1.0 - (now_year - yr) / 25.0)
    s = 4.0 * tcos + 1.5 * acos + 0.6 * math.log1p(cites) + 0.8 * rec_bonus
    if not rec.get("abstract"):
        s -= 0.35  # abstracts are what let the agent judge
    return round(s, 3)


# --------------------------------------------------------------------------
# output
# --------------------------------------------------------------------------

def slug(s, n=40):
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s[:n] or "query"


def fmt_brief(records, top):
    lines = [f"{'#':>3}  {'YEAR':<5} {'CITES':>6}  TITLE"]
    for i, r in enumerate(records[:top], 1):
        t = (r.get("title") or "")[:82]
        tag = tier_tag(r.get("quality"))
        tag = f" [{tag}]" if tag else ""
        lines.append(f"{i:>3}  {str(r.get('year') or ''):<5} {r.get('citations') or 0:>6}  {t}{tag}")
        if r.get("venue"):
            lines.append(f"       {r['venue'][:80]}")
        if r.get("doi"):
            lines.append(f"       https://doi.org/{r['doi']}")
    return "\n".join(lines)


def fmt_md(records, query):
    out = [f"# Literature search: {query}", ""]
    out.append(f"_{len(records)} unique records, generated {datetime.now():%Y-%m-%d %H:%M}_")
    out.append("")
    out.append("| # | Year | Quality | Title | Venue | Cites | Link |")
    out.append("|---|------|---------|-------|-------|-------|------|")
    for i, r in enumerate(records, 1):
        title = (r.get("title") or "").replace("|", "\\|")
        venue = (r.get("venue") or "").replace("|", "\\|")[:60]
        link = f"https://doi.org/{r['doi']}" if r.get("doi") else (r.get("url") or "")
        q = r.get("quality") or {}
        qlab = tier_tag(q) + (f" ({q.get('reason','')})" if q.get("reason") else "")
        out.append(f"| {i} | {r.get('year') or ''} | {qlab} | {title} | {venue} | {r.get('citations') or 0} | {link} |")
    return "\n".join(out)


def fmt_bibtex(records, avoid=None):
    used = set(avoid or ())
    chunks = []
    for r in records:
        if not r.get("title"):
            continue
        fam = ""
        if r.get("authors"):
            fam = r["authors"][0].split()[-1]
        fam = re.sub(r"[^A-Za-z]", "", unicodedata.normalize("NFKD", fam)).lower() or "anon"
        word = next((w for w in re.findall(r"[A-Za-z]{3,}", r["title"])
                     if w.lower() not in STOP), "paper")
        base = f"{fam}{r.get('year') or ''}{word.lower()}"
        key, i = base, 0
        while key in used:
            i += 1
            key = base + chr(96 + i)
        used.add(key)
        kind = "article" if r.get("venue") else "misc"
        fields = {
            "title": r["title"],
            "author": " and ".join(r.get("authors") or []),
            "year": r.get("year"),
            "journal": r.get("venue") if kind == "article" else None,
            "doi": r.get("doi"),
            "url": r.get("url") if kind != "article" else None,
        }
        body = ",\n".join(f"  {k} = {{{v}}}" for k, v in fields.items() if v)
        chunks.append(f"@{kind}{{{key},\n{body}\n}}")
    return "\n\n".join(chunks)


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def parse_existing_bib(path):
    """Return (dois, titles, citekeys) already present in a .bib file."""
    dois, titles, keys = set(), set(), set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            txt = f.read()
    except OSError:
        return dois, titles, keys
    for block in re.split(r"\n(?=@)", txt):
        m = re.match(r"\s*@\w+\s*\{\s*([^,\s]+)", block)
        if m:
            keys.add(m.group(1))
        m = re.search(r"doi\s*=\s*\{(.+?)\}", block, re.I | re.S)
        if m:
            dois.add(norm_doi(m.group(1)))
        m = re.search(r"title\s*=\s*\{(.+?)\}\s*,", block, re.I | re.S)
        if m:
            titles.add(norm_title(clean_text(m.group(1))))
    return dois, titles, keys


def write_bib(path, records):
    """Append records to a .bib file, skipping DOIs/titles already there."""
    exists = os.path.exists(path) and os.path.getsize(path) > 0
    dois, titles, keys = parse_existing_bib(path) if exists else (set(), set(), set())

    new = []
    for r in records:
        if not r.get("title"):
            continue
        d, t = norm_doi(r.get("doi")), norm_title(r.get("title"))
        if (d and d in dois) or (t and t in titles):
            continue
        new.append(r)
        if d:
            dois.add(d)
        if t:
            titles.add(t)
    if not new:
        return 0

    body = fmt_bibtex(new, avoid=keys)
    with open(path, "a", encoding="utf-8") as f:
        if not exists:
            f.write("% Generated by paper-search\n\n")
        else:
            f.write("\n\n")
        f.write(body + "\n")
    return len(new)


def maybe_write_bib(a, records):
    """Resolve --bib (dir or .bib path), append, return a status line."""
    if not getattr(a, "bib", None) or not records:
        return None
    target = a.bib
    if not target.lower().endswith(".bib"):
        os.makedirs(target, exist_ok=True)
        target = os.path.join(target, f"paper-search-{datetime.now():%Y%m%d}.bib")
    added = write_bib(target, records)
    if added == 0:
        return f"BibTeX: no new entries (all already in {target})"
    return f"BibTeX: {added} new entries -> {target}"


# --------------------------------------------------------------------------
# quality gate (SSCI/SCIE allowlist + preprint reputation checks)
# --------------------------------------------------------------------------

JOURNALS_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "journals.csv")
HINDEX_BAR = 20

TOP_INSTITUTIONS = [
    "harvard", "stanford", "massachusetts institute of technology", "mit ",
    "princeton", "yale", "columbia university", "university of pennsylvania",
    "cornell", "johns hopkins", "northwestern", "carnegie mellon",
    "university of chicago", "california institute of technology", "caltech",
    "duke university", "new york university", "university of california, berkeley",
    "university of california, los angeles", "university of california, san diego",
    "university of michigan", "university of texas", "university of wisconsin",
    "university of minnesota", "university of illinois", "purdue",
    "georgia institute of technology", "university of washington", "boston university",
    "university of toronto", "university of british columbia", "mcgill",
    "university of waterloo", "oxford", "cambridge", "imperial college",
    "university college london", "london school of economics", "eth ",
    "university of amsterdam", "katholieke universiteit leuven",
    "university of copenhagen", "max planck", "sorbonne",
    "paris sciences et lettres", "tsinghua", "peking university", "fudan",
    "shanghai jiao tong", "zhejiang university", "nanjing university",
    "sun yat-sen", "university of hong kong", "chinese university of hong kong",
    "hong kong university of science and technology", "city university of hong kong",
    "hong kong polytechnic", "national university of singapore",
    "nanyang technological", "singapore management university", "university of tokyo",
    "kyoto university", "seoul national university", "kaist",
    "university of melbourne", "university of sydney",
    "university of new south wales", "monash", "university of queensland",
    "indian institute of technology", "university of st. gallen", "humboldt",
    "ludwig-maximilians", "technical university of munich", "hebrew university",
    "aarhus university", "university of aarhus", "universitat politecnica",
]

MEGA_COMPANIES = [
    "google", "microsoft", "meta ", "amazon", "apple", "ibm", "intel", "nvidia",
    "openai", "deepmind", "anthropic", "alibaba", "tencent", "bytedance", "baidu",
    "huawei", "samsung", "mckinsey", "boston consulting group", "bain ",
    "accenture", "netflix", "spotify", "uber", "airbnb", "salesforce", "oracle",
    "sap ", "jpmorgan", "goldman sachs",
]

REPUTABLE_PUBLISHERS = [
    "elsevier", "springer", "wiley", "taylor & francis", "taylor and francis",
    "sage ", "oxford university press", "cambridge university press",
    "american psychological", "informs", "institute for operations research",
    "academy of management", "american marketing association", "ieee",
    "association for computing machinery", "acm ", "emerald", "mdpi",
    "frontiers media", "plos ", "bmj ", "wolters kluwer", "de gruyter",
    "palgrave", "university of chicago press", "mit press", "duke university press",
    "guilford", "routledge",
]

_journals = None


def load_journals():
    global _journals
    if _journals is not None:
        return _journals
    _journals = {}
    order = {"FLAGSHIP": 3, "SSCI": 2, "SCIE": 2, "SSCI/SCIE": 2, "ESCI": 1}
    try:
        with open(JOURNALS_CSV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = [p.strip() for p in line.split(",")]
                if len(parts) < 2:
                    continue
                key = norm_title(parts[0])
                idx = parts[1].upper()
                if key and (key not in _journals or order.get(idx, 0) > order.get(_journals[key]["order"], 0)):
                    _journals[key] = {"title": parts[0], "index": idx, "order": order.get(idx, 0)}
    except OSError as e:
        log(f"[quality] cannot read {JOURNALS_CSV}: {e}")
    return _journals


def match_journal(venue):
    j = load_journals()
    v = norm_title(venue)
    if not v:
        return None
    if v in j:
        return j[v]
    best, ratio = None, 0.0
    for key, row in j.items():
        r = difflib.SequenceMatcher(None, v, key).ratio()
        if r > ratio:
            best, ratio = row, r
    return best if ratio >= 0.94 else None


def hit_affiliation(institutions):
    blob = " ".join((i or "").lower() for i in (institutions or [])[:10])
    if not blob:
        return None
    for name in TOP_INSTITUTIONS:
        if name in blob:
            return f"top-tier institution: {name.strip()}"
    for name in MEGA_COMPANIES:
        if name in blob:
            return f"major company: {name.strip()}"
    return None


def reputable_publisher(rec):
    p = (rec.get("publisher") or "").lower()
    if not p:
        return False
    return any(x in p for x in REPUTABLE_PUBLISHERS)


def is_preprint(rec):
    blob = ((rec.get("venue") or "") + " " + (rec.get("url") or "")).lower()
    if re.search(r"arxiv|ssrn|biorxiv|medrxiv|osf\.io|research square|working paper|preprint|repec|ideas/rep", blob):
        return True
    if (rec.get("type") or "").lower() in ("preprint", "posted-content"):
        return True
    return "arxiv" in (rec.get("sources") or [])


def assess_quality(rec):
    j = match_journal(rec.get("venue") or "")
    if j:
        return {"tier": "flagship" if j["index"] == "FLAGSHIP" else "indexed",
                "index": j["index"], "reason": j["title"]}
    if is_preprint(rec):
        aff = hit_affiliation(rec.get("institutions"))
        if aff:
            return {"tier": "preprint-ok", "index": "-", "reason": aff}
        return {"tier": "preprint", "index": "-",
                "reason": "preprint without a recognised affiliation"}
    if rec.get("issn") and reputable_publisher(rec):
        return {"tier": "unverified", "index": "?",
                "reason": f"{rec.get('publisher') or 'reputable publisher'}; not yet in the allowlist"}
    return {"tier": "low", "index": "-",
            "reason": "no ISSN or unrecognised venue"}


def enrich_author_hindex(records, cache_dir):
    """One batched call to check preprint co-author reputation (h-index)."""
    need = [r for r in records if r.get("quality") and r["quality"]["tier"] == "preprint"]
    if not need:
        return
    ids = list(dict.fromkeys(a for r in need for a in (r.get("author_ids") or [])))[:60]
    if not ids:
        return
    try:
        url = "https://api.openalex.org/authors?" + urllib.parse.urlencode({
            "filter": "id:" + "|".join(ids), "select": "id,summary_stats", "per-page": "100"})
        data = get_json(url, cache_dir)
        hmap = {res["id"].rsplit("/", 1)[-1]: (res.get("summary_stats") or {}).get("h_index") or 0
                for res in data.get("results", [])}
    except Exception as e:
        log(f"[quality] author enrichment failed: {type(e).__name__}: {e}")
        return
    for r in need:
        hs = [hmap.get(a, 0) for a in (r.get("author_ids") or [])]
        if hs and max(hs) >= HINDEX_BAR:
            r["quality"] = {"tier": "preprint-ok", "index": "-",
                            "reason": f"co-author h-index {max(hs)}"}


def apply_quality(records, mode, cache_dir=None):
    if mode == "off":
        for r in records:
            r["quality"] = r.get("quality") or {"tier": "all", "index": "-",
                                                "reason": "quality filter off"}
        return records
    for r in records:
        r["quality"] = assess_quality(r)
    enrich_author_hindex(records, cache_dir)
    keep = []
    for r in records:
        t = r["quality"]["tier"]
        if t in ("flagship", "indexed", "preprint-ok"):
            keep.append(r)
        elif t == "unverified" and mode == "balanced":
            keep.append(r)
    return keep


TIER_RANK = {"flagship": 5, "indexed": 4, "preprint-ok": 3, "unverified": 2,
             "preprint": 1, "low": 0, "all": 3}


def tier_tag(q):
    if not q:
        return ""
    t = q.get("tier")
    if t == "indexed":
        return q.get("index", "SSCI")
    if t == "flagship":
        return "FLAG"
    if t == "preprint-ok":
        return "PRE+"
    if t == "preprint":
        return "PRE"
    if t == "unverified":
        return "UNV"
    if t == "low":
        return "LOW"
    return ""


def cmd_search(a):
    queries = list(a.query or [])
    if a.queries_file:
        with open(a.queries_file, encoding="utf-8") as f:
            queries += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    if not queries:
        eprint("error: give at least one --query")
        return 2

    names = [s.strip() for s in a.sources.split(",") if s.strip()]
    bad = [n for n in names if n not in SOURCES]
    if bad:
        eprint(f"error: unknown source(s) {bad}; choose from {list(SOURCES)}")
        return 2

    store, idx, qset = [], {}, set()
    for q in queries:
        qset |= toks(q)
        for name in names:
            fn = SOURCES[name]
            try:
                recs = fn(q, a.limit, a.year_from, a.year_to, None if a.no_cache else a.cache_dir)
                add_all(recs, store, idx)
                log(f"[{name}] '{q[:60]}' -> {len(recs)}")
            except Exception as e:
                log(f"[{name}] '{q[:60]}' failed: {type(e).__name__}: {e}")
            time.sleep(0.25)

    now_year = datetime.now().year
    for r in store:
        if a.oa_only and not r.get("oa_url"):
            r["_drop"] = True
        if a.min_cites and (r.get("citations") or 0) < a.min_cites:
            r["_drop"] = True
        r["score"] = score(r, qset, now_year)

    store = [r for r in store if not r.get("_drop")]
    store = apply_quality(store, a.quality, a.cache_dir)
    store.sort(key=lambda r: (-TIER_RANK.get(r["quality"]["tier"], 0), -r["score"]))

    seen, unique = set(), []
    for r in store:
        k = norm_title(r.get("title"))
        if k in seen:
            continue
        seen.add(k)
        unique.append(r)
    store = unique[: a.max_results]

    if not store:
        if a.format == "json":
            print("[]")
        elif a.format in ("md", "bibtex"):
            pass
        else:
            print("No results. Broaden the queries, drop --year-from, "
                  "or try --sources openalex.")
        return 0

    if a.save:
        os.makedirs(a.save, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        base = os.path.join(a.save, f"{slug(queries[0])}-{stamp}")
        payload = {
            "meta": {"generated": datetime.now().isoformat(timespec="seconds"),
                     "queries": queries, "sources": names,
                     "year_from": a.year_from, "year_to": a.year_to,
                     "count": len(store)},
            "queries": queries,
            "results": [{k: v for k, v in r.items() if not k.startswith("_")} for r in store],
        }
        for ext, content in (
            (".json", json.dumps(payload, ensure_ascii=False, indent=2)),
            (".md", fmt_md(store, queries[0])),
            (".bib", fmt_bibtex(store)),
        ):
            with open(base + ext, "w", encoding="utf-8") as f:
                f.write(content)
        log(f"saved: {base}.json / .md / .bib")

    bib_msg = maybe_write_bib(a, store)
    if bib_msg:
        if a.format == "brief":
            print(bib_msg)
        else:
            log(bib_msg)

    if a.format == "json":
        print(json.dumps([{k: v for k, v in r.items() if not k.startswith("_")}
                          for r in store], ensure_ascii=False, indent=2))
    elif a.format == "md":
        print(fmt_md(store, queries[0]))
    elif a.format == "bibtex":
        print(fmt_bibtex(store))
    else:
        print(fmt_brief(store, a.top))
    return 0


def resolve_openalex_id(ref, cache_dir):
    """Accept an OpenAlex id (W123), a DOI, or a doi.org URL."""
    ref = ref.strip()
    if re.fullmatch(r"[Ww]\d+", ref):
        return ref.upper()
    doi = norm_doi(ref)
    if doi:
        w = get_json(f"https://api.openalex.org/works/https://doi.org/{doi}", cache_dir)
        return (w.get("id") or "").rsplit("/", 1)[-1]
    raise ValueError(f"cannot resolve {ref!r} to an OpenAlex work")


def cmd_snowball(a):
    wid = resolve_openalex_id(a.id, None if a.no_cache else a.cache_dir)
    store, idx = [], {}
    dirs = ["cites", "refs"] if a.direction == "both" else [a.direction]

    if "cites" in dirs:
        url = ("https://api.openalex.org/works?" + urllib.parse.urlencode(
            {"filter": f"cites:{wid}", "per-page": str(min(a.limit, 200)),
             "select": "id,doi,title,publication_year,cited_by_count,primary_location,"
                       "authorships,abstract_inverted_index,type,open_access"}))
        data = get_json(url, None if a.no_cache else a.cache_dir)
        recs = []
        for w in data.get("results", []):
            inv = w.get("abstract_inverted_index") or {}
            pos = sorted((p, wd) for wd, ps in inv.items() for p in ps)
            loc = w.get("primary_location") or {}
            recs.append(new_record(
                title=clean_text(w.get("title")), year=w.get("publication_year"),
                authors=[(x.get("author") or {}).get("display_name", "") for x in w.get("authorships", [])][:12],
                venue=clean_venue(((loc.get("source") or {}) or {}).get("display_name")),
                doi=norm_doi(w.get("doi")), url=w.get("doi") or w.get("id"),
                abstract=" ".join(wd for _, wd in pos), citations=w.get("cited_by_count") or 0,
                type=w.get("type") or "", sources=["openalex:cites"],
                openalex_id=(w.get("id") or "").rsplit("/", 1)[-1]))
        add_all(recs, store, idx)
        log(f"citing works: {len(recs)}")

    if "refs" in dirs:
        w = get_json(f"https://api.openalex.org/works/{wid}", None if a.no_cache else a.cache_dir)
        refs = (w.get("referenced_works") or [])[:50]
        if refs:
            ids = "|".join(r.rsplit("/", 1)[-1] for r in refs)
            url = ("https://api.openalex.org/works?" + urllib.parse.urlencode(
                {"filter": f"openalex_id:{ids}", "per-page": "50",
                 "select": "id,doi,title,publication_year,cited_by_count,primary_location,"
                           "authorships,abstract_inverted_index,type,open_access"}))
            data = get_json(url, None if a.no_cache else a.cache_dir)
            recs = []
            for x in data.get("results", []):
                inv = x.get("abstract_inverted_index") or {}
                pos = sorted((p, wd) for wd, ps in inv.items() for p in ps)
                loc = x.get("primary_location") or {}
                recs.append(new_record(
                    title=clean_text(x.get("title")), year=x.get("publication_year"),
                    authors=[(y.get("author") or {}).get("display_name", "") for y in x.get("authorships", [])][:12],
                    venue=clean_venue(((loc.get("source") or {}) or {}).get("display_name")),
                    doi=norm_doi(x.get("doi")), url=x.get("doi") or x.get("id"),
                    abstract=" ".join(wd for _, wd in pos), citations=x.get("cited_by_count") or 0,
                    type=x.get("type") or "", sources=["openalex:refs"],
                    openalex_id=(x.get("id") or "").rsplit("/", 1)[-1]))
            add_all(recs, store, idx)
            log(f"referenced works: {len(recs)}")

    store.sort(key=lambda r: -(r.get("citations") or 0))
    for r in store:
        r["score"] = score(r, toks(a.context or ""), datetime.now().year)
    store = apply_quality(store, a.quality, a.cache_dir)
    store.sort(key=lambda r: (-TIER_RANK.get(r["quality"]["tier"], 0), -r["score"]))

    if a.save and store:
        os.makedirs(a.save, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
        base = os.path.join(a.save, f"snowball-{slug(wid)}-{stamp}")
        with open(base + ".json", "w", encoding="utf-8") as f:
            json.dump([{k: v for k, v in r.items() if not k.startswith("_")} for r in store],
                      f, ensure_ascii=False, indent=2)
        log(f"saved: {base}.json")

    bib_msg = maybe_write_bib(a, store)
    if bib_msg:
        if a.format == "brief":
            print(bib_msg)
        else:
            log(bib_msg)

    if a.format == "json":
        print(json.dumps([{k: v for k, v in r.items() if not k.startswith("_")}
                          for r in store], ensure_ascii=False, indent=2))
    elif a.format == "bibtex":
        print(fmt_bibtex(store))
    else:
        print(fmt_brief(store, a.top))
    return 0


# --------------------------------------------------------------------------
# interactive picker
# --------------------------------------------------------------------------

def load_results(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("results", [])
    return data


def parse_selection(spec, n):
    """'1,3,5-7' -> 0-based indices. Empty/'all' -> everything."""
    spec = (spec or "").strip().lower()
    if spec in ("", "all", "*"):
        return list(range(n))
    out = set()
    for part in re.split(r"[,\s]+", spec):
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            if a.isdigit() and b.isdigit():
                out.update(range(max(1, int(a)), min(n, int(b)) + 1))
        elif part.isdigit():
            out.add(int(part))
    return sorted(i - 1 for i in out if 1 <= i <= n)


PICKER = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pick papers</title>
<style>
:root{--ink:#17181c;--mut:#6b7078;--line:#e3e5ea;--bg:#fbfbfc;--accent:#2f5fe0;--ok:#1a7f52;--warn:#b45309}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",sans-serif;padding-bottom:78px}
header{padding:22px 28px 14px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:0;z-index:5}
h1{margin:0 0 4px;font-size:19px;font-weight:650;letter-spacing:-.01em}
.meta{color:var(--mut);font-size:13px}
.bar{display:flex;gap:10px;flex-wrap:wrap;align-items:center;padding:14px 28px;border-bottom:1px solid var(--line);background:#fff;position:sticky;top:74px;z-index:4}
input[type=search],select{font:inherit;font-size:14px;padding:7px 10px;border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink)}
input[type=search]{flex:1 1 260px;min-width:180px}
button{font:inherit;font-size:13.5px;padding:7px 12px;border:1px solid var(--line);background:#fff;border-radius:7px;cursor:pointer;color:var(--ink)}
button:hover{border-color:#c9cdd6;background:#fafafb}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:hover{background:#274fc4}
label.chk{display:inline-flex;gap:7px;align-items:center;color:var(--mut);font-size:13.5px;user-select:none;cursor:pointer}
main{padding:8px 28px 30px;max-width:1080px}
.row{display:grid;grid-template-columns:26px 1fr;gap:12px;padding:15px 4px;border-bottom:1px solid var(--line)}
.row:hover{background:#fff}
.row input[type=checkbox]{width:17px;height:17px;margin-top:3px;accent-color:var(--accent);cursor:pointer}
.idx{color:var(--mut);font-variant-numeric:tabular-nums;font-size:12.5px}
.t{font-weight:600;font-size:15.2px;line-height:1.35;margin-bottom:3px}
.sub{color:var(--mut);font-size:13px}
.sub b{color:#3c4148;font-weight:550}
.badges{margin-top:6px;display:flex;gap:6px;flex-wrap:wrap}
.b{font-size:11px;letter-spacing:.02em;text-transform:uppercase;padding:2px 6px;border-radius:4px;border:1px solid var(--line);color:var(--mut)}
.b.oa{color:var(--ok);border-color:#bfe3d2;background:#f2faf6}
.b.no{color:var(--warn);border-color:#f0dcc2;background:#fdf8f1}
details{margin-top:7px}
summary{cursor:pointer;color:var(--accent);font-size:13px;list-style:none}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸ ";}
details[open] summary::before{content:"▾ ";}
.abs{margin-top:7px;color:#3c4148;font-size:13.6px;max-width:80ch;background:#fff;border-left:2px solid var(--line);padding:2px 0 2px 12px}
footer{position:fixed;bottom:0;left:0;right:0;background:#fff;border-top:1px solid var(--line);padding:13px 28px;display:flex;gap:12px;align-items:center;z-index:9}
.count{font-size:14px;font-weight:600}
.count span{color:var(--accent)}
.hint{color:var(--mut);font-size:12.5px;margin-left:auto}
.toast{position:fixed;bottom:84px;left:50%;transform:translateX(-50%);background:#17181c;color:#fff;padding:9px 16px;border-radius:8px;font-size:13px;opacity:0;transition:opacity .18s;pointer-events:none}
.toast.on{opacity:1}
.empty{color:var(--mut);padding:40px 0;text-align:center}
</style></head><body>
<header>
  <h1>Pick papers to download</h1>
  <div class="meta" id="meta"></div>
</header>
<div class="bar">
  <input type="search" id="q" placeholder="Filter by title, author, venue, abstract…">
  <select id="year"><option value="0">Any year</option></select>
  <label class="chk"><input type="checkbox" id="oa"> Open access only</label>
  <label class="chk"><input type="checkbox" id="hq"> High quality only</label>
  <select id="sort">
    <option value="rank">Original ranking</option>
    <option value="year">Newest first</option>
    <option value="cites">Most cited</option>
  </select>
  <button id="all">Select all shown</button>
  <button id="none">Clear</button>
</div>
<main id="list"></main>
<footer>
  <div class="count"><span id="n">0</span> selected</div>
  <button class="primary" id="copy">Copy selection</button>
  <button id="dl">Download selection.json</button>
  <div class="hint">Then paste the copied list into the chat.</div>
</footer>
<div class="toast" id="toast"></div>
<script>
const DATA = __DATA__;
const KEY = "paper-search:" + DATA.meta.query_slug;
let sel = new Set(JSON.parse(localStorage.getItem(KEY) || "[]"));
const $ = s => document.querySelector(s);
const esc = s => (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

function oaOf(r){ return !!(r.pdf_url || (r.oa_url||"").match(/\.pdf($|\?)/i)); }
function save(){ localStorage.setItem(KEY, JSON.stringify([...sel])); renderCount(); }
function renderCount(){ $("#n").textContent = sel.size; }

function years(){
  const ys = [...new Set(DATA.results.map(r=>r.year).filter(Boolean))].sort((a,b)=>b-a);
  $("#year").insertAdjacentHTML("beforeend", ys.map(y=>`<option value="${y}">${y} and newer</option>`).join(""));
}

function view(){
  const q = $("#q").value.toLowerCase().trim();
  const minY = +$("#year").value;
  const oaOnly = $("#oa").checked;
  const hqOnly = $("#hq").checked;
  let rows = DATA.results.map((r,i)=>({r,i}));
  if (minY) rows = rows.filter(({r}) => (r.year||0) >= minY);
  if (oaOnly) rows = rows.filter(({r}) => oaOf(r));
  if (hqOnly) rows = rows.filter(({r}) => ["flagship","indexed","preprint-ok"].includes((r.quality||{}).tier));
  if (q) rows = rows.filter(({r}) => ((r.title||"")+" "+(r.authors||[]).join(" ")+" "+(r.venue||"")+" "+(r.abstract||"")).toLowerCase().includes(q));
  const s = $("#sort").value;
  if (s==="year") rows.sort((a,b)=>(b.r.year||0)-(a.r.year||0));
  if (s==="cites") rows.sort((a,b)=>(b.r.citations||0)-(a.r.citations||0));
  return rows;
}

function render(){
  const rows = view();
  if (!rows.length){ $("#list").innerHTML = '<div class="empty">Nothing matches these filters.</div>'; return; }
  $("#list").innerHTML = rows.map(({r,i})=>{
    const auth = (r.authors||[]).slice(0,3).join(", ") + ((r.authors||[]).length>3 ? " et al." : "");
    const q = r.quality || {};
    const qlab = q.tier==='indexed' ? (q.index||'SSCI') : q.tier==='flagship' ? 'FLAG'
      : q.tier==='preprint-ok' ? 'PRE+' : q.tier==='unverified' ? 'UNV'
      : q.tier==='preprint' ? 'PRE' : q.tier==='low' ? 'LOW' : '';
    const qbadge = qlab ? `<span class="b ${q.tier==='low'||q.tier==='preprint'?'no':''}">${qlab}</span>` : "";
    const badges = [
      oaOf(r) ? '<span class="b oa">open access</span>' : '<span class="b no">may be paywalled</span>',
      r.doi ? '<span class="b">doi</span>' : "",
      r.type ? `<span class="b">${esc(r.type)}</span>` : ""
    ].join("");
    return `<div class="row">
      <input type="checkbox" data-i="${i}" ${sel.has(i)?"checked":""}>
      <div>
        <div class="idx">#${i+1}${r.year?` · ${r.year}`:""}${r.citations?` · ${r.citations} citations`:""}</div>
        <div class="t">${esc(r.title||"(untitled)")}</div>
        <div class="sub">${esc(auth)}${r.venue?" · <b>"+esc(r.venue)+"</b>":""}</div>
        <div class="badges">${qbadge}${badges}</div>
        ${r.abstract?`<details><summary>abstract</summary><div class="abs">${esc(r.abstract)}</div></details>`:""}
      </div></div>`;
  }).join("");
  document.querySelectorAll("input[data-i]").forEach(cb=>{
    cb.onchange = () => { const i=+cb.dataset.i; cb.checked ? sel.add(i) : sel.delete(i); save(); };
  });
}

function toast(msg){ const t=$("#toast"); t.textContent=msg; t.classList.add("on"); setTimeout(()=>t.classList.remove("on"),1600); }

$("#q").oninput = render; $("#year").onchange = render; $("#oa").onchange = render;
$("#hq").onchange = render; $("#sort").onchange = render;
$("#all").onclick = () => { view().forEach(({i})=>sel.add(i)); save(); render(); };
$("#none").onclick = () => { sel.clear(); save(); render(); };
$("#copy").onclick = async () => {
  const list = [...sel].sort((a,b)=>a-b).map(i=>i+1).join(",");
  if (!list) return toast("Nothing selected");
  try { await navigator.clipboard.writeText(list); toast("Copied: " + list); }
  catch { prompt("Copy this list:", list); }
};
$("#dl").onclick = () => {
  const picked = [...sel].sort((a,b)=>a-b).map(i=>DATA.results[i]);
  const blob = new Blob([JSON.stringify({indices:[...sel].sort((a,b)=>a-b), results:picked}, null, 2)], {type:"application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = "selection.json"; a.click();
  toast("selection.json downloaded");
};

$("#meta").textContent = `${DATA.results.length} records · ${DATA.meta.sources || ""} · ${DATA.meta.queries ? DATA.meta.queries[0] : ""}`;
years(); render(); renderCount();
</script></body></html>
"""


def cmd_pick(a):
    data = json.load(open(a.from_json, encoding="utf-8"))
    results = data.get("results", data if isinstance(data, list) else [])
    meta = data.get("meta", {}) if isinstance(data, dict) else {}
    meta["query_slug"] = slug((meta.get("queries") or ["results"])[0])
    if "queries" not in meta:
        meta["queries"] = [os.path.basename(a.from_json)]
    payload = {"meta": meta, "results": results}
    html = PICKER.replace("__DATA__", json.dumps(payload, ensure_ascii=False))

    out = a.out or os.path.splitext(a.from_json)[0] + ".pick.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Picker written: {out}")
    print(f"{len(results)} records. Open it, tick papers, press 'Copy selection', paste the list here.")
    if a.open:
        try:
            os.startfile(out)  # Windows
        except AttributeError:
            import subprocess
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", out])
    return 0


# --------------------------------------------------------------------------
# PDF retrieval
# --------------------------------------------------------------------------

def safe_name(rec):
    fam = "anon"
    if rec.get("authors"):
        fam = rec["authors"][0].split()[-1]
    fam = re.sub(r"[^A-Za-z0-9]", "", fam) or "anon"
    year = rec.get("year") or "nd"
    title = re.sub(r"[^A-Za-z0-9 ]+", "", rec.get("title") or "")[:70].strip()
    title = re.sub(r"\s+", "-", title)
    return f"{fam}-{year}-{title or 'untitled'}.pdf"


def pdf_candidates(rec):
    """Ordered list of URLs likely to serve a PDF."""
    cands = []

    def add(u):
        if u and u not in cands:
            cands.append(u)

    add(rec.get("pdf_url"))
    oa = rec.get("oa_url") or ""
    if re.search(r"\.pdf($|[?#])", oa, re.I):
        add(oa)

    m = re.search(r"arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}|[a-z\-]+/\d+)", rec.get("url") or "", re.I)
    if m:
        add(f"https://arxiv.org/pdf/{m.group(1)}")

    doi = norm_doi(rec.get("doi"))
    email = os.environ.get("PAPER_SEARCH_MAILTO", "")
    if doi and email:
        try:
            u = get_json(f"https://api.unpaywall.org/v2/{urllib.parse.quote(doi)}?email={urllib.parse.quote(email)}", None)
            for loc in [u.get("best_oa_location")] + (u.get("oa_locations") or []):
                if loc:
                    add(loc.get("url_for_pdf"))
        except Exception as e:
            log(f"[unpaywall] {doi}: {type(e).__name__}")

    return cands


def scraper_pdf_url(doi):
    """Publisher landing pages often expose <meta name='citation_pdf_url'>."""
    try:
        html = http_get(f"https://doi.org/{doi}", timeout=20, retries=1).decode("utf-8", "replace")
    except Exception:
        return None
    m = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)', html, re.I)
    if m:
        return m.group(1)
    m = re.search(r'content=["\']([^"\']+)["\'][^>]+name=["\']citation_pdf_url["\']', html, re.I)
    return m.group(1) if m else None


class RedirectTo(Exception):
    def __init__(self, url):
        super().__init__(url)
        self.url = url


def download_pdf(url, dest, timeout=90):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA_FMT % VERSION, "Accept": "application/pdf,*/*"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
    if not data.startswith(b"%PDF"):
        if len(data) < 600000:
            html = data.decode("utf-8", "replace")
            m = re.search(r'<meta[^>]+http-equiv=["\']refresh["\'][^>]+'
                          r'content=["\'][^"\']*url=([^"\'>]+)', html, re.I)
            if not m:
                m = re.search(r'(?:window|document)\.location(?:\.href)?\s*=\s*["\']([^"\']+)', html)
            if not m:
                m = re.search(r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+'
                              r'content=["\']([^"\']+)', html, re.I)
            if m:
                raise RedirectTo(urllib.parse.urljoin(url, m.group(1)))
        raise ValueError("not a PDF")
    if len(data) < 20000:
        raise ValueError(f"suspiciously small ({len(data)} B)")
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "wb") as f:
        f.write(data)
    return len(data)


def cmd_fetch(a):
    results = load_results(a.from_json)
    picks = parse_selection(a.select, len(results))
    if not picks:
        print("Nothing selected.")
        return 0
    os.makedirs(a.out, exist_ok=True)

    manifest = []
    rows = []
    for i in picks:
        rec = results[i]
        dest = os.path.join(a.out, safe_name(rec))
        status, note = "no-oa", ""
        if os.path.exists(dest) and os.path.getsize(dest) > 20000:
            status, note = "exists", f"{os.path.getsize(dest)//1024} KB"
        elif a.dry_run:
            urls = pdf_candidates(rec) or (["(guess from DOI)"] if rec.get("doi") else [])
            status, note = "would-try", urls[0][:70]
        else:
            tried, seen = [], set()
            queue = list(pdf_candidates(rec))
            if rec.get("doi"):
                u = scraper_pdf_url(norm_doi(rec["doi"]))
                if u and u not in queue:
                    queue.append(u)
            status = "failed" if queue else "no-oa"
            note = "no open-access copy found"
            while queue and len(tried) < 6:
                u = queue.pop(0)
                if u in seen:
                    continue
                seen.add(u)
                tried.append(u)
                try:
                    size = download_pdf(u, dest)
                    status, note = "downloaded", f"{size//1024} KB"
                    break
                except RedirectTo as e:
                    if e.url not in seen:
                        queue.insert(0, e.url)
                    note = "followed redirect"
                except Exception as e:
                    note = f"{type(e).__name__}"
                    log(f"[fetch] {u[:80]} -> {type(e).__name__}: {e}")
            if status == "failed":
                note = f"{len(tried)} url(s) tried"
        manifest.append({
            "index": i + 1, "doi": rec.get("doi"), "title": rec.get("title"),
            "status": status, "file": dest if status in ("downloaded", "exists") else None,
            "note": note,
        })
        if a.format == "json":
            continue
        mark = {"downloaded": "OK  ", "exists": "have", "no-oa": "--  ",
                "failed": "!!  ", "would-try": "?   "}[status]
        rows.append(f"{mark} #{i+1:<3} {status:<10} {(rec.get('title') or '')[:70]}")

    with open(os.path.join(a.out, "fetch-manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    if a.format == "json":
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print("\n".join(rows))
        got = sum(1 for m in manifest if m["status"] in ("downloaded", "exists"))
        print(f"\n{got}/{len(manifest)} available in {os.path.abspath(a.out)}")
        missing = [m for m in manifest if m["status"] in ("no-oa", "failed")]
        if missing:
            print("No open-access copy: " + ", ".join(f"#{m['index']}" for m in missing))
    return 0


# --------------------------------------------------------------------------
# Zotero
# --------------------------------------------------------------------------

LOCAL_BASE = "http://localhost:23119/api/users/0"
ZOT_CACHE = os.path.join(DEFAULT_CACHE, "zotero-local.json")


def zot_probe_local(timeout=3):
    """Return (server_id, zotero_version) if the local API is reachable."""
    try:
        req = urllib.request.Request(LOCAL_BASE + "/items?limit=1",
                                     headers={"Zotero-API-Version": "3"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.headers.get("Zotero-Server-ID"), r.headers.get("X-Zotero-Version")
    except Exception:
        return None, None


def zot_local_key(server_id):
    try:
        with open(ZOT_CACHE, encoding="utf-8") as f:
            d = json.load(f)
        if d.get("server_id") == server_id and d.get("key"):
            return d["key"]
    except Exception:
        pass
    return os.environ.get("ZOTERO_LOCAL_KEY") or None


def zot_save_key(server_id, key):
    os.makedirs(os.path.dirname(ZOT_CACHE), exist_ok=True)
    with open(ZOT_CACHE, "w", encoding="utf-8") as f:
        json.dump({"server_id": server_id, "key": key}, f)
    try:
        os.chmod(ZOT_CACHE, 0o600)
    except OSError:
        pass


def zot_authorize(server_id):
    """Ask Zotero for a local API key. Shows a permission dialog to the user."""
    body = json.dumps({"appName": "paper-search",
                       "keyName": "paper-search import"}).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:23119/api/local/authorize", data=body, method="POST",
        headers={"Zotero-API-Version": "3", "Zotero-Server-ID": server_id,
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("key")


def zot_config(authorize=False):
    """Local API first, web API second. Returns a dict or None."""
    web_key = os.environ.get("ZOTERO_API_KEY", "").strip()
    web_lib = os.environ.get("ZOTERO_LIBRARY_ID", "").strip()
    if web_key and web_lib:
        typ = os.environ.get("ZOTERO_LIBRARY_TYPE", "user").strip().lower()
        prefix = "groups" if typ.startswith("group") else "users"
        return {"base": f"https://api.zotero.org/{prefix}/{web_lib}", "key": web_key,
                "server_id": None, "mode": "web", "version": None}

    sid, ver = zot_probe_local()
    if not sid:
        return None
    key = zot_local_key(sid)
    if not key and authorize:
        key = zot_authorize(sid)
        if key:
            zot_save_key(sid, key)
    return {"base": LOCAL_BASE, "key": key, "server_id": sid,
            "mode": "local", "version": ver}


def zot_request(cfg, method, path, payload=None, raw=None, ctype=None, extra=None):
    headers = {"Zotero-API-Version": "3"}
    if cfg.get("server_id"):
        headers["Zotero-Server-ID"] = cfg["server_id"]
    if cfg.get("key"):
        headers["Zotero-API-Key"] = cfg["key"]
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    elif raw is not None:
        data = raw
        headers["Content-Type"] = ctype or "application/octet-stream"
        headers["If-None-Match"] = "*"
    if extra:
        headers.update(extra)
    req = urllib.request.Request(cfg["base"] + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    try:
        return json.loads(body) if body else None
    except ValueError:
        return None


def zot_key(resp):
    if isinstance(resp, dict):
        if resp.get("key"):
            return resp["key"]
        ok = resp.get("successful") or {}
        if ok:
            first = ok[sorted(ok)[0]]
            return (first or {}).get("key")
    return None


def zot_collection(cfg, name, create=True):
    found = zot_request(cfg, "GET",
                        f"/collections?q={urllib.parse.quote(name)}&limit=100") or []
    for c in found:
        if (c.get("data") or {}).get("name", "").strip().lower() == name.strip().lower():
            return c["key"], False
    if not create:
        return None, False
    resp = zot_request(cfg, "POST", "/collections", [{"name": name}])
    ck = zot_key(resp)
    if not ck:
        raise RuntimeError(f"could not create collection {name!r}: {resp}")
    return ck, True


def zot_find_by_doi(cfg, doi):
    """Look for an existing library item with this DOI."""
    d = norm_doi(doi)
    if not d:
        return None
    try:
        res = zot_request(cfg, "GET",
                          f"/items?q={urllib.parse.quote(d)}&qmode=everything&limit=25") or []
    except Exception:
        return None
    for it in res:
        if norm_doi((it.get("data") or {}).get("DOI")) == d:
            return it
    return None


def zot_item(rec, collection_key):
    creators = []
    for a in rec.get("authors") or []:
        parts = a.split()
        if not parts:
            continue
        if len(parts) == 1:
            creators.append({"creatorType": "author", "name": parts[0]})
        else:
            creators.append({"creatorType": "author",
                             "firstName": " ".join(parts[:-1]), "lastName": parts[-1]})
    it = {
        "itemType": "journalArticle" if rec.get("venue") else "document",
        "title": rec.get("title") or "",
        "creators": creators,
        "abstractNote": rec.get("abstract") or "",
        "date": str(rec.get("year") or ""),
        "DOI": norm_doi(rec.get("doi")),
        "url": rec.get("url") or "",
        "publicationTitle": rec.get("venue") or "",
        "collections": [collection_key],
        "language": "en",
        "libraryCatalog": ", ".join(rec.get("sources") or []),
    }
    return {k: v for k, v in it.items() if v not in ("", [], None)}


def zot_attach(cfg, parent, path):
    data = open(path, "rb").read()
    md5 = hashlib.md5(data).hexdigest()
    payload = {
        "itemType": "attachment", "parentItem": parent, "linkMode": "imported_file",
        "title": "Full Text PDF", "contentType": "application/pdf",
        "filename": os.path.basename(path), "md5": md5,
        "mtime": int(os.path.getmtime(path) * 1000),
    }
    created = zot_request(cfg, "POST", "/items", [payload])
    akey = zot_key(created)
    if not akey:
        raise RuntimeError("attachment item not created")
    item = zot_request(cfg, "GET", f"/items/{akey}") or {}
    href = ((item.get("links") or {}).get("enclosure") or {}).get("href")
    if not href:
        raise RuntimeError("no upload link")
    req = urllib.request.Request(href, data=data, method="POST", headers={
        "Content-Type": "application/pdf", "If-None-Match": "*",
        "Content-Length": str(len(data))})
    urllib.request.urlopen(req, timeout=180).read()
    zot_request(cfg, "PATCH", f"/items/{akey}", {"md5": md5},
                extra={"If-Unmodified-Since-Version": str(item.get("version", 0))})
    return akey


def write_zotero_bundle(outdir, collection, records, pdfdir=None):
    os.makedirs(outdir, exist_ok=True)
    bib = os.path.join(outdir, f"{slug(collection)}-for-zotero.bib")
    with open(bib, "w", encoding="utf-8") as f:
        f.write(f"% Target collection: {collection}\n\n")
        f.write(fmt_bibtex(records))
    tips = os.path.join(outdir, "HOW-TO-IMPORT.txt")
    with open(tips, "w", encoding="utf-8") as f:
        f.write(
            f"Target Zotero collection: {collection}\n\n"
            "1. In Zotero, create (or select) that collection.\n"
            f"2. Drag {os.path.basename(bib)} onto the collection in the left pane.\n"
            "   (Or File > Import, and choose the collection as destination.)\n"
            "3. Check for duplicates with Duplicate Items before merging.\n")
    return bib, tips


def cmd_zotero(a):
    results = load_results(a.from_json)
    picks = parse_selection(a.select, len(results))
    if not picks:
        print("Nothing selected.")
        return 0
    records = [results[i] for i in picks]

    cfg = None if a.offline else zot_config(authorize=a.authorize)
    if not cfg or (cfg["mode"] == "local" and not cfg.get("key")):
        if cfg and not cfg.get("key"):
            print("Local Zotero found, but write access is not granted yet.")
            print("Re-run with --authorize to approve the request in Zotero.")
        bib, tips = write_zotero_bundle(a.out, a.collection, records, a.pdf_dir)
        print(f"Wrote {bib}")
        print(f"Wrote {tips}")
        print(f"Drag the .bib onto the '{a.collection}' collection in Zotero.")
        return 0

    where = f"local Zotero {cfg.get('version') or ''}".strip() if cfg["mode"] == "local" else "Zotero web API"
    print(f"Using {where}")

    if a.dry_run:
        print(f"[dry run] target collection: '{a.collection}'")
        for i in picks:
            r = results[i]
            hit = zot_find_by_doi(cfg, r.get("doi"))
            if hit:
                d = hit.get("data") or {}
                print(f"  #{i+1:<3} exists ({d.get('key')}) — would add to collection")
            else:
                print(f"  #{i+1:<3} would import — {(r.get('title') or '')[:60]}")
        return 0

    ck, created = zot_collection(cfg, a.collection)
    print(f"Collection '{a.collection}' {'created' if created else 'found'} ({ck})")

    imported, linked, skipped, failed, keys = 0, 0, 0, [], []
    for i in picks:
        rec = results[i]
        try:
            hit = zot_find_by_doi(cfg, rec.get("doi"))
            if hit:
                d = hit.get("data") or {}
                cols = d.get("collections") or []
                k = d.get("key") or hit.get("key")
                if ck in cols:
                    skipped += 1
                else:
                    zot_request(cfg, "PATCH", f"/items/{k}",
                                {"collections": cols + [ck]},
                                extra={"If-Unmodified-Since-Version": str(hit.get("version", 0))})
                    linked += 1
                keys.append((i, k))
                continue
            resp = zot_request(cfg, "POST", "/items", [zot_item(rec, ck)]) or {}
            k = zot_key(resp)
            if k:
                imported += 1
                keys.append((i, k))
            else:
                failed.append((i, resp))
        except Exception as e:
            failed.append((i, f"{type(e).__name__}: {e}"))

    print(f"Imported {imported}, linked {linked} existing, "
          f"skipped {skipped} already present, {len(failed)} failed")
    for idx, info in failed:
        print(f"  failed #{idx+1}: {info}")

    if a.pdf_dir:
        attached, missing = 0, 0
        for idx, k in keys:
            if not k:
                continue
            p = os.path.join(a.pdf_dir, safe_name(records[idx]))
            if not os.path.exists(p):
                missing += 1
                continue
            try:
                zot_attach(cfg, k, p)
                attached += 1
            except Exception as e:
                log(f"[zotero] attach #{idx+1}: {type(e).__name__}: {e}")
                missing += 1
        print(f"Attached {attached} PDF(s); {missing} without a local file")
    return 0


def cmd_journals(a):
    rows = load_journals()
    if a.add:
        key = norm_title(a.add)
        if key in rows:
            print(f"Already present: {rows[key]['title']} ({rows[key]['index']})")
            return 0
        rows[key] = {"title": a.add, "index": a.index, "order": 0}
        with open(JOURNALS_CSV, "a", encoding="utf-8") as f:
            f.write(f"{a.add},{a.index}\n")
        print(f"Added: {a.add} ({a.index}) -> {JOURNALS_CSV}")
        return 0
    if a.search:
        pat = norm_title(a.search)
        hits = [r for k, r in rows.items() if pat in k]
        hits.sort(key=lambda r: -r.get("order", 0))
        for r in hits[:25]:
            print(f"{r['index']:<9} {r['title']}")
        print(f"\n{len(hits)} match(es), {len(rows)} entries total")
        return 0
    if a.list:
        for r in sorted(rows.values(), key=lambda r: -r.get("order", 0)):
            print(f"{r['index']:<9} {r['title']}")
        print(f"\n{len(rows)} entries total")
        return 0
    print(f"{len(rows)} journals in the allowlist: {JOURNALS_CSV}")
    return 0


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(prog="paper_search", description="Multi-source academic literature search")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--limit", type=int, default=25, help="results per query per source (default 25)")
        sp.add_argument("--max-results", type=int, default=60, help="cap after merge (default 60)")
        sp.add_argument("--top", type=int, default=25, help="rows in brief output")
        sp.add_argument("--format", choices=["brief", "json", "md", "bibtex"], default="brief")
        sp.add_argument("--save", metavar="DIR", help="write .json/.md/.bib into DIR")
        sp.add_argument("--bib", metavar="PATH",
                        help="append to a .bib file, or write a dated .bib into a directory; "
                             "entries already present are skipped")
        sp.add_argument("--no-cache", action="store_true")
        sp.add_argument("--verbose", "-v", action="store_true", help="progress on stderr")
        sp.add_argument("--cache-dir", default=DEFAULT_CACHE)

    s = sub.add_parser("search", help="keyword search across sources")
    s.add_argument("--query", "-q", action="append", help="repeatable; pass 4-8 variants")
    s.add_argument("--queries-file", help="one query per line, # comments allowed")
    s.add_argument("--sources", default="openalex,arxiv,pubmed,crossref",
                   help="comma list: openalex,arxiv,pubmed,crossref,s2")
    s.add_argument("--year-from", type=int)
    s.add_argument("--year-to", type=int)
    s.add_argument("--oa-only", action="store_true", help="only records with an OA link or DOI")
    s.add_argument("--min-cites", type=int, default=0)
    s.add_argument("--quality", choices=["strict", "balanced", "off"], default="balanced",
                   help="strict: SSCI/SCIE + flagship + credible preprints only; "
                        "balanced: also reputable journals not yet in the allowlist; "
                        "off: keep everything")
    common(s)
    s.set_defaults(func=cmd_search)

    b = sub.add_parser("snowball", help="walk citations forward/backward from one paper")
    b.add_argument("--id", required=True, help="DOI, doi.org URL, or OpenAlex id")
    b.add_argument("--direction", choices=["cites", "refs", "both"], default="cites")
    b.add_argument("--context", help="optional context to rank neighbours")
    b.add_argument("--quality", choices=["strict", "balanced", "off"], default="balanced")
    common(b)
    b.set_defaults(func=cmd_snowball)

    k = sub.add_parser("pick", help="generate an interactive HTML picker from a saved search")
    k.add_argument("--from-json", required=True, help="the .json written by search --save")
    k.add_argument("--out", help="output .html path")
    k.add_argument("--open", action="store_true", help="open in the default browser")
    k.set_defaults(func=cmd_pick)

    f = sub.add_parser("fetch", help="download open-access PDFs for selected records")
    f.add_argument("--from-json", required=True)
    f.add_argument("--select", default="all", help='1-based, e.g. "1,3,5-7" (default: all)')
    f.add_argument("--out", default="pdfs", help="destination folder (default: pdfs)")
    f.add_argument("--dry-run", action="store_true", help="show what would be tried")
    f.add_argument("--verbose", "-v", action="store_true", help="show each attempt on stderr")
    f.add_argument("--format", choices=["brief", "json"], default="brief")
    f.set_defaults(func=cmd_fetch)

    z = sub.add_parser("zotero", help="import selected records into a Zotero collection")
    z.add_argument("--from-json", required=True)
    z.add_argument("--select", default="all", help='1-based, e.g. "1,3,5-7"')
    z.add_argument("--collection", required=True, help="target subcollection name")
    z.add_argument("--pdf-dir", help="folder with downloaded PDFs, attached to the items")
    z.add_argument("--out", default="zotero-import", help="where to write the .bib fallback")
    z.add_argument("--offline", action="store_true", help="force the .bib route even with an API key")
    z.add_argument("--authorize", action="store_true",
                   help="ask Zotero for local write access (shows a permission dialog)")
    z.add_argument("--dry-run", action="store_true", help="report what would happen, write nothing")
    z.set_defaults(func=cmd_zotero)

    g = sub.add_parser("journals", help="inspect or extend the SSCI/SCIE allowlist")
    g.add_argument("--list", action="store_true", help="show all entries")
    g.add_argument("--search", help="search the allowlist by title")
    g.add_argument("--add", metavar="TITLE", help="add a journal title")
    g.add_argument("--index", choices=["SSCI", "SCIE", "SSCI/SCIE", "FLAGSHIP", "ESCI"],
                   default="SSCI", help="index for --add (default SSCI)")
    g.set_defaults(func=cmd_journals)

    a = p.parse_args()
    global VERBOSE
    VERBOSE = bool(getattr(a, "verbose", False))
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
