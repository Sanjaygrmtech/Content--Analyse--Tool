from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from analyzer_ai import configure_gemini, run_ai_analysis
from analyzer_rules import compare_rule_analysis, run_rule_analysis
from scraper import parse_pasted_content, scrape_url


st.set_page_config(page_title="Content Quality Analyzer", layout="wide")

st.title("Content Quality Analyzer")
st.subheader(
    "Phase 1 + Rule + AI Analysis: benchmark your article vs competitors for SEO structure, readability, gaps, and optimization priorities."
)

with st.sidebar:
    st.header("Inputs")
    primary_keyword = st.text_input("Primary Target Keyword", placeholder="e.g., enterprise seo strategy")
    gemini_api_key = st.text_input("Gemini API Key", type="password", placeholder="Paste your Gemini API key")
    input_method = st.radio("Input method", ["Enter URLs", "Paste Content"])

st.caption(f"Primary keyword for context: **{primary_keyword or 'Not provided'}**")


def _status_chip(ok: bool, good_text: str = "Good", bad_text: str = "Issue"):
    st.markdown(f":green[{good_text}]" if ok else f":red[{bad_text}]")


def _warning_chip(flag: bool, warn_text: str, ok_text: str = "Looks good"):
    st.markdown(f":orange[{warn_text}]" if flag else f":green[{ok_text}]")


def _show_extraction_block(label: str, result: dict[str, Any]):
    if result.get("error"):
        st.error(f"{label}: {result['error']}")
        return

    st.success(f"{label}: Content extracted successfully")
    with st.expander(f"{label} — Raw extraction debug", expanded=False):
        st.write(f"**Word count:** {result.get('word_count', 0)}")
        st.write("**Heading hierarchy:**")
        st.json(result.get("heading_hierarchy", []))
        st.write("**Link counts:**")
        st.write(
            {
                "internal_link_count": result.get("internal_link_count", 0),
                "external_link_count": result.get("external_link_count", 0),
                "gov_edu_count": result.get("gov_edu_count", 0),
            }
        )
        st.write("**.gov/.edu sources found:**")
        st.json(result.get("gov_edu_sources", []))
        if result.get("note"):
            st.info(result["note"])


