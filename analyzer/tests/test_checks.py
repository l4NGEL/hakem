from pathlib import Path

import pytest

from hakem_analyzer.checks import run_checks, split_sections

SAMPLES = Path(__file__).resolve().parents[1] / "samples"


def codes(text: str) -> list[str]:
    return [i.code for i in run_checks(text).issues]


@pytest.mark.parametrize("name", ["clean_markdown.md", "clean_turkish.md"])
def test_clean_samples_have_no_findings(name):
    assert codes((SAMPLES / name).read_text(encoding="utf-8")) == []


def test_heading_styles_are_recognised():
    text = "# Title\n\nABSTRACT\nx\n\n1. Introduction\nx\n\n2.1 Data\nx\n\n## Methods\nx\n\nKaynakça\n"
    keys = [s.key for s in split_sections(text)]
    assert keys == [None, "abstract", "introduction", None, "methods", "references"]


def test_turkish_and_english_capital_i():
    keys = [s.key for s in split_sections("GİRİŞ\nmetin\n\nINTRODUCTION\ntext\n")]
    assert keys == ["introduction", "introduction"]


def test_numeric_citation_lists_and_ranges_expand():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    result = run_checks(text.replace("[4]", "[4, 8-9]", 1))
    missing = [i.message for i in result.issues if i.code == "citation_without_reference"]
    assert missing == ["[8] is cited but there is no reference entry 8.",
                       "[9] is cited but there is no reference entry 9."]


def test_author_year_cross_check():
    text = (SAMPLES / "clean_turkish.md").read_text(encoding="utf-8")
    text = text.replace("(Arslan, 2022)", "(Arslan, 2023)")
    found = {i.code: i.message for i in run_checks(text).issues}
    assert "(Arslan, 2023) is cited" in found["citation_without_reference"]
    assert "Arslan (2022)" in found["uncited_reference"]


def test_figure_mentioned_without_caption_and_caption_without_mention():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    text = text.replace("Figure 1 shows", "Fig. 2 shows")
    c = codes(text)
    assert "missing_figure" in c and "unreferenced_figure" in c


def test_acronym_defined_after_use():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    text = text.replace("Spectral features around", "A CMS tracks spectral features around")
    text = text.replace("they rarely have a condition monitoring system (CMS)", "they rarely have one")
    assert "undefined_acronym" in codes(text)


def test_mixed_citation_styles():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    text = text.replace("[3].", "(Lindqvist, 2018).", 1)
    assert "mixed_citation_style" in codes(text)


def test_missing_and_out_of_order_sections():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    text = text.replace("## Methods", "## Notes")
    assert "missing_section" in codes(text)


def test_abstract_bounds():
    text = (SAMPLES / "clean_markdown.md").read_text(encoding="utf-8")
    short = run_checks(text.split("## Introduction")[0][:400] + "\n## Introduction" + text.split("## Introduction")[1])
    assert any(i.code == "abstract_length" for i in short.issues)


def test_empty_text_reports_all_sections_missing():
    assert codes("").count("missing_section") == 6
