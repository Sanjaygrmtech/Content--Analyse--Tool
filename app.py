from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from analyzer_ai import configure_gemini, run_ai_analysis
from analyzer_rules import compare_rule_analysis, run_rule_analysis
from scorer import calculate_score
from scraper import parse_pasted_content, scrape_url


st.set_page_config(page_title="Content Quality Analyzer", layout="wide")

st.title("Content Quality Analyzer")
st.subheader("Final Dashboard: Scrape, benchmark, score, and prioritize SEO improvements.")

with st.sidebar:
    st.header("Inputs")
    primary_keyword = st.text_input("Primary Target Keyword", placeholder="e.g., enterprise seo strategy")
    gemini_api_key = st.text_input("Gemini API Key", type="password", placeholder="Paste your Gemini API key")
    input_method = st.radio("Input method", ["Enter URLs", "Paste Content"])

st.caption(f"Primary keyword for context: **{primary_keyword or 'Not provided'}**")


def _color_for_score(score: int) -> str:
    if score < 60:
        return "#dc2626"
    if score < 70:
        return "#f59e0b"
    if score < 80:
        return "#eab308"
    if score < 90:
        return "#22c55e"
    return "#166534"


def _summary_for_rating(rating: str) -> str:
    mapping = {
        "Excellent": "Minimal improvements needed — focus on maintaining quality and fine-tuning opportunities.",
        "Very Good": "A few strategic optimizations can elevate this content to top-tier performance.",
        "Good": "Solid foundation, but meaningful gaps remain compared to stronger competitors.",
        "Fair": "Significant improvements are needed across multiple SEO and content quality areas.",
        "Poor": "Major rework is recommended before expecting strong search performance.",
    }
    return mapping.get(rating, "Review the category breakdown to identify highest-impact improvements.")


def _show_extraction_block(label: str, result: dict[str, Any]):
    if result.get("error"):
        st.error(f"{label}: {result['error']}")
        return

    st.success(f"{label}: Content extracted successfully")
    st.write(f"Word count: {result.get('word_count', 0)}")
    st.write(
        {
            "internal_link_count": result.get("internal_link_count", 0),
            "external_link_count": result.get("external_link_count", 0),
            "gov_edu_count": result.get("gov_edu_count", 0),
        }
    )


