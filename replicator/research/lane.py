"""The research lane: a small, bounded web lookup that feeds Explain.

Replicator's models never answer "how does this work" from memory. Explain asks this lane instead: it searches,
reads a few pages, and hands the model a short numbered list of excerpts. The model may only state what an excerpt
says and must cite it; `core/explain.py` then checks every sentence against the excerpt it cites.

"Limited context" is literal. The lane has hard budgets (queries, pages, bytes per page, characters per excerpt,
characters in total), so one explanation costs a few kilobytes of reading and a few thousand tokens of context, and
a page can never flood the model. Pages are untrusted text: they are reduced to plain sentences, never executed,
and the prompt tells the model to treat them as quotations, not instructions.

Backends (all plain HTTPS GETs with a generic User-Agent, nothing about the user or the project is sent):
  wikipedia   the MediaWiki API: search, then the plain-text extract of each hit (no scraping needed)
  searxng     your own SearXNG instance (`search_url` in ~/.config/Replicator/services.json) for the wider web
Public search sites answer scripts with a bot check, and the lane does not try to get round one: without a
SearXNG address it reads Wikipedia only.
Only the search words leave the machine: the object's name and its part names.
"""
from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

UA = "Replicator-research/1.0 (local desktop app)"
TIMEOUT = 12
MAX_QUERIES = 4          # searches per explanation
MAX_PAGES = 6            # pages read per explanation
MAX_PAGE_BYTES = 400_000
EXCERPT_CHARS = 620      # one excerpt
EXCERPTS_PER_SOURCE = 2
CONTEXT_CHARS = 6400     # everything the model gets to read
STOP = set("a an the of and or to in on for with by from at as is are was were be been it its this that these those "
           "which who whom what how why when where can could may might will would should than then also into over "
           "under between not no but if so such their there his her they them we you your our has have had do does "
           "did more most other some any each used use using one two new".split())
SKIP_HOSTS = ("youtube.", "facebook.", "twitter.", "x.com", "instagram.", "pinterest.", "tiktok.", "reddit.")


@dataclass
class Source:
    n: int
    title: str
    url: str
    domain: str
    excerpts: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def _get(url: str, limit: int = MAX_PAGE_BYTES) -> str:
    if not url.lower().startswith(("https://", "http://")):
        raise ValueError("only http(s) pages are read")
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en"})
    _pace(urllib.parse.urlparse(url).netloc)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and "json" not in ctype and "text" not in ctype:
            raise ValueError(f"not a text page ({ctype})")
        raw = r.read(limit)
    return raw.decode(r.headers.get_content_charset() or "utf-8", "replace")


_last: dict[str, float] = {}


def _pace(host: str, gap: float = 0.6) -> None:
    """Be a polite client: never more than one request per `gap` seconds to the same host."""
    wait = _last.get(host, 0.0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()


class _Text(HTMLParser):
    """HTML to readable text: paragraphs, headings and list items; scripts, styles, nav and footers dropped."""
    DROP = {"script", "style", "noscript", "nav", "footer", "header", "aside", "form", "svg", "button", "figure"}
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "td", "br", "div", "section", "article", "blockquote", "dd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self.DROP:
            self.skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):
        if tag in self.DROP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self.skip:
            self.out.append(data)


def page_text(markup: str) -> tuple[str, list[str]]:
    """(title, paragraphs) of an HTML page. Paragraphs shorter than a sentence are menu debris and are dropped."""
    p = _Text()
    try:
        p.feed(markup)
    except Exception:  # noqa: BLE001 - broken markup: keep what was read so far
        pass
    paras = []
    for block in "".join(p.out).split("\n"):
        t = re.sub(r"\s+", " ", block).strip()
        t = re.sub(r"\[\d+\]", "", t)                      # footnote markers
        if len(t) >= 80 and t.count(" ") >= 12:
            paras.append(t)
    return re.sub(r"\s+", " ", p.title).strip(), paras


def words(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z][a-z0-9\-]{2,}", text.lower()) if w not in STOP]


def _stem(w: str) -> str:
    for suf in ("ings", "ing", "ers", "er", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def stems(text: str) -> set[str]:
    return {_stem(w) for w in words(text)}


def rank(paragraphs: list[str], query_terms: set[str], k: int = EXCERPTS_PER_SOURCE) -> list[str]:
    """The k paragraphs that say the most about the query terms (BM25-style, favouring explanatory prose)."""
    if not paragraphs:
        return []
    docs = [[_stem(w) for w in words(p)] for p in paragraphs]
    n = len(docs)
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    avg = sum(len(d) for d in docs) / n or 1.0
    scored = []
    for i, d in enumerate(docs):
        s = 0.0
        for t in query_terms:
            f = d.count(t)
            if f:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * f * 2.2 / (f + 1.2 * (0.25 + 0.75 * len(d) / avg))
        if re.search(r"\b(works?|because|so that|allows?|causes?|drives?|converts?|used to|function|purpose)\b",
                     paragraphs[i].lower()):
            s *= 1.25                                      # prefer text that explains over text that lists
        s *= 1.0 + 0.15 * (1 - i / n)                     # and the top of the page over the bottom
        scored.append((s, i))
    top = sorted((x for x in scored if x[0] > 0), reverse=True)[:k]
    return [clip(paragraphs[i]) for _, i in sorted(top, key=lambda x: x[1])]


def clip(text: str, limit: int = EXCERPT_CHARS) -> str:
    """Cut at a sentence end inside the budget."""
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[: end + 1] if end > limit * 0.5 else cut.rsplit(" ", 1)[0] + " …").strip()


