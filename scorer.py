from __future__ import annotations

from typing import Any


def _rating_from_score(score: int) -> str:
    if score >= 90:
        return "Excellent"
    if score >= 80:
        return "Very Good"
    if score >= 70:
        return "Good"
    if score >= 60:
        return "Fair"
    return "Poor"


def _score_keyword(rule_results: dict[str, Any], ai_results: dict[str, Any] | None) -> dict[str, Any]:
    data = rule_results.get("keyword_analysis", {})
    score = 0
    details: list[dict[str, Any]] = []

    checks = [
        ("Keyword in title", bool(data.get("keyword_in_title")), 3),
        ("Keyword in meta description", bool(data.get("keyword_in_meta")), 2),
        ("Keyword in H1", bool(data.get("keyword_in_h1")), 3),
        ("Keyword in first 100 words", bool(data.get("keyword_in_first_100_words")), 2),
    ]
    for label, ok, points in checks:
        earned = points if ok else 0
        score += earned
        details.append({"item": label, "earned": earned, "max": points})

    density = float(data.get("keyword_density", 0) or 0)
    density_points = 3 if 0.5 <= density <= 2.5 else 0
    score += density_points
    details.append({"item": "Keyword density (0.5%-2.5%)", "earned": density_points, "max": 3})

    missing_topics = []
    if ai_results and not ai_results.get("error"):
        missing_topics = ai_results.get("keyword_gap_analysis", {}).get("missing_topics", []) or []

    miss_count = len(missing_topics)
    if not ai_results or ai_results.get("error"):
        ai_points = 4
        details.append({"item": "AI keyword gap (fallback without AI)", "earned": ai_points, "max": 7})
    elif miss_count <= 2:
        ai_points = 7
        details.append({"item": "AI keyword gap (0-2 missing topics)", "earned": ai_points, "max": 7})
    elif miss_count <= 4:
        ai_points = 5
        details.append({"item": "AI keyword gap (3-4 missing topics)", "earned": ai_points, "max": 7})
    elif miss_count <= 6:
        ai_points = 3
        details.append({"item": "AI keyword gap (5-6 missing topics)", "earned": ai_points, "max": 7})
    else:
        ai_points = 0
        details.append({"item": "AI keyword gap (7+ missing topics)", "earned": ai_points, "max": 7})

    score += ai_points
    return {"score": min(score, 20), "max": 20, "details": details}


def _score_content_structure(rule_results: dict[str, Any], ai_results: dict[str, Any] | None) -> dict[str, Any]:
    data = rule_results.get("content_structure", {})
    score = 0
    details: list[dict[str, Any]] = []

    checks = [
        ("Single H1", bool(data.get("has_single_h1")), 2),
        ("Valid heading hierarchy", bool(data.get("heading_hierarchy_valid")), 3),
        ("Has introduction", bool(data.get("has_introduction")), 2),
        ("Has conclusion", bool(data.get("has_conclusion")), 2),
        ("Has key takeaways", bool(data.get("has_key_takeaways")), 2),
    ]
    for label, ok, points in checks:
        earned = points if ok else 0
        score += earned
        details.append({"item": label, "earned": earned, "max": points})

    rating_points = {"excellent": 4, "good": 3, "fair": 1, "poor": 0}
    ai_rating = "fair"
    if ai_results and not ai_results.get("error"):
        ai_rating = str(ai_results.get("heading_quality", {}).get("overall_rating", "fair")).lower()
    earned_ai = rating_points.get(ai_rating, 1)
    score += earned_ai
    details.append({"item": f"AI heading quality ({ai_rating})", "earned": earned_ai, "max": 4})

    return {"score": min(score, 15), "max": 15, "details": details}


def _score_intent(ai_results: dict[str, Any] | None) -> dict[str, Any]:
    details: list[dict[str, Any]] = []
    if not ai_results or ai_results.get("error"):
        details.append({"item": "No AI intent check (neutral)", "earned": 8, "max": 15})
        return {"score": 8, "max": 15, "details": details}

    confidence = str(ai_results.get("user_intent", {}).get("confidence", "low")).lower()
    explanation = str(ai_results.get("user_intent", {}).get("explanation", "")).lower()
    clear = any(token in explanation for token in ["because", "based", "evidence", "signals"])

    if confidence == "high" and clear:
        score = 15
    elif confidence == "medium":
        score = 10
    else:
        score = 5

    details.append({"item": f"AI intent confidence ({confidence})", "earned": score, "max": 15})
    return {"score": score, "max": 15, "details": details}


def _score_readability(rule_results: dict[str, Any]) -> dict[str, Any]:
    read = rule_results.get("readability", {})
    meta = rule_results.get("meta", {})
    images = rule_results.get("images", {})
    summary = rule_results.get("summary", {})

    details: list[dict[str, Any]] = []
    score = 0

    grade = float(read.get("flesch_kincaid_grade", 0) or 0)
    grade_pts = 5 if 6 <= grade <= 10 else 2
    score += grade_pts
    details.append({"item": "Flesch-Kincaid grade range", "earned": grade_pts, "max": 5})

    para_len = float(read.get("avg_paragraph_length", 0) or 0)
    para_pts = 3 if 1.5 <= para_len <= 6 else 1
    score += para_pts
    details.append({"item": "Reasonable paragraph length", "earned": para_pts, "max": 3})

    wc = int(summary.get("word_count", 0) or 0)
    wc_pts = 2 if wc >= 500 else 0
    score += wc_pts
    details.append({"item": "Word count 500+", "earned": wc_pts, "max": 2})

    image_count = int(images.get("image_count", 0) or 0)
    missing_alt = int(images.get("images_missing_alt_count", 0) or 0)
    if image_count > 0 and missing_alt == 0:
        img_pts = 3
    elif image_count > 0:
        img_pts = 1
    else:
        img_pts = 0
    score += img_pts
    details.append({"item": "Images present with alt text", "earned": img_pts, "max": 3})

    title_pts = 1 if bool(meta.get("title_length_ok")) else 0
    meta_pts = 1 if bool(meta.get("meta_description_length_ok")) else 0
    score += title_pts + meta_pts
    details.append({"item": "Meta title length", "earned": title_pts, "max": 1})
    details.append({"item": "Meta description length", "earned": meta_pts, "max": 1})

    return {"score": min(score, 15), "max": 15, "details": details}


