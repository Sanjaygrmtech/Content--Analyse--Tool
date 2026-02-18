from __future__ import annotations

import streamlit as st
from typing import Any

from scraper import parse_pasted_content, scrape_url
from analyzer_rules import run_rule_analysis, compare_rule_analysis


st.set_page_config(page_title="Content Quality Analyzer", layout="wide")

st.title("Content Quality Analyzer")
st.subheader(
    "Collect and inspect content structure, run rule-based analysis, and compare against competitors."
)

with st.sidebar:
    st.header("Inputs")
    primary_keyword = st.text_input("Primary Target Keyword", placeholder="e.g., california eviction relocation payouts")
    input_method = st.radio("Input method", ["Enter URLs", "Paste Content"])

st.caption(f"Primary keyword for context: **{primary_keyword or 'Not provided'}**")


# --- Helper: color indicator ---
def _status_icon(good: bool) -> str:
    return "✅" if good else "❌"

def _warning_icon(value: bool) -> str:
    return "⚠️" if value else "✅"


# --- Helper: show extraction block ---
def _show_extraction_block(label: str, result: dict):
    if result.get("error"):
        st.error(f"{label}: {result['error']}")
        return
    st.success(f"{label}: Content extracted successfully")
    with st.expander(f"{label} — Extraction details", expanded=False):
        st.write(f"**Word count:** {result.get('word_count', 0)}")
        st.write("**Heading hierarchy:**")
        st.json(result.get("heading_hierarchy", []))
        st.write("**Link counts:**")
        st.write({
            "internal_link_count": result.get("internal_link_count", 0),
            "external_link_count": result.get("external_link_count", 0),
            "gov_edu_count": result.get("gov_edu_count", 0),
        })
        st.write("**.gov/.edu sources found:**")
        st.json(result.get("gov_edu_sources", []))
        note = result.get("note")
        if note:
            st.info(note)


# --- Helper: show rule-based analysis ---
def _show_rule_analysis(label: str, analysis: dict[str, Any]):
    if analysis.get("error"):
        st.error(f"{label} analysis error: {analysis['error']}")
        return

    st.markdown(f"### 📊 Rule-Based Analysis: {label}")

    # --- Keyword Analysis ---
    with st.expander("🔑 Keyword Analysis", expanded=True):
        kw = analysis.get("keyword_analysis", {})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Keyword Density", f"{kw.get('keyword_density', 0)}%")
        with col2:
            st.metric("Keyword in H2s", kw.get("keyword_in_h2s", 0))
        with col3:
            st.metric("Occurrences", analysis.get("summary", {}).get("keyword_occurrences", 0))

        st.markdown(f"""
| Check | Status |
|-------|--------|
| Keyword in Title | {_status_icon(kw.get('keyword_in_title', False))} |
| Keyword in Meta Description | {_status_icon(kw.get('keyword_in_meta', False))} |
| Keyword in H1 | {_status_icon(kw.get('keyword_in_h1', False))} |
| Keyword in First 100 Words | {_status_icon(kw.get('keyword_in_first_100_words', False))} |
""")

    # --- Content Structure ---
    with st.expander("🏗️ Content Structure", expanded=True):
        cs = analysis.get("content_structure", {})
        st.markdown(f"""
| Check | Status |
|-------|--------|
| Single H1 Tag | {_status_icon(cs.get('has_single_h1', False))} |
| Valid Heading Hierarchy | {_status_icon(cs.get('heading_hierarchy_valid', False))} |
| Has Introduction (60+ words before first H2) | {_status_icon(cs.get('has_introduction', False))} |
| Has Conclusion / Bottom Line | {_status_icon(cs.get('has_conclusion', False))} |
| Has Key Takeaways Section | {_status_icon(cs.get('has_key_takeaways', False))} |
| Has Sources / References Section | {_status_icon(cs.get('has_sources_section', False))} |
""")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("H2 Count", cs.get("h2_count", 0))
        with col2:
            st.metric("H3 Count", cs.get("h3_count", 0))
        with col3:
            st.metric("H2/Content Ratio", cs.get("heading_to_content_ratio", 0))

    # --- Readability ---
    with st.expander("📖 Readability", expanded=True):
        rd = analysis.get("readability", {})
        verdict = rd.get("readability_verdict", "Unknown")
        verdict_color = "🟢" if verdict == "Easy" else "🟡" if verdict == "Moderate" else "🔴"

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Flesch Reading Ease", rd.get("flesch_reading_ease", 0))
            st.metric("Avg Sentence Length", f"{rd.get('avg_sentence_length', 0)} words")
        with col2:
            st.metric("Flesch-Kincaid Grade", rd.get("flesch_kincaid_grade", 0))
            st.metric("Avg Paragraph Length", f"{rd.get('avg_paragraph_length', 0)} sentences")

        st.markdown(f"**Readability Verdict:** {verdict_color} {verdict}")

    # --- Links & Sources ---
    with st.expander("🔗 Links & Sources", expanded=True):
        lk = analysis.get("links", {})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Internal Links", lk.get("internal_link_count", 0))
        with col2:
            st.metric("External Links", lk.get("external_link_count", 0))
        with col3:
            st.metric("Total Links", lk.get("total_link_count", 0))

        st.markdown(f"""
| Check | Status |
|-------|--------|
| Link Ratio (Int:Ext) | {lk.get('link_ratio', 'N/A')} |
| Has Authority Sources (.gov/.edu) | {_status_icon(lk.get('has_authority_sources', False))} |
| .gov/.edu Source Count | {lk.get('gov_edu_source_count', 0)} |
| Overlinking Flag | {_warning_icon(lk.get('overlinking_flag', False))} |
""")

        if lk.get("gov_edu_sources_list"):
            st.markdown("**Authority sources found:**")
            for src in lk["gov_edu_sources_list"]:
                st.markdown(f"- {src}")

    # --- Meta Tags ---
    with st.expander("🏷️ Meta Tags", expanded=True):
        mt = analysis.get("meta", {})
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Title Length", f"{mt.get('title_length', 0)} chars")
            optimal = "✅ Optimal (30-60)" if mt.get("title_length_ok") else "❌ Not optimal"
            st.caption(optimal)
        with col2:
            st.metric("Meta Description Length", f"{mt.get('meta_description_length', 0)} chars")
            optimal = "✅ Optimal (120-160)" if mt.get("meta_description_length_ok") else "❌ Not optimal"
            st.caption(optimal)

    # --- Image Analysis ---
    with st.expander("🖼️ Image Analysis", expanded=False):
        img = analysis.get("images", {})
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Images", img.get("image_count", 0))
        with col2:
            st.metric("Missing Alt Text", img.get("images_missing_alt_count", 0))
        with col3:
            st.metric("% Missing Alt", f"{img.get('images_missing_alt_percentage', 0)}%")


