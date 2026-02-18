from __future__ import annotations

import streamlit as st

from scraper import parse_pasted_content, scrape_url


st.set_page_config(page_title="Content Quality Analyzer", layout="wide")

st.title("Content Quality Analyzer")
st.subheader(
    "Phase 1: Collect and inspect content structure from your article and competitor pages before scoring."
)

with st.sidebar:
    st.header("Inputs")
    primary_keyword = st.text_input("Primary Target Keyword", placeholder="e.g., enterprise seo strategy")
    input_method = st.radio("Input method", ["Enter URLs", "Paste Content"])


st.caption(f"Primary keyword for context: **{primary_keyword or 'Not provided'}**")


def _show_result_block(label: str, result: dict):
    if result.get("error"):
        st.error(f"{label}: {result['error']}")
        return

    st.success(f"{label}: Content extracted successfully")
    with st.expander(f"{label} — Extraction details", expanded=False):
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

        note = result.get("note")
        if note:
            st.info(note)


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
            provided_urls = [(label, url) for label, url in url_inputs if url]

            results = {}
            with st.spinner("Scraping content..."):
                for label, url in provided_urls:
                    results[label] = scrape_url(url)

            st.markdown("### Extraction Results")
            for label, _ in provided_urls:
                _show_result_block(label, results[label])

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
            provided_content = [(label, content) for label, content in content_inputs if content]

            results = {}
            with st.spinner("Scraping content..."):
                for label, content in provided_content:
                    results[label] = parse_pasted_content(content)

            st.markdown("### Extraction Results")
            for label, _ in provided_content:
                _show_result_block(label, results[label])
