from __future__ import annotations

import json
from typing import Any


MY_WORD_LIMIT = 4000
COMP_WORD_LIMIT = 3000


def _truncate_words(text: str, max_words: int) -> str:
    words = (text or "").split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words])


def _compact_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def build_analysis_prompt(
    my_content: dict[str, Any],
    competitor_contents: list[dict[str, Any]],
    keyword: str,
    rule_results: dict[str, Any],
) -> str:
    """Builds a comprehensive Gemini prompt with extracted content + rule results."""
    my_text = _truncate_words(my_content.get("body_text", "") or "", MY_WORD_LIMIT)

    competitor_blocks: list[dict[str, Any]] = []
    for idx, content in enumerate(competitor_contents, start=1):
        competitor_blocks.append(
            {
                "name": f"Competitor {idx}",
                "title": content.get("title_tag", ""),
                "headings": content.get("heading_hierarchy", []),
                "body_text": _truncate_words(content.get("body_text", "") or "", COMP_WORD_LIMIT),
            }
        )

    prompt_payload = {
        "target_keyword": keyword or "",
        "user_article": {
            "title": my_content.get("title_tag", ""),
            "meta_description": my_content.get("meta_description", ""),
            "headings": my_content.get("heading_hierarchy", []),
            "body_text": my_text,
            "word_count": my_content.get("word_count", 0),
        },
        "competitor_articles": competitor_blocks,
        "rule_based_results": rule_results,
    }

    schema = {
        "user_intent": {
            "classification": "informational | transactional | commercial_investigation | navigational",
            "confidence": "high | medium | low",
            "explanation": "Brief explanation of why",
        },
        "target_audience": {
            "expertise_level": "beginner | intermediate | advanced | professional",
            "audience_type": "consumer | b2b | b2c | academic | legal",
            "explanation": "Brief explanation",
        },
        "geo_targeting": {
            "scope": "global | us_national | us_state_specific | other_country | unclear",
            "detected_region": "String or null",
            "explanation": "Brief explanation of signals found",
        },
        "keyword_gap_analysis": {
            "missing_topics": [
                "List of semantic topics competitors cover that the user's article doesn't"
            ],
            "missing_keywords": [
                "Specific keywords/phrases found in competitors but absent in user's article"
            ],
            "over_covered_topics": [
                "Topics the user covers more than competitors — potential strengths"
            ],
        },
        "heading_quality": {
            "overall_rating": "poor | fair | good | excellent",
            "vague_headings": ["List of user's headings that are too generic"],
            "suggested_improvements": [
                {"current": "Current heading text", "suggested": "Better version"}
            ],
        },
        "content_depth": {
            "vs_competitors": "shallower | comparable | deeper",
            "gaps": ["Specific areas where competitors go deeper"],
            "strengths": ["Areas where user's content is stronger"],
        },
        "structural_suggestions": {
            "missing_sections": ["Sections that should be added based on competitor analysis"],
            "reorder_suggestions": ["Any sections that would work better in a different order"],
            "remove_suggestions": ["Any sections that seem unnecessary or redundant"],
        },
        "overall_ai_assessment": {
            "summary": "2-3 sentence overall assessment",
            "top_3_priorities": ["The 3 most impactful changes to make"],
        },
    }

    return (
        "You are an SEO content strategist. Analyze the dataset below and return ONLY JSON.\n\n"
        "CRITICAL INSTRUCTIONS:\n"
        "1) Respond ONLY with valid JSON. No markdown. No code blocks. No explanation outside the JSON.\n"
        "2) Base your analysis on observable evidence from the text. Do not guess.\n"
        "3) For keyword_gap_analysis, focus on SEMANTIC topics and concepts, not just exact keyword matches.\n"
        "4) For geo_targeting, look for: currency symbols, phone formats, state/city names, legal references, "
        "spellings (color vs colour), regulatory mentions.\n"
        "5) Use concise, actionable outputs and avoid repetition.\n\n"
        "Return JSON that matches this exact structure (same top-level keys and nested keys):\n"
        f"{_compact_json(schema)}\n\n"
        "DATASET:\n"
        f"{_compact_json(prompt_payload)}"
    )
