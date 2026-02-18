from __future__ import annotations

import re
from typing import Any

import textstat


CONCLUSION_TERMS = ["conclusion", "bottom line", "final thoughts", "key takeaways", "summary", "wrap up"]
TAKEAWAY_TERMS = ["key takeaways", "highlights", "main points", "tl;dr", "tldr"]
SOURCES_TERMS = ["sources", "references", "citations", "further reading"]


def _normalize(text: str) -> str:
    return " ".join((text or "").lower().split()).strip()


def _safe_div(numerator: float, denominator: float) -> float:
    return round(numerator / denominator, 4) if denominator else 0.0


def _count_keyword_occurrences(text: str, keyword: str) -> int:
    if not keyword:
        return 0
    pattern = re.compile(rf"\b{re.escape(keyword.lower())}\b")
    return len(pattern.findall(text.lower()))


def _keyword_variants(keyword: str) -> list[str]:
    base = _normalize(keyword)
    if not base:
        return []
    parts = base.split()
    variants = {base}
    if len(parts) > 1:
        variants.add(" ".join(parts[:-1]))
        variants.add(" ".join(parts[1:]))
    for part in parts:
        if len(part) > 4:
            variants.add(part)
    return [v for v in variants if v]


def _contains_variant(text: str, variants: list[str]) -> bool:
    text_n = _normalize(text)
    return any(v in text_n for v in variants)


def _heading_hierarchy_valid(heading_hierarchy: list[dict[str, str]]) -> bool:
    previous_level = 0
    for item in heading_hierarchy:
        level = item.get("level", "").lower()
        if not level.startswith("h"):
            continue
        try:
            current = int(level[1:])
        except ValueError:
            continue
        if previous_level and current > previous_level + 1:
            return False
        previous_level = current
    return True




def _safe_textstat(func, text: str, default: float = 0.0) -> float:
    try:
        return float(func(text))
    except Exception:
        return default

def _estimate_avg_sentence_length(text: str) -> float:
    words = len(text.split())
    sentences = max(int(_safe_textstat(textstat.sentence_count, text, default=1)), 1)
    return round(words / sentences, 2)


def _estimate_avg_paragraph_length(raw_text: str) -> float:
    paragraphs = [p for p in re.split(r"\n\s*\n", raw_text) if p.strip()]
    if not paragraphs:
        return 0.0
    sentence_counts = [max(int(_safe_textstat(textstat.sentence_count, p, default=1)), 1) for p in paragraphs]
    return round(sum(sentence_counts) / len(sentence_counts), 2)


def _section_heading_contains(headings: list[str], terms: list[str]) -> bool:
    lowered = [_normalize(h) for h in headings]
    return any(any(term in heading for term in terms) for heading in lowered)


def run_rule_analysis(extracted: dict[str, Any], keyword: str) -> dict[str, Any]:
    if not extracted or extracted.get("error"):
        return {"error": extracted.get("error", "No extractable content to analyze.")}

    keyword_n = _normalize(keyword)
    variants = _keyword_variants(keyword_n)

    title_tag = extracted.get("title_tag", "") or ""
    meta_description = extracted.get("meta_description", "") or ""
    h1_list = extracted.get("h1", []) or []
    h2_list = extracted.get("h2", []) or []
    h3_list = extracted.get("h3", []) or []
    heading_hierarchy = extracted.get("heading_hierarchy", []) or []
    body_text = extracted.get("body_text", "") or ""
    raw_html = extracted.get("raw_html", "") or ""
    word_count = extracted.get("word_count", 0) or 0

    first_100 = " ".join(body_text.split()[:100])

    keyword_occurrences = _count_keyword_occurrences(body_text, keyword_n) if keyword_n else 0
    keyword_density = round((keyword_occurrences / word_count) * 100, 2) if word_count else 0.0
    keyword_in_h2s = sum(1 for h2 in h2_list if _contains_variant(h2, variants)) if variants else 0

    total_links = int(extracted.get("internal_link_count", 0) or 0) + int(extracted.get("external_link_count", 0) or 0)
    link_ratio = f"{int(extracted.get('internal_link_count', 0) or 0)}:{int(extracted.get('external_link_count', 0) or 0)}"

    image_count = len(extracted.get("images", []) or [])
    missing_alt = int(extracted.get("images_missing_alt", 0) or 0)

    flesch_reading_ease = round(_safe_textstat(textstat.flesch_reading_ease, body_text, default=0.0), 2) if body_text else 0.0
    flesch_kincaid_grade = round(_safe_textstat(textstat.flesch_kincaid_grade, body_text, default=0.0), 2) if body_text else 0.0

    all_headings = [h.get("text", "") for h in heading_hierarchy if isinstance(h, dict)]
    intro_word_target = 150
    introduction_segment = " ".join(body_text.split()[:intro_word_target])

    h2_estimate_ok = round((len(h2_list) / (word_count / 250)), 2) if word_count else 0.0

    readability_verdict = "Easy" if flesch_kincaid_grade < 8 else "Moderate" if flesch_kincaid_grade < 12 else "Difficult"

    analysis = {
        "keyword_analysis": {
            "keyword_in_title": _contains_variant(title_tag, variants) if variants else False,
            "keyword_in_meta": _contains_variant(meta_description, variants) if variants else False,
            "keyword_in_h1": any(_contains_variant(h1, variants) for h1 in h1_list) if variants else False,
            "keyword_in_h2s": keyword_in_h2s,
            "keyword_density": keyword_density,
            "keyword_in_first_100_words": _contains_variant(first_100, variants) if variants else False,
        },
        "content_structure": {
            "has_single_h1": len(h1_list) == 1,
            "heading_hierarchy_valid": _heading_hierarchy_valid(heading_hierarchy),
            "h2_count": len(h2_list),
            "h3_count": len(h3_list),
            "heading_to_content_ratio": h2_estimate_ok,
            "has_introduction": len(introduction_segment.split()) >= 60,
            "has_conclusion": _section_heading_contains(all_headings, CONCLUSION_TERMS),
            "has_key_takeaways": _section_heading_contains(all_headings, TAKEAWAY_TERMS),
            "has_sources_section": _section_heading_contains(all_headings, SOURCES_TERMS),
        },
        "readability": {
            "flesch_reading_ease": flesch_reading_ease,
            "flesch_kincaid_grade": flesch_kincaid_grade,
            "avg_sentence_length": _estimate_avg_sentence_length(body_text),
            "avg_paragraph_length": _estimate_avg_paragraph_length(raw_html if "\n\n" in raw_html else body_text),
            "readability_verdict": readability_verdict,
        },
        "links": {
            "internal_link_count": int(extracted.get("internal_link_count", 0) or 0),
            "external_link_count": int(extracted.get("external_link_count", 0) or 0),
            "total_link_count": total_links,
            "link_ratio": link_ratio,
            "gov_edu_source_count": int(extracted.get("gov_edu_count", 0) or 0),
            "gov_edu_sources_list": extracted.get("gov_edu_sources", []) or [],
            "has_authority_sources": int(extracted.get("gov_edu_count", 0) or 0) > 0,
            "overlinking_flag": total_links > (word_count / 100) if word_count else False,
        },
        "images": {
            "image_count": image_count,
            "images_missing_alt_count": missing_alt,
            "images_missing_alt_percentage": round((missing_alt / image_count) * 100, 2) if image_count else 0.0,
        },
        "meta": {
            "title_length": len(title_tag),
            "title_length_ok": 30 <= len(title_tag) <= 60,
            "meta_description_length": len(meta_description),
            "meta_description_length_ok": 120 <= len(meta_description) <= 160,
        },
        "summary": {
            "word_count": word_count,
            "keyword_occurrences": keyword_occurrences,
            "keyword": keyword,
        },
    }

    return analysis