def _show_rule_analysis(label: str, analysis: dict[str, Any]):
    st.markdown(f"## {label} — Rule-Based Analysis")
    if analysis.get("error"):
        st.error(f"{label}: {analysis['error']}")
        return

    keyword = analysis.get("keyword_analysis", {})
    structure = analysis.get("content_structure", {})
    readability = analysis.get("readability", {})
    links = analysis.get("links", {})
    images = analysis.get("images", {})
    meta = analysis.get("meta", {})

    with st.expander("Keyword Analysis", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Keyword in Title", "Yes" if keyword.get("keyword_in_title") else "No")
            _status_chip(bool(keyword.get("keyword_in_title")), "Present", "Missing")
        with c2:
            st.metric("Keyword in Meta", "Yes" if keyword.get("keyword_in_meta") else "No")
            _status_chip(bool(keyword.get("keyword_in_meta")), "Present", "Missing")
        with c3:
            st.metric("Keyword in H1", "Yes" if keyword.get("keyword_in_h1") else "No")
            _status_chip(bool(keyword.get("keyword_in_h1")), "Present", "Missing")

        c4, c5, c6 = st.columns(3)
        c4.metric("H2s with Keyword", keyword.get("keyword_in_h2s", 0))
        c5.metric("Keyword Density (%)", keyword.get("keyword_density", 0.0))
        c6.metric("Keyword in First 100 Words", "Yes" if keyword.get("keyword_in_first_100_words") else "No")

    with st.expander("Content Structure", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Single H1", "Yes" if structure.get("has_single_h1") else "No")
        _status_chip(bool(structure.get("has_single_h1")), "Good", "Issue")
        c2.metric("Hierarchy Valid", "Yes" if structure.get("heading_hierarchy_valid") else "No")
        _status_chip(bool(structure.get("heading_hierarchy_valid")), "Good", "Issue")
        c3.metric("H2 Count", structure.get("h2_count", 0))
        c4.metric("H3 Count", structure.get("h3_count", 0))

        ratio = structure.get("heading_to_content_ratio", 0.0)
        st.metric("Heading-to-Content Ratio Score", ratio)
        _warning_chip(ratio < 0.8, "Add more H2 headings for long-form readability")

        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Has Introduction", "Yes" if structure.get("has_introduction") else "No")
        d2.metric("Has Conclusion", "Yes" if structure.get("has_conclusion") else "No")
        d3.metric("Has Key Takeaways", "Yes" if structure.get("has_key_takeaways") else "No")
        d4.metric("Has Sources Section", "Yes" if structure.get("has_sources_section") else "No")

    with st.expander("Readability", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Flesch Reading Ease", readability.get("flesch_reading_ease", 0.0))
        c2.metric("Flesch-Kincaid Grade", readability.get("flesch_kincaid_grade", 0.0))
        c3.metric("Avg Sentence Length", readability.get("avg_sentence_length", 0.0))
        c4.metric("Avg Paragraph Length", readability.get("avg_paragraph_length", 0.0))
        verdict = readability.get("readability_verdict", "Unknown")
        if verdict == "Easy":
            st.markdown(f"Verdict: :green[{verdict}]")
        elif verdict == "Moderate":
            st.markdown(f"Verdict: :orange[{verdict}]")
        else:
            st.markdown(f"Verdict: :red[{verdict}]")

    with st.expander("Links & Sources", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Internal Links", links.get("internal_link_count", 0))
        c2.metric("External Links", links.get("external_link_count", 0))
        c3.metric("Total Links", links.get("total_link_count", 0))
        c4.metric("Internal:External", links.get("link_ratio", "0:0"))

        c5, c6 = st.columns(2)
        c5.metric(".gov/.edu Sources", links.get("gov_edu_source_count", 0))
        c6.metric("Has Authority Sources", "Yes" if links.get("has_authority_sources") else "No")
        _warning_chip(bool(links.get("overlinking_flag")), "Possible overlinking (>1 link per 100 words)")

        st.write("**Authority source URLs:**")
        st.json(links.get("gov_edu_sources_list", []))

    with st.expander("Meta Tags", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Title Length", meta.get("title_length", 0))
        c2.metric("Title Length OK", "Yes" if meta.get("title_length_ok") else "No")
        _warning_chip(not bool(meta.get("title_length_ok")), "Adjust title to 30-60 chars")
        c3.metric("Meta Description Length", meta.get("meta_description_length", 0))
        c4.metric("Meta Description Length OK", "Yes" if meta.get("meta_description_length_ok") else "No")
        _warning_chip(not bool(meta.get("meta_description_length_ok")), "Adjust meta to 120-160 chars")

    with st.expander("Image Analysis", expanded=False):
        i1, i2, i3 = st.columns(3)
        i1.metric("Image Count", images.get("image_count", 0))
        i2.metric("Missing Alt Count", images.get("images_missing_alt_count", 0))
        i3.metric("Missing Alt (%)", images.get("images_missing_alt_percentage", 0.0))


def _comparison_table(my_label: str, my_analysis: dict[str, Any], competitor_map: dict[str, dict[str, Any]]):
    rows = []

    def _get(a: dict[str, Any], *path: str, default: Any = 0):
        current = a
        for p in path:
            if not isinstance(current, dict):
                return default
            current = current.get(p, default)
        return current

    entries = {my_label: my_analysis, **competitor_map}
    for name, analysis in entries.items():
        if analysis.get("error"):
            continue
        rows.append(
            {
                "Article": name,
                "Word Count": _get(analysis, "summary", "word_count"),
                "H2 Count": _get(analysis, "content_structure", "h2_count"),
                "H3 Count": _get(analysis, "content_structure", "h3_count"),
                "Total Links": _get(analysis, "links", "total_link_count"),
                "Flesch-Kincaid Grade": _get(analysis, "readability", "flesch_kincaid_grade"),
                "Keyword in Title": _get(analysis, "keyword_analysis", "keyword_in_title"),
            }
        )

    if not rows:
        st.warning("No valid analyses to compare yet.")
        return

    st.markdown("## Comparison Table")
    st.dataframe(pd.DataFrame(rows), use_container_width=True)


def _render_badge(value: str, good: set[str] | None = None, warn: set[str] | None = None):
    good = good or set()
    warn = warn or set()
    value = value or "unknown"
    if value in good:
        st.markdown(f":green[{value}]")
    elif value in warn:
        st.markdown(f":orange[{value}]")
    else:
        st.markdown(f":red[{value}]")


def _show_ai_analysis(ai_result: dict[str, Any]):
    st.markdown("## AI Analysis (Gemini)")
    if ai_result.get("error"):
        st.error(ai_result["error"])
        return

    intent = ai_result.get("user_intent", {})
    audience = ai_result.get("target_audience", {})
    geo = ai_result.get("geo_targeting", {})
    gaps = ai_result.get("keyword_gap_analysis", {})
    heading = ai_result.get("heading_quality", {})
    depth = ai_result.get("content_depth", {})
    structure = ai_result.get("structural_suggestions", {})
    overall = ai_result.get("overall_ai_assessment", {})

    with st.expander("User Intent & Audience", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.markdown("**Intent**")
        _render_badge(intent.get("classification", ""), good={"informational", "commercial_investigation"}, warn={"transactional"})
        c2.markdown("**Confidence**")
        _render_badge(intent.get("confidence", ""), good={"high"}, warn={"medium"})
        c3.markdown("**Audience Expertise**")
        _render_badge(audience.get("expertise_level", ""), good={"intermediate", "advanced", "professional"}, warn={"beginner"})
        st.write(f"Intent rationale: {intent.get('explanation', 'N/A')}")
        st.write(f"Audience type: {audience.get('audience_type', 'N/A')}")
        st.write(f"Audience rationale: {audience.get('explanation', 'N/A')}")

    with st.expander("Geo-Targeting", expanded=False):
        c1, c2 = st.columns(2)
        c1.markdown("**Detected Scope**")
        _render_badge(geo.get("scope", ""), good={"global", "us_national"}, warn={"unclear"})
        c2.write(f"Detected region: {geo.get('detected_region')}")
        st.write(geo.get("explanation", "No geo signals provided."))

    with st.expander("Keyword Gaps", expanded=False):
        st.markdown("**Missing semantic topics to add**")
        for topic in gaps.get("missing_topics", []) or []:
            st.markdown(f"- :red[{topic}]")
        st.markdown("**Missing keyword phrases**")
        for kw in gaps.get("missing_keywords", []) or []:
            st.markdown(f"- :orange[{kw}]")
        st.markdown("**Over-covered topics (potential strengths)**")
        for topic in gaps.get("over_covered_topics", []) or []:
            st.markdown(f"- :green[{topic}]")

    with st.expander("Heading Quality", expanded=False):
        _render_badge(heading.get("overall_rating", ""), good={"good", "excellent"}, warn={"fair"})
        vague = heading.get("vague_headings", []) or []
        if vague:
            st.write("**Headings to tighten:**")
            for item in vague:
                st.markdown(f"- :orange[{item}]")

        improvements = heading.get("suggested_improvements", []) or []
        if improvements:
            table = pd.DataFrame(improvements)
            st.write("**Current vs Suggested headings**")
            st.dataframe(table, use_container_width=True)

    with st.expander("Content Depth", expanded=False):
        c1, c2 = st.columns(2)
        c1.write("**Depth vs competitors**")
        _render_badge(depth.get("vs_competitors", ""), good={"deeper", "comparable"}, warn={"shallower"})
        c2.write("**Strength areas**")
        for item in depth.get("strengths", []) or []:
            c2.markdown(f"- :green[{item}]")
        st.write("**Depth gaps to close**")
        for item in depth.get("gaps", []) or []:
            st.markdown(f"- :red[{item}]")

    with st.expander("AI Recommendations", expanded=True):
        st.markdown("### Top 3 Priorities")
        priorities = overall.get("top_3_priorities", []) or []
        for idx, p in enumerate(priorities, start=1):
            st.markdown(f"{idx}. :red[{p}]")

        st.markdown("### Structural Suggestions")
        for section_name, key in [
            ("Missing Sections", "missing_sections"),
            ("Reorder Suggestions", "reorder_suggestions"),
            ("Remove Suggestions", "remove_suggestions"),
        ]:
            st.write(f"**{section_name}:**")
            items = structure.get(key, []) or []
            if not items:
                st.markdown("- None")
            for item in items:
                st.markdown(f"- :orange[{item}]")

        st.markdown("### Overall Assessment")
        st.info(overall.get("summary", "No summary returned."))


def _process_and_render(results: dict[str, dict[str, Any]], labels: list[str]):
    st.markdown("### Extraction Results")
    for label in labels:
        _show_extraction_block(label, results[label])

    analyses: dict[str, dict[str, Any]] = {}
    with st.spinner("Running rule-based analysis..."):
        for label in labels:
            analyses[label] = run_rule_analysis(results[label], primary_keyword)

    st.markdown("---")
    _show_rule_analysis("Your Article", analyses.get("Your Article", {"error": "Missing analysis"}))

    for label in labels:
        if label != "Your Article":
            _show_rule_analysis(label, analyses[label])

    comparison = compare_rule_analysis(
        analyses.get("Your Article", {"error": "Missing analysis"}),
        [analyses[label] for label in labels if label.startswith("Competitor")],
    )

    st.markdown("---")
    st.markdown("## Competitive Gaps")
    if comparison.get("error"):
        st.error(comparison["error"])
    else:
        weaker = comparison.get("weaker_areas", [])
        if weaker:
            for item in weaker:
                st.markdown(f"- :red[{item}]")
        elif comparison.get("note"):
            st.info(comparison["note"])
        else:
            st.success("No clear weak areas detected based on available rule checks.")

    competitor_map = {k: v for k, v in analyses.items() if k.startswith("Competitor")}
    _comparison_table("Your Article", analyses.get("Your Article", {}), competitor_map)

    st.markdown("---")
    if not gemini_api_key.strip():
        st.info("AI analysis is optional. Add a Gemini API Key in the sidebar to unlock AI insights.")
        return

    try:
        configure_gemini(gemini_api_key)
    except Exception as exc:
        st.error(f"Unable to configure Gemini: {exc}")
        return

    my_content = results.get("Your Article", {})
    competitor_contents = [results[label] for label in labels if label.startswith("Competitor") and not results[label].get("error")]
    ai_payload = {
        "my_rule_analysis": analyses.get("Your Article", {}),
        "competitor_rule_analysis": {label: analyses[label] for label in labels if label.startswith("Competitor")},
        "comparison": comparison,
    }

    with st.spinner("Running AI analysis with Gemini..."):
        ai_result = run_ai_analysis(my_content, competitor_contents, primary_keyword, ai_payload)

    _show_ai_analysis(ai_result)


if input_method == "Enter URLs":
    your_url = st.text_input("Your Article URL", placeholder="https://example.com/your-article")
    competitor_url_1 = st.text_input("Competitor URL 1", placeholder="https://competitor.com/article")
    competitor_url_2 = st.text_input("Competitor URL 2 (optional)", placeholder="https://competitor2.com/article")
    competitor_url_3 = st.text_input("Competitor URL 3 (optional)", placeholder="https://competitor3.com/article")

    if st.button("Analyze", type="primary"):
        if not competitor_url_1.strip():
            st.error("Competitor URL 1 is required.")
        elif not your_url.strip():
            st.error("Your Article URL is required.")
        else:
            url_inputs = [
                ("Your Article", your_url.strip()),
                ("Competitor 1", competitor_url_1.strip()),
                ("Competitor 2", competitor_url_2.strip()),
                ("Competitor 3", competitor_url_3.strip()),
            ]
            provided = [(label, url) for label, url in url_inputs if url]

            extracted_results: dict[str, dict[str, Any]] = {}
            with st.spinner("Scraping content..."):
                for label, url in provided:
                    extracted_results[label] = scrape_url(url)

            _process_and_render(extracted_results, [label for label, _ in provided])

else:
    your_content = st.text_area(
        "Your Article Content (HTML or plain text)",
        height=220,
        placeholder="Paste your article HTML or plain text here...",
    )
    competitor_content_1 = st.text_area("Competitor Content 1", height=220, placeholder="Paste competitor content here...")
    competitor_content_2 = st.text_area(
        "Competitor Content 2 (optional)",
        height=220,
        placeholder="Paste optional second competitor content here...",
    )

    if st.button("Analyze", type="primary"):
        if not your_content.strip():
            st.error("Your Article Content is required.")
        elif not competitor_content_1.strip():
            st.error("Competitor Content 1 is required.")
        else:
            content_inputs = [
                ("Your Article", your_content.strip()),
                ("Competitor 1", competitor_content_1.strip()),
                ("Competitor 2", competitor_content_2.strip()),
            ]
            provided = [(label, content) for label, content in content_inputs if content]

            extracted_results: dict[str, dict[str, Any]] = {}
            with st.spinner("Scraping content..."):
                for label, content in provided:
                    extracted_results[label] = parse_pasted_content(content)

            _process_and_render(extracted_results, [label for label, _ in provided])
