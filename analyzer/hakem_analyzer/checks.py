"""Deterministic manuscript checks.

Everything here is rule-based and cheap: it runs before (and independently of)
the LLM review, so a report is still produced when no model is configured, and
the LLM is told what was already found instead of re-discovering it.

Input is plain text or Markdown. Headings are recognised in three common forms:
Markdown (`## Methods`), numbered (`2. Methods`, `2.1 Data`) and a short line on
its own that matches a known section name (`ABSTRACT`, `References`).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

# Canonical section -> accepted heading spellings (lower-case, no numbering).
SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "abstract": ("abstract", "summary", "özet", "öz"),
    "introduction": ("introduction", "background", "motivation", "giriş"),
    "methods": ("methods", "method", "methodology", "materials and methods",
                "experimental setup", "approach", "proposed method",
                "yöntem", "yöntemler", "materyal ve yöntem", "gereç ve yöntem"),
    "results": ("results", "experiments", "evaluation", "experimental results",
                "results and discussion", "bulgular", "sonuçlar", "deneyler",
                "bulgular ve tartışma"),
    "discussion": ("discussion", "conclusion", "conclusions",
                   "discussion and conclusion", "conclusion and future work",
                   "results and discussion", "tartışma", "sonuç",
                   "tartışma ve sonuç", "bulgular ve tartışma"),
    "references": ("references", "bibliography", "works cited", "literature cited",
                   "kaynaklar", "kaynakça"),
}
REQUIRED_SECTIONS = ("abstract", "introduction", "methods", "results",
                     "discussion", "references")

ABSTRACT_MIN_WORDS = 100
ABSTRACT_MAX_WORDS = 300
LONG_SENTENCE_WORDS = 45

_MD_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(?P<title>.+?)\s*#*\s*$")
_NUM_HEADING = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)*)\.?\s+(?P<title>[A-ZÇĞİÖŞÜ][^.!?]{1,80})$")
_NUMERIC_CITE = re.compile(r"\[(?P<body>\d+(?:\s*[-–,]\s*\d+)*)\]")
_NAME = r"[A-ZÇĞİÖŞÜ][\w'\-]+"
_ETAL = r"(?: et al\.| vd\.)?"
_ONE_CITE = rf"{_NAME}{_ETAL}(?:,| (?:and|&|ve) {_NAME},)?\s*(?:19|20)\d{{2}}[a-z]?"
_AUTHOR_YEAR_CITE = re.compile(rf"\((?P<body>{_ONE_CITE}(?:;\s*{_ONE_CITE})*)\)")
_REF_NUMBERED = re.compile(r"^\s*(?:\[(?P<a>\d+)\]|(?P<b>\d+)\.)\s+\S")
_FIG_KIND = r"Fig(?:ure)?s?|Tables?|Şekil|Tablo|Çizelge"
_FIG_MENTION = re.compile(rf"(?<!\w)(?P<kind>{_FIG_KIND})\.?\s+(?P<num>\d+)", re.IGNORECASE)
_CAPTION = re.compile(rf"^\s*(?:\*\*)?(?P<kind>{_FIG_KIND})\.?\s+(?P<num>\d+)\s*[:.|]", re.IGNORECASE)
_ACRONYM_DEF = re.compile(r"\(([A-Z][A-Z0-9]{1,7}s?)\)")
_ACRONYM_USE = re.compile(r"\b([A-Z][A-Z0-9]{1,7})s?\b")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\[(])")

# Upper-case tokens that are not acronyms needing a definition.
_ACRONYM_ALLOW = {
    "I", "A", "AI", "OK", "US", "UK", "EU", "USA", "PDF", "URL", "ID", "IT", "II", "III",
    "IV", "DOI", "ISBN", "ISSN", "PHD", "MSC", "GPU", "CPU", "RAM", "SQL", "API", "HTTP",
    "JSON", "XML", "HTML", "CSV", "UTC", "AM", "PM", "TABLE", "FIGURE", "NOTE",
}


@dataclass
class Issue:
    code: str
    severity: str          # "high" | "medium" | "low"
    message: str
    line: int | None = None
    section: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Section:
    key: str | None        # canonical name, or None for an unrecognised heading
    title: str
    start_line: int        # 1-based line of the heading
    body: str = ""


@dataclass
class CheckResult:
    sections: list[Section] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    stats: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "sections": [{"key": s.key, "title": s.title, "line": s.start_line} for s in self.sections],
            "issues": [i.to_dict() for i in self.issues],
            "stats": self.stats,
        }


def _lower_tr(s: str) -> str:
    return s.replace("I", "ı").replace("İ", "i").lower()


def _fig_kind(kind: str) -> str:
    return "table" if _lower_tr(kind).startswith(("tab", "çiz")) else "figure"


def _canonical(title: str) -> str | None:
    # Turkish and English lower-case "I" differently ("ı" vs "i"), so try both.
    for lowered in (title.lower(), _lower_tr(title)):
        t = re.sub(r"[^\w ]|[\d_]", " ", lowered)
        t = re.sub(r"\s+", " ", t).strip()
        for key, aliases in SECTION_ALIASES.items():
            if t in aliases:
                return key
    return None


def _heading_title(line: str) -> str | None:
    m = _MD_HEADING.match(line)
    if m:
        return m.group("title").strip("*_ ")
    m = _NUM_HEADING.match(line)
    if m and len(m.group("title").split()) <= 8:
        return m.group("title").strip()
    stripped = line.strip().strip("*_:").strip()
    if stripped and len(stripped) <= 40 and _canonical(stripped):
        return stripped
    return None


def split_sections(text: str) -> list[Section]:
    lines = text.splitlines()
    sections: list[Section] = []
    current: Section | None = None
    buf: list[str] = []
    for i, line in enumerate(lines, start=1):
        title = _heading_title(line)
        if title is not None:
            if current is not None:
                current.body = "\n".join(buf).strip()
            current = Section(key=_canonical(title), title=title, start_line=i)
            sections.append(current)
            buf = []
        else:
            buf.append(line)
    if current is not None:
        current.body = "\n".join(buf).strip()
    return sections


def _expand_numeric(body: str) -> set[int]:
    nums: set[int] = set()
    for part in re.split(r"\s*,\s*", body):
        if re.search(r"[-–]", part):
            a, b = re.split(r"\s*[-–]\s*", part)[:2]
            lo, hi = int(a), int(b)
            if 0 < hi - lo < 200:
                nums.update(range(lo, hi + 1))
        elif part.strip().isdigit():
            nums.add(int(part))
    return nums


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _words(s: str) -> int:
    return len(re.findall(r"\b\w[\w'-]*\b", s))


def check_structure(sections: list[Section]) -> list[Issue]:
    issues: list[Issue] = []
    present = {s.key for s in sections if s.key}
    for key in REQUIRED_SECTIONS:
        if key not in present:
            issues.append(Issue("missing_section", "high",
                                f"No '{key.title()}' section was found.", section=key))
    order = [s.key for s in sections if s.key in REQUIRED_SECTIONS]
    expected = [k for k in REQUIRED_SECTIONS if k in order]
    first_seen = list(dict.fromkeys(order))
    if first_seen != expected:
        issues.append(Issue("section_order", "medium",
                            "Sections are out of the usual order: " + " → ".join(first_seen) + "."))
    for s in sections:
        if s.key and s.key != "references" and _words(s.body) == 0:
            issues.append(Issue("empty_section", "high",
                                f"Section '{s.title}' has no text.", line=s.start_line, section=s.key))
    return issues


def check_abstract(sections: list[Section]) -> tuple[list[Issue], int | None]:
    abstract = next((s for s in sections if s.key == "abstract"), None)
    if abstract is None:
        return [], None
    n = _words(abstract.body)
    issues = []
    if 0 < n < ABSTRACT_MIN_WORDS:
        issues.append(Issue("abstract_length", "medium",
                            f"Abstract is {n} words; most venues expect {ABSTRACT_MIN_WORDS}-{ABSTRACT_MAX_WORDS}.",
                            line=abstract.start_line, section="abstract"))
    elif n > ABSTRACT_MAX_WORDS:
        issues.append(Issue("abstract_length", "medium",
                            f"Abstract is {n} words; most venues cap it at {ABSTRACT_MAX_WORDS}.",
                            line=abstract.start_line, section="abstract"))
    if _NUMERIC_CITE.search(abstract.body) or _AUTHOR_YEAR_CITE.search(abstract.body):
        issues.append(Issue("abstract_citation", "low",
                            "The abstract contains citations; many venues do not allow them.",
                            line=abstract.start_line, section="abstract"))
    return issues, n


def check_citations(text: str, sections: list[Section]) -> tuple[list[Issue], dict]:
    refs = next((s for s in sections if s.key == "references"), None)
    ref_start = refs.start_line if refs else None
    body_lines = text.splitlines()[: (ref_start - 1) if ref_start else None]
    body = "\n".join(body_lines)

    cited: dict[int, int] = {}
    for m in _NUMERIC_CITE.finditer(body):
        for n in _expand_numeric(m.group("body")):
            cited.setdefault(n, _line_of(body, m.start()))
    # (first author surname, year) -> first line it is cited on
    ay_cited: dict[tuple[str, str], int] = {}
    for m in _AUTHOR_YEAR_CITE.finditer(body):
        for piece in m.group("body").split(";"):
            name, year = re.match(_NAME, piece.strip()), re.search(r"(?:19|20)\d{2}[a-z]?", piece)
            if name and year:
                ay_cited.setdefault((name.group(0), year.group(0)), _line_of(body, m.start()))
    author_year = len(_AUTHOR_YEAR_CITE.findall(body))

    ref_numbers: list[int] = []
    ay_refs: list[tuple[str, str]] = []
    unnumbered_refs = 0
    if refs:
        for line in refs.body.splitlines():
            if not line.strip():
                continue
            m = _REF_NUMBERED.match(line)
            if m:
                ref_numbers.append(int(m.group("a") or m.group("b")))
            elif len(line.strip()) > 20:
                unnumbered_refs += 1
                name = re.match(_NAME, line.strip())
                year = re.search(r"(?:19|20)\d{2}[a-z]?", line)
                if name and year:
                    ay_refs.append((name.group(0), year.group(0)))

    issues: list[Issue] = []
    stats = {"numeric_citations": len(cited), "author_year_citations": author_year,
             "reference_entries": len(ref_numbers) + unnumbered_refs}

    if cited and author_year:
        issues.append(Issue("mixed_citation_style", "medium",
                            f"Both numeric ({len(cited)}) and author-year ({author_year}) citations are used."))
    if not cited and not author_year and refs:
        issues.append(Issue("no_citations", "high",
                            "The reference list is never cited in the text.", section="references"))

    if ref_numbers:
        ref_set = set(ref_numbers)
        for n in sorted(set(cited) - ref_set):
            issues.append(Issue("citation_without_reference", "high",
                                f"[{n}] is cited but there is no reference entry {n}.", line=cited[n]))
        for n in sorted(ref_set - set(cited)):
            if cited:  # only meaningful when the text uses numeric citations
                issues.append(Issue("uncited_reference", "medium",
                                    f"Reference [{n}] is listed but never cited.", section="references"))
        dupes = sorted({n for n in ref_numbers if ref_numbers.count(n) > 1})
        for n in dupes:
            issues.append(Issue("duplicate_reference_number", "medium",
                                f"Reference number {n} appears more than once.", section="references"))
        if cited:
            first_order = sorted(cited, key=lambda k: (cited[k], k))
            if first_order != sorted(first_order) and len(first_order) >= 3:
                issues.append(Issue("citation_order", "low",
                                    "Numeric citations are not numbered in order of first appearance."))

    if ay_refs and ay_cited:
        ref_keys = set(ay_refs)
        for (name, year), line in sorted(ay_cited.items(), key=lambda kv: kv[1]):
            if (name, year) not in ref_keys:
                issues.append(Issue("citation_without_reference", "high",
                                    f"({name}, {year}) is cited but has no matching reference entry.", line=line))
        for name, year in sorted(ref_keys - set(ay_cited)):
            issues.append(Issue("uncited_reference", "medium",
                                f"Reference '{name} ({year})' is listed but never cited.", section="references"))
    return issues, stats


def check_figures(text: str, sections: list[Section]) -> list[Issue]:
    refs = next((s for s in sections if s.key == "references"), None)
    lines = text.splitlines()
    if refs:
        lines = lines[: refs.start_line - 1]
    captions: dict[tuple[str, int], int] = {}
    mentions: dict[tuple[str, int], int] = {}
    for i, line in enumerate(lines, start=1):
        cap = _CAPTION.match(line)
        if cap:
            kind = _fig_kind(cap.group("kind"))
            captions.setdefault((kind, int(cap.group("num"))), i)
            rest = line[cap.end():]
        else:
            rest = line
        for m in _FIG_MENTION.finditer(rest):
            kind = _fig_kind(m.group("kind"))
            mentions.setdefault((kind, int(m.group("num"))), i)
    issues = []
    for (kind, n), line in sorted(captions.items()):
        if (kind, n) not in mentions:
            issues.append(Issue("unreferenced_figure", "medium",
                                f"{kind.title()} {n} has a caption but is never referred to in the text.", line=line))
    for (kind, n), line in sorted(mentions.items()):
        if (kind, n) not in captions:
            issues.append(Issue("missing_figure", "high",
                                f"{kind.title()} {n} is referred to but has no caption.", line=line))
    return issues


def check_acronyms(text: str, sections: list[Section]) -> list[Issue]:
    refs = next((s for s in sections if s.key == "references"), None)
    lines = text.splitlines()
    if refs:
        lines = lines[: refs.start_line - 1]
    heading_lines = {s.start_line for s in sections}
    defined_at: dict[str, int] = {}
    first_use: dict[str, int] = {}
    for i, line in enumerate(lines, start=1):
        if i in heading_lines or _CAPTION.match(line):
            continue
        for m in _ACRONYM_DEF.finditer(line):
            defined_at.setdefault(m.group(1).rstrip("s"), i)
        no_defs = _ACRONYM_DEF.sub(" ", line)
        no_cites = _NUMERIC_CITE.sub(" ", no_defs)
        for m in _ACRONYM_USE.finditer(no_cites):
            tok = m.group(1)
            if tok in _ACRONYM_ALLOW or tok.isdigit() or re.fullmatch(r"[A-Z]\d*", tok):
                continue
            first_use.setdefault(tok, i)
    issues = []
    for tok, line in sorted(first_use.items(), key=lambda kv: kv[1]):
        d = defined_at.get(tok)
        if d is None:
            issues.append(Issue("undefined_acronym", "low",
                                f"'{tok}' is never defined (e.g. 'Full Name ({tok})').", line=line))
        elif line < d:
            issues.append(Issue("acronym_used_before_definition", "low",
                                f"'{tok}' is used on line {line} but defined on line {d}.", line=line))
    return issues


def check_sentences(sections: list[Section]) -> tuple[list[Issue], dict]:
    long_count = 0
    worst: tuple[int, int, str] | None = None
    total = 0
    for s in sections:
        if s.key == "references":
            continue
        for sent in _SENTENCE_SPLIT.split(s.body.replace("\n", " ")):
            n = _words(sent)
            if n == 0:
                continue
            total += 1
            if n > LONG_SENTENCE_WORDS:
                long_count += 1
                if worst is None or n > worst[0]:
                    worst = (n, s.start_line, s.title)
    issues = []
    if long_count:
        n, line, title = worst
        issues.append(Issue("long_sentences", "low",
                            f"{long_count} sentence(s) exceed {LONG_SENTENCE_WORDS} words; the longest "
                            f"({n} words) is in '{title}'.", line=line))
    return issues, {"sentences": total, "long_sentences": long_count}


def run_checks(text: str) -> CheckResult:
    sections = split_sections(text)
    result = CheckResult(sections=sections)
    result.issues += check_structure(sections)
    abs_issues, abs_words = check_abstract(sections)
    result.issues += abs_issues
    cite_issues, cite_stats = check_citations(text, sections)
    result.issues += cite_issues
    result.issues += check_figures(text, sections)
    result.issues += check_acronyms(text, sections)
    sent_issues, sent_stats = check_sentences(sections)
    result.issues += sent_issues
    result.stats = {"words": _words(text), "abstract_words": abs_words, **cite_stats, **sent_stats}
    return result