def compare_rule_analysis(my_analysis: dict[str, Any], competitor_analyses: list[dict[str, Any]]) -> dict[str, Any]:
    if not my_analysis or my_analysis.get("error"):
        return {"error": my_analysis.get("error", "No analysis available for your article.")}

    competitors = [a for a in competitor_analyses if a and not a.get("error")]
    if not competitors:
        return {"note": "No valid competitor analyses available for comparison."}

    my_word_count = my_analysis.get("summary", {}).get("word_count", 0)
    avg_comp_word_count = sum(c.get("summary", {}).get("word_count", 0) for c in competitors) / len(competitors)

    my_h2 = my_analysis.get("content_structure", {}).get("h2_count", 0)
    my_h3 = my_analysis.get("content_structure", {}).get("h3_count", 0)
    avg_comp_h2 = sum(c.get("content_structure", {}).get("h2_count", 0) for c in competitors) / len(competitors)
    avg_comp_h3 = sum(c.get("content_structure", {}).get("h3_count", 0) for c in competitors) / len(competitors)

    my_links = my_analysis.get("links", {}).get("total_link_count", 0)
    avg_comp_links = sum(c.get("links", {}).get("total_link_count", 0) for c in competitors) / len(competitors)

    my_grade = my_analysis.get("readability", {}).get("flesch_kincaid_grade", 0)
    avg_comp_grade = sum(c.get("readability", {}).get("flesch_kincaid_grade", 0) for c in competitors) / len(competitors)

    weaknesses = []
    if my_word_count < avg_comp_word_count:
        weaknesses.append("Your article is shorter than competitors on average.")
    if my_h2 < avg_comp_h2:
        weaknesses.append("Your article uses fewer H2 headings than competitors.")
    if my_h3 < avg_comp_h3:
        weaknesses.append("Your article uses fewer H3 headings than competitors.")
    if my_links < avg_comp_links:
        weaknesses.append("Your article has fewer total links than competitors.")
    if my_grade > avg_comp_grade:
        weaknesses.append("Your readability grade level is higher (harder to read) than competitors.")

    return {
        "word_count_comparison": {
            "my_word_count": my_word_count,
            "avg_competitor_word_count": round(avg_comp_word_count, 2),
            "status": "weaker" if my_word_count < avg_comp_word_count else "strong_or_equal",
        },
        "heading_comparison": {
            "my_h2_count": my_h2,
            "avg_competitor_h2_count": round(avg_comp_h2, 2),
            "my_h3_count": my_h3,
            "avg_competitor_h3_count": round(avg_comp_h3, 2),
        },
        "link_comparison": {
            "my_total_links": my_links,
            "avg_competitor_total_links": round(avg_comp_links, 2),
        },
        "readability_comparison": {
            "my_flesch_kincaid_grade": my_grade,
            "avg_competitor_flesch_kincaid_grade": round(avg_comp_grade, 2),
        },
        "weaker_areas": weaknesses,
    }