# --- Helper: show comparison ---
def _show_comparison(comparison: dict[str, Any]):
    if comparison.get("error"):
        st.error(comparison["error"])
        return
    if comparison.get("note"):
        st.info(comparison["note"])
        return

    st.markdown("### 📈 Competitive Comparison")

    # Comparison table
    wc = comparison.get("word_count_comparison", {})
    hc = comparison.get("heading_comparison", {})
    lc = comparison.get("link_comparison", {})
    rc = comparison.get("readability_comparison", {})

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Your Article**")
        st.metric("Word Count", wc.get("my_word_count", 0))
        st.metric("H2 Tags", hc.get("my_h2_count", 0))
        st.metric("H3 Tags", hc.get("my_h3_count", 0))
        st.metric("Total Links", lc.get("my_total_links", 0))
        st.metric("Reading Grade", rc.get("my_flesch_kincaid_grade", 0))
    with col2:
        st.markdown("**Competitor Average**")
        st.metric("Word Count", wc.get("avg_competitor_word_count", 0))
        st.metric("H2 Tags", hc.get("avg_competitor_h2_count", 0))
        st.metric("H3 Tags", hc.get("avg_competitor_h3_count", 0))
        st.metric("Total Links", lc.get("avg_competitor_total_links", 0))
        st.metric("Reading Grade", rc.get("avg_competitor_flesch_kincaid_grade", 0))

    # Weaknesses
    weaker = comparison.get("weaker_areas", [])
    if weaker:
        st.markdown("---")
        st.markdown("#### ⚠️ Areas Where You're Weaker")
        for w in weaker:
            st.warning(w)
    else:
        st.success("Your article matches or exceeds competitors across all measured dimensions.")


# --- Main analysis flow ---
def _run_full_analysis(results: dict[str, dict], provided_labels: list[str]):
    # Phase 1: Extraction Results
    st.markdown("### Extraction Results")
    for label in provided_labels:
        _show_extraction_block(label, results.get(label, {"error": "No data"}))

    # Phase 2: Rule-Based Analysis
    if not primary_keyword.strip():
        st.warning("⚠️ Enter a Primary Target Keyword in the sidebar for keyword analysis. Showing structure analysis only.")

    keyword = primary_keyword.strip() if primary_keyword else ""

    analyses = {}
    with st.spinner("Running rule-based analysis..."):
        for label in provided_labels:
            extracted = results.get(label, {})
            if not extracted.get("error"):
                analyses[label] = run_rule_analysis(extracted, keyword)

    st.markdown("---")

    # Show your article analysis
    if "Your Article" in analyses:
        _show_rule_analysis("Your Article", analyses["Your Article"])

    # Show competitor analyses
    for label in provided_labels:
        if label.startswith("Competitor") and label in analyses:
            st.markdown("---")
            _show_rule_analysis(label, analyses[label])

    # Show comparison
    if "Your Article" in analyses:
        competitor_analyses = [analyses[label] for label in provided_labels if label.startswith("Competitor") and label in analyses]
        if competitor_analyses:
            st.markdown("---")
            comparison = compare_rule_analysis(analyses["Your Article"], competitor_analyses)
            _show_comparison(comparison)


# --- URL Input Mode ---
if input_method == "Enter URLs":
    your_url = st.text_input("Your Article URL", placeholder="https://example.com/your-article")
    competitor_url_1 = st.text_input("Competitor URL 1", placeholder="https://competitor.com/article")
    competitor_url_2 = st.text_input("Competitor URL 2 (optional)", placeholder="https://competitor2.com/article")
    competitor_url_3 = st.text_input("Competitor URL 3 (optional)", placeholder="https://competitor3.com/article")

    analyze_clicked = st.button("Analyze", type="primary")

    if analyze_clicked:
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

            results = {}
            with st.spinner("Scraping content..."):
                for label, url in provided:
                    results[label] = scrape_url(url)

            _run_full_analysis(results, [label for label, _ in provided])

# --- Paste Content Mode ---
else:
    your_content = st.text_area(
        "Your Article Content (HTML or plain text)",
        height=220,
        placeholder="Paste your article HTML or plain text here...",
    )
    competitor_content_1 = st.text_area(
        "Competitor Content 1",
        height=220,
        placeholder="Paste competitor content here...",
    )
    competitor_content_2 = st.text_area(
        "Competitor Content 2 (optional)",
        height=220,
        placeholder="Paste optional second competitor content here...",
    )

    analyze_clicked = st.button("Analyze", type="primary")

    if analyze_clicked:
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

            results = {}
            with st.spinner("Parsing content..."):
                for label, content in provided:
                    results[label] = parse_pasted_content(content)

            _run_full_analysis(results, [label for label, _ in provided])