def _score_source_authority(rule_results: dict[str, Any]) -> dict[str, Any]:
    links = rule_results.get("links", {})
    structure = rule_results.get("content_structure", {})
    gov_count = int(links.get("gov_edu_source_count", 0) or 0)

    if gov_count <= 0:
        base = 0
    elif gov_count == 1:
        base = 4
    elif gov_count == 2:
        base = 7
    else:
        base = 10

    bonus = 3 if bool(structure.get("has_sources_section")) else 0
    total = min(10, base + bonus)
    return {
        "score": total,
        "max": 10,
        "details": [
            {"item": ".gov/.edu authority sources", "earned": base, "max": 10},
            {"item": "Sources/references section bonus", "earned": min(3, max(0, total - base)), "max": 3},
        ],
    }


def _score_link_profile(rule_results: dict[str, Any]) -> dict[str, Any]:
    links = rule_results.get("links", {})
    internal = int(links.get("internal_link_count", 0) or 0)
    external = int(links.get("external_link_count", 0) or 0)
    over = bool(links.get("overlinking_flag"))

    ratio_ok = False
    if external > 0:
        ratio = internal / external
        ratio_ok = 0.5 <= ratio <= 3

    details = [
        {"item": "Has internal links", "earned": 3 if internal > 0 else 0, "max": 3},
        {"item": "Has external links", "earned": 3 if external > 0 else 0, "max": 3},
        {"item": "No overlinking", "earned": 2 if not over else 0, "max": 2},
        {"item": "Balanced internal/external ratio", "earned": 2 if ratio_ok else 0, "max": 2},
    ]
    score = sum(d["earned"] for d in details)
    return {"score": min(score, 10), "max": 10, "details": details}


def _score_depth(rule_results: dict[str, Any], ai_results: dict[str, Any] | None) -> dict[str, Any]:
    if ai_results and not ai_results.get("error"):
        depth = str(ai_results.get("content_depth", {}).get("vs_competitors", "comparable")).lower()
        mapping = {"deeper": 10, "comparable": 7, "shallower": 3}
        score = mapping.get(depth, 5)
        return {"score": score, "max": 10, "details": [{"item": f"AI depth rating ({depth})", "earned": score, "max": 10}]}

    my_words = int(rule_results.get("summary", {}).get("word_count", 0) or 0)
    comp_avg = float(rule_results.get("comparison_context", {}).get("avg_competitor_word_count", 0) or 0)
    if comp_avg <= 0:
        score = 5
        label = "No competitor average word count"
    else:
        ratio = my_words / comp_avg
        if ratio >= 1.2:
            score = 8
            label = "20%+ longer than competitors"
        elif ratio >= 0.85:
            score = 5
            label = "Similar length to competitors"
        else:
            score = 3
            label = "Shorter than competitors"
    return {"score": score, "max": 10, "details": [{"item": label, "earned": score, "max": 10}]}


def _score_geo(ai_results: dict[str, Any] | None) -> dict[str, Any]:
    if not ai_results or ai_results.get("error"):
        return {"score": 3, "max": 5, "details": [{"item": "No AI geo analysis (neutral)", "earned": 3, "max": 5}]}

    scope = str(ai_results.get("geo_targeting", {}).get("scope", "unclear")).lower()
    score = 5 if scope != "unclear" else 2
    return {"score": score, "max": 5, "details": [{"item": f"Geo scope clarity ({scope})", "earned": score, "max": 5}]}


def calculate_score(rule_results: dict[str, Any], ai_results: dict[str, Any] | None) -> dict[str, Any]:
    """Computes weighted quality score out of 100 using rule + optional AI results."""
    categories = {
        "keyword_coverage": _score_keyword(rule_results, ai_results),
        "content_structure": _score_content_structure(rule_results, ai_results),
        "user_intent_alignment": _score_intent(ai_results),
        "readability_presentation": _score_readability(rule_results),
        "source_authority": _score_source_authority(rule_results),
        "link_profile": _score_link_profile(rule_results),
        "depth_vs_competitors": _score_depth(rule_results, ai_results),
        "geo_targeting_clarity": _score_geo(ai_results),
    }

    total = int(round(sum(v["score"] for v in categories.values())))
    total = max(0, min(100, total))

    lost_points = []
    for cat_key, cat in categories.items():
        for d in cat.get("details", []):
            max_pts = d.get("max", 0)
            earned = d.get("earned", 0)
            lost = max_pts - earned
            if lost > 0:
                lost_points.append((lost, cat_key, d.get("item", "")))

    lost_points.sort(reverse=True, key=lambda x: x[0])
    top_improvements = [f"{item} ({cat.replace('_', ' ')})" for _, cat, item in lost_points[:8]]

    return {
        "total_score": total,
        "rating": _rating_from_score(total),
        "category_scores": categories,
        "top_improvements": top_improvements,
    }