def _show_hero(score_data: dict[str, Any]):
    total = int(score_data.get("total_score", 0))
    rating = score_data.get("rating", "Unknown")
    color = _color_for_score(total)
    summary = _summary_for_rating(rating)

    st.markdown(
        f"""
        <div style="padding: 1rem 1.25rem; border-radius: 0.75rem; border: 1px solid #e5e7eb; background: #fafafa;">
          <div style="font-size: 0.95rem; color: #6b7280;">Overall Content Score</div>
          <div style="display:flex; align-items:end; gap:1rem;">
            <div style="font-size: 3rem; font-weight: 700; color: {color}; line-height:1;">{total}</div>
            <div style="font-size: 1.15rem; font-weight: 600; color: {color}; margin-bottom:0.3rem;">{rating}</div>
          </div>
          <div style="margin-top:0.6rem; color:#374151;">{summary}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_score_breakdown(score_data: dict[str, Any]):
    st.markdown("### Score Breakdown")
    for cat, values in score_data.get("category_scores", {}).items():
        score = float(values.get("score", 0))
        max_score = float(values.get("max", 1))
        ratio = score / max_score if max_score else 0
        label = cat.replace("_", " ").title()
        st.write(f"**{label}** — {int(score)}/{int(max_score)}")
        st.progress(min(max(ratio, 0.0), 1.0))


def _show_action_items(score_data: dict[str, Any]):
    st.markdown("### Top 3 Action Items")
    improvements = score_data.get("top_improvements", [])[:3]
    if not improvements:
        st.success("No critical issues detected from current scoring rules.")
        return
    for idx, item in enumerate(improvements, start=1):
        st.markdown(f"{idx}. :red[{item}]")


def _safe_df_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def _render_tabs(
    rule: dict[str, Any],
    ai: dict[str, Any],
    comparison: dict[str, Any],
    competitor_table: pd.DataFrame,
):
    tabs = st.tabs([
        "Keyword Analysis",
        "Content Structure",
        "Readability",
        "Links & Sources",
        "AI Insights",
        "Competitor Comparison",
    ])

    keyword = rule.get("keyword_analysis", {})
    structure = rule.get("content_structure", {})
    readability = rule.get("readability", {})
    links = rule.get("links", {})
    meta = rule.get("meta", {})

    with tabs[0]:
        st.json(keyword)
        if ai and not ai.get("error"):
            gaps = ai.get("keyword_gap_analysis", {})
            st.markdown("#### AI Semantic Keyword Gaps")
            st.write("Missing topics:")
            for item in gaps.get("missing_topics", []) or []:
                st.markdown(f"- {item}")
            st.write("Missing keywords:")
            for item in gaps.get("missing_keywords", []) or []:
                st.markdown(f"- {item}")

    with tabs[1]:
        st.json(structure)
        if ai and not ai.get("error"):
            hq = ai.get("heading_quality", {})
            st.markdown("#### AI Heading Suggestions")
            st.write(f"Overall rating: {hq.get('overall_rating', 'N/A')}")
            improv = hq.get("suggested_improvements", []) or []
            if improv:
                st.dataframe(_safe_df_rows(improv), use_container_width=True)

    with tabs[2]:
        st.json(readability)
        st.write("Meta lengths:")
        st.write(
            {
                "title_length": meta.get("title_length", 0),
                "title_length_ok": meta.get("title_length_ok", False),
                "meta_description_length": meta.get("meta_description_length", 0),
                "meta_description_length_ok": meta.get("meta_description_length_ok", False),
            }
        )

    with tabs[3]:
        st.json(links)

    with tabs[4]:
        if ai.get("error"):
            st.info("AI analysis unavailable. Add a valid Gemini API key to unlock this tab.")
        else:
            st.json(
                {
                    "user_intent": ai.get("user_intent", {}),
                    "target_audience": ai.get("target_audience", {}),
                    "geo_targeting": ai.get("geo_targeting", {}),
                    "content_depth": ai.get("content_depth", {}),
                    "overall_ai_assessment": ai.get("overall_ai_assessment", {}),
                }
            )
            st.markdown("#### Structural Suggestions")
            st.json(ai.get("structural_suggestions", {}))

    with tabs[5]:
        if comparison.get("error"):
            st.error(comparison.get("error"))
        elif comparison.get("note"):
            st.info(comparison.get("note"))
        else:
            st.json(comparison)
        st.markdown("#### Side-by-side metrics")
        if competitor_table.empty:
            st.info("No competitor rows available.")
        else:
            st.dataframe(competitor_table, use_container_width=True)


def _build_comparison_table(analyses: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for article, analysis in analyses.items():
        if analysis.get("error"):
            continue
        rows.append(
            {
                "Article": article,
                "Total Score": analysis.get("score", {}).get("total_score", "-"),
                "Rating": analysis.get("score", {}).get("rating", "-"),
                "Word Count": analysis.get("rule", {}).get("summary", {}).get("word_count", 0),
                "H2 Count": analysis.get("rule", {}).get("content_structure", {}).get("h2_count", 0),
                "Total Links": analysis.get("rule", {}).get("links", {}).get("total_link_count", 0),
                "Flesch-Kincaid": analysis.get("rule", {}).get("readability", {}).get("flesch_kincaid_grade", 0),
            }
        )
    return pd.DataFrame(rows)


def _avg_comp_word_count(analyses: dict[str, dict[str, Any]], exclude: str) -> float:
    comp = [
        a.get("rule", {}).get("summary", {}).get("word_count", 0)
        for label, a in analyses.items()
        if label != exclude and label.startswith("Competitor") and not a.get("error")
    ]
    return float(sum(comp) / len(comp)) if comp else 0.0


def _run_pipeline(extracted_results: dict[str, dict[str, Any]], labels: list[str]):
    st.markdown("### Extraction Results")
    with st.expander("Show raw extraction status", expanded=False):
        for label in labels:
            _show_extraction_block(label, extracted_results[label])

    analyses: dict[str, dict[str, Any]] = {}
    with st.spinner("Running rule-based analysis..."):
        for label in labels:
            ext = extracted_results[label]
            rule = run_rule_analysis(ext, primary_keyword)
            analyses[label] = {"extracted": ext, "rule": rule}

    comparison = compare_rule_analysis(
        analyses.get("Your Article", {}).get("rule", {"error": "Missing analysis"}),
        [analyses[label]["rule"] for label in labels if label.startswith("Competitor")],
    )

    ai_results: dict[str, Any] = {"error": "AI analysis unavailable"}
    if gemini_api_key.strip():
        try:
            configure_gemini(gemini_api_key)
            my_content = analyses.get("Your Article", {}).get("extracted", {})
            competitors = [analyses[label]["extracted"] for label in labels if label.startswith("Competitor") and not analyses[label]["extracted"].get("error")]
            ai_payload = {
                "my_rule_analysis": analyses.get("Your Article", {}).get("rule", {}),
                "competitor_rule_analysis": {label: analyses[label]["rule"] for label in labels if label.startswith("Competitor")},
                "comparison": comparison,
            }
            with st.spinner("Running AI analysis with Gemini..."):
                ai_results = run_ai_analysis(my_content, competitors, primary_keyword, ai_payload)
        except Exception as exc:
            ai_results = {"error": f"Unable to run AI analysis: {exc}"}
    else:
        st.info("AI analysis is optional. Add Gemini API key in sidebar for intent/gap/depth insights.")

    # Score user + competitors
    for label in labels:
        rule = analyses[label]["rule"]
        if rule.get("error"):
            analyses[label]["error"] = rule.get("error")
            analyses[label]["score"] = {"total_score": 0, "rating": "Poor", "category_scores": {}, "top_improvements": []}
            continue

        # add fallback context for depth scoring
        rule_with_context = dict(rule)
        rule_with_context["comparison_context"] = {
            "avg_competitor_word_count": _avg_comp_word_count(analyses, exclude=label)
        }
        ai_for_label = ai_results if label == "Your Article" else None
        analyses[label]["score"] = calculate_score(rule_with_context, ai_for_label)
        analyses[label]["rule"] = rule_with_context

    my_score = analyses.get("Your Article", {}).get("score", {"total_score": 0, "rating": "Poor", "category_scores": {}, "top_improvements": []})
    _show_hero(my_score)
    _show_score_breakdown(my_score)
    _show_action_items(my_score)

    competitor_table = _build_comparison_table(analyses)

    st.markdown("### Competitor Scores")
    if competitor_table.empty:
        st.info("No competitor scores available.")
    else:
        st.dataframe(competitor_table, use_container_width=True)

    _render_tabs(
        analyses.get("Your Article", {}).get("rule", {}),
        ai_results,
        comparison,
        competitor_table,
    )


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
            _run_pipeline(extracted_results, [label for label, _ in provided])

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
            _run_pipeline(extracted_results, [label for label, _ in provided])