# ------------------------------------------------------------------ backends
def wikipedia(query: str, limit: int = 3) -> list[tuple[str, str, list[str]]]:
    """[(title, url, paragraphs)] from the MediaWiki API (search, then plain-text extracts)."""
    api = "https://en.wikipedia.org/w/api.php?"
    hits = json.loads(_get(api + urllib.parse.urlencode(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": limit, "format": "json"})))
    titles = [h["title"] for h in hits.get("query", {}).get("search", [])]
    out = []
    for t in titles:
        data = json.loads(_get(api + urllib.parse.urlencode(
            {"action": "query", "prop": "extracts", "explaintext": 1, "exsectionformat": "plain",
             "titles": t, "format": "json", "redirects": 1})))
        for page in data.get("query", {}).get("pages", {}).values():
            text = page.get("extract") or ""
            paras = [re.sub(r"\s+", " ", p).strip() for p in text.split("\n")]
            paras = [p for p in paras if len(p) >= 80 and p.count(" ") >= 12]
            if paras:
                out.append((page.get("title", t), "https://en.wikipedia.org/wiki/" +
                            urllib.parse.quote(page.get("title", t).replace(" ", "_")), paras))
    return out


def searxng_url(base: str, query: str) -> str:
    """`base` is an instance (http://host:8888) or a full template with {query} (as browsers store search engines)."""
    base = base.replace("%7Bquery%7D", "{query}").replace("%7bquery%7d", "{query}")
    if "{query}" in base:
        return base.replace("{query}", urllib.parse.quote_plus(query))
    return base.rstrip("/").removesuffix("/search") + "/search?" + urllib.parse.urlencode({"q": query, "format": "json"})


def searxng(base: str, query: str, limit: int = 5) -> list[tuple[str, str]]:
    data = json.loads(_get(searxng_url(base, query)))
    if not data.get("results") and data.get("unresponsive_engines"):
        raise RuntimeError("no results; engines down: " + ", ".join(e[0] for e in data["unresponsive_engines"]))
    return [(r.get("title", ""), r["url"]) for r in data.get("results", [])[:limit] if r.get("url")]


# ------------------------------------------------------------------ the lane
def gather(queries: list[str], focus: list[str], search_url: str = "", log=print) -> list[Source]:
    """Run the lane: at most MAX_QUERIES searches and MAX_PAGES pages, at most CONTEXT_CHARS of excerpts.
    `focus` are the words the excerpts should be about (the object and its parts)."""
    terms = set()
    for f in focus + queries:
        terms |= stems(f)
    sources: list[Source] = []
    seen: set[str] = set()
    budget = CONTEXT_CHARS

    def add(title: str, url: str, paras: list[str]) -> None:
        nonlocal budget
        key = url.split("#")[0].rstrip("/")
        if key in seen or budget <= 0 or len(sources) >= MAX_PAGES:
            return
        ex = []
        for e in rank(paras, terms):
            if len(e) <= budget:
                ex.append(e)
                budget -= len(e)
        if ex:
            seen.add(key)
            sources.append(Source(len(sources) + 1, title[:120] or key, url,
                                  urllib.parse.urlparse(url).netloc.removeprefix("www."), ex))

    for q in queries[:MAX_QUERIES]:
        if len(sources) >= MAX_PAGES or budget <= 0:
            break
        log(f"research: searching “{q}”")
        try:
            for title, url, paras in wikipedia(q, 2):
                add(title, url, paras)
        except Exception as e:  # noqa: BLE001 - one backend failing must not end the lane
            log(f"research: wikipedia unavailable ({e})")
        hits = []
        if search_url:
            try:
                hits = searxng(search_url, q)
            except Exception as e:  # noqa: BLE001
                log(f"research: SearXNG unavailable ({e})")
        for title, url in hits[:3]:
            host = urllib.parse.urlparse(url).netloc
            if any(s in host for s in SKIP_HOSTS) or "wikipedia.org" in host or len(sources) >= MAX_PAGES:
                continue
            try:
                ptitle, paras = page_text(_get(url))
                add(title or ptitle, url, paras)
            except Exception as e:  # noqa: BLE001 - a dead or binary page is skipped
                log(f"research: skipped {host} ({e})")
    log(f"research: {len(sources)} source(s), {CONTEXT_CHARS - budget:,} characters of excerpts")
    return sources


def context_block(sources: list[Source]) -> str:
    """The numbered excerpts exactly as the model sees them."""
    lines = []
    for s in sources:
        lines.append(f"[{s.n}] {s.title} ({s.domain})")
        lines += [f"    “{e}”" for e in s.excerpts]
    return "\n".join(lines)
