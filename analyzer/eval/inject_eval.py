"""Seeded-defect evaluation of the rule-based checks.

Takes the clean sample manuscripts (which produce zero findings), injects one or
more known defects at random positions with varied wording, and measures for
each defect type:

  recall       - share of injected defects whose expected issue code is reported
  spill-over   - share of trials that also report a code nobody injected

This is a synthetic test of whether each rule fires when it should and stays
quiet otherwise. It says nothing about how common these defects are in real
manuscripts, or about false alarms on writing styles the samples do not cover.

    python eval/inject_eval.py --trials 300 --seed 7
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from hakem_analyzer.checks import run_checks, split_sections  # noqa: E402

SAMPLES = {
    "en_numeric": ROOT / "samples" / "clean_markdown.md",
    "tr_author_year": ROOT / "samples" / "clean_turkish.md",
}

ACRONYMS = ["RMSE", "FFT", "SVM", "LSTM", "PCA", "ROC", "SNR", "BLEU"]
SURNAMES = ["Doğan", "Keller", "Moreau", "Tanaka", "Okafor", "Lindgren", "Çelik", "Haddix"]
FILLER_EN = ["This choice follows common practice in the field.",
             "The same setting was used in all experiments.",
             "We return to this point in the discussion."]
FILLER_TR = ["Bu seçim alandaki yaygın uygulamayı izlemektedir.",
             "Tüm deneylerde aynı ayar kullanılmıştır.",
             "Bu konuya tartışma bölümünde geri dönülecektir."]


class Doc:
    def __init__(self, name: str, text: str):
        self.name = name
        self.lines = text.splitlines()
        self.turkish = name.startswith("tr")
        self.numeric = "numeric" in name

    @property
    def text(self) -> str:
        return "\n".join(self.lines) + "\n"

    def sections(self):
        return split_sections(self.text)

    def has(self, key):
        return any(s.key == key for s in self.sections())

    def section(self, key):
        return next(s for s in self.sections() if s.key == key)

    def body_paragraph_lines(self, keys=("introduction", "methods", "results", "discussion")):
        """Line indices (0-based) of prose paragraphs in the given sections."""
        out = []
        secs = self.sections()
        for i, s in enumerate(secs):
            if s.key not in keys:
                continue
            end = secs[i + 1].start_line - 1 if i + 1 < len(secs) else len(self.lines)
            for idx in range(s.start_line, end):
                line = self.lines[idx]
                if len(line.split()) > 12 and not re.match(r"^\s*(Table|Figure|Tablo|Şekil)\b", line):
                    out.append(idx)
        return out

    def append_to_random_paragraph(self, rng, sentence: str):
        idx = rng.choice(self.body_paragraph_lines())
        self.lines[idx] = self.lines[idx].rstrip() + " " + sentence

    def ref_numbers(self):
        refs = self.section("references")
        return [int(m.group(1)) for line in self.lines[refs.start_line:]
                if (m := re.match(r"^\[(\d+)\]", line))]


# --- defect injectors: each mutates the doc and returns the issue code it should trigger

def drop_section(doc: Doc, rng):
    key = rng.choice([k for k in ("methods", "discussion") if doc.has(k)])
    del doc.lines[doc.section(key).start_line - 1]
    return "missing_section"


def empty_section(doc: Doc, rng):
    secs = doc.sections()
    key = rng.choice([k for k in ("results", "discussion") if doc.has(k)])
    i = next(i for i, s in enumerate(secs) if s.key == key)
    start, end = secs[i].start_line, secs[i + 1].start_line - 1 if i + 1 < len(secs) else len(doc.lines)
    del doc.lines[start:end]
    doc.lines.insert(start, "")
    return "empty_section"


def cite_missing_reference(doc: Doc, rng):
    if doc.numeric:
        n = max(doc.ref_numbers()) + rng.randint(3, 6)  # never the number uncited_reference adds
        sentence = rng.choice(FILLER_EN)[:-1] + f" [{n}]."
    else:
        sentence = rng.choice(FILLER_TR)[:-1] + f" ({rng.choice(SURNAMES)}, {rng.randint(2005, 2023)})."
    doc.append_to_random_paragraph(rng, sentence)
    return "citation_without_reference"


def uncited_reference(doc: Doc, rng):
    name = rng.choice(SURNAMES)
    year = rng.randint(2005, 2023)
    if doc.numeric:
        n = max(doc.ref_numbers()) + 1
        doc.lines.append(f"[{n}] {name[0]}. {name}, \"An additional study,\" Journal of Testing, vol. 3, pp. 1-10, {year}.")
    else:
        doc.lines.append(f"{name}, Z. ({year}). Ek bir çalışma. Test Dergisi, 3(1), 1-10.")
    return "uncited_reference"


def unreferenced_figure(doc: Doc, rng):
    kind = ("Şekil" if rng.random() < .5 else "Tablo") if doc.turkish else rng.choice(["Figure", "Table"])
    idx = rng.choice(doc.body_paragraph_lines(("methods", "results")))
    doc.lines.insert(idx + 1, f"{kind} 7: Ek sonuçlar." if doc.turkish else f"{kind} 7: Additional results.")
    doc.lines.insert(idx + 1, "")
    return "unreferenced_figure"


def missing_figure(doc: Doc, rng):
    if doc.turkish:
        sentence = f"Ayrıntılar {rng.choice(['Şekil', 'Tablo'])} {rng.randint(3, 6)}'da verilmiştir."
    else:
        sentence = f"Details are given in {rng.choice(['Figure', 'Fig.', 'Table'])} {rng.randint(3, 6)}."
    doc.append_to_random_paragraph(rng, sentence)
    return "missing_figure"


def undefined_acronym(doc: Doc, rng):
    acr = rng.choice(ACRONYMS)
    sentence = (f"Sonuçlar {acr} ile de doğrulandı." if doc.turkish
                else f"The results were also checked with {acr}.")
    doc.append_to_random_paragraph(rng, sentence)
    return "undefined_acronym"


def long_abstract(doc: Doc, rng):
    a = doc.section("abstract")
    body_idx = next(i for i in range(a.start_line, len(doc.lines)) if doc.lines[i].strip())
    original = doc.lines[body_idx]
    while len(doc.lines[body_idx].split()) <= 300 + rng.randint(0, 80):
        doc.lines[body_idx] += " " + original
    return "abstract_length"


def short_abstract(doc: Doc, rng):
    a = doc.section("abstract")
    body_idx = next(i for i in range(a.start_line, len(doc.lines)) if doc.lines[i].strip())
    words = doc.lines[body_idx].split()
    doc.lines[body_idx] = " ".join(words[: rng.randint(30, 80)]) + "."
    return "abstract_length"


def mixed_citation_style(doc: Doc, rng):
    if doc.numeric:
        # cite an existing reference author-year style so only the style is wrong
        sentence = rng.choice(FILLER_EN)[:-1] + " (Osei, 2020)."
    else:
        sentence = rng.choice(FILLER_TR)[:-1] + " [2]."
    doc.append_to_random_paragraph(rng, sentence)
    return "mixed_citation_style"


def long_sentence(doc: Doc, rng):
    words = ("bu deney farklı koşullar altında ve farklı veri alt kümeleriyle defalarca tekrarlanmış"
             if doc.turkish else
             "this experiment was repeated many times under different conditions and on different subsets of the data").split()
    n = rng.randint(50, 70)
    sentence = " ".join((words * 10)[:n]).capitalize() + "."
    doc.append_to_random_paragraph(rng, sentence)
    return "long_sentences"


DEFECTS = [drop_section, empty_section, cite_missing_reference, uncited_reference,
           unreferenced_figure, missing_figure, undefined_acronym, long_abstract,
           short_abstract, mixed_citation_style, long_sentence]

# Defects in the same group would undo each other, so a trial uses at most one per
# group. Structural edits run first so later text insertions are not deleted by them.
EXCLUSIVE = [{drop_section, empty_section}, {long_abstract, short_abstract}]
STRUCTURAL = (drop_section, empty_section)


def pick_defects(rng, k: int):
    pool = DEFECTS[:]
    chosen = []
    while pool and len(chosen) < k:
        fn = rng.choice(pool)
        chosen.append(fn)
        for group in EXCLUSIVE:
            if fn in group:
                pool = [f for f in pool if f not in group]
        if fn in pool:
            pool.remove(fn)
    return sorted(chosen, key=lambda f: f not in STRUCTURAL)


# Codes a defect legitimately causes as a side effect (not counted as spill-over):
# a citation to a new high reference number breaks first-appearance order.
SIDE_EFFECTS = {
    "drop_section": {"section_order"},
    "cite_missing_reference": {"citation_order"},
}


def run(trials: int, seed: int, max_defects: int) -> dict:
    rng = random.Random(seed)
    texts = {k: p.read_text(encoding="utf-8") for k, p in SAMPLES.items()}

    baseline = {k: [i.code for i in run_checks(t).issues] for k, t in texts.items()}

    hits, injected = Counter(), Counter()
    spill_trials, spill_codes = 0, Counter()
    per_sample = defaultdict(lambda: Counter())
    for _ in range(trials):
        name = rng.choice(list(texts))
        doc = Doc(name, texts[name])
        chosen = pick_defects(rng, rng.randint(1, max_defects))
        expected, allowed = [], set()
        for fn in chosen:
            code = fn(doc, rng)
            expected.append((fn.__name__, code))
            allowed |= {code} | SIDE_EFFECTS.get(code, set()) | SIDE_EFFECTS.get(fn.__name__, set())
        found = {i.code for i in run_checks(doc.text).issues}
        for fn_name, code in expected:
            injected[fn_name] += 1
            per_sample[name]["injected"] += 1
            if code in found:
                hits[fn_name] += 1
                per_sample[name]["hit"] += 1
        extra = found - allowed
        if extra:
            spill_trials += 1
            spill_codes.update(extra)

    return {
        "trials": trials, "seed": seed, "max_defects_per_trial": max_defects,
        "clean_baseline_issues": baseline,
        "recall_by_defect": {k: round(hits[k] / injected[k], 3) for k in sorted(injected)},
        "injected_by_defect": dict(sorted(injected.items())),
        "overall_recall": round(sum(hits.values()) / sum(injected.values()), 3),
        "recall_by_sample": {k: round(v["hit"] / v["injected"], 3) for k, v in per_sample.items()},
        "spill_over_rate": round(spill_trials / trials, 3),
        "spill_over_codes": dict(spill_codes.most_common()),
    }


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--max-defects", type=int, default=3)
    ap.add_argument("--out", type=Path, default=ROOT / "eval" / "results.json")
    args = ap.parse_args()
    res = run(args.trials, args.seed, args.max_defects)
    args.out.write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))
