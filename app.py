from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

from analyzer_ai import configure_gemini, run_ai_analysis
from analyzer_rules import compare_rule_analysis, run_rule_analysis
from scorer import calculate_score
from scraper import parse_pasted_content, scrape_url

APP_VERSION = "v1.0.0"

st.set_page_config(page_title="Content Quality Analyzer", layout="wide")


@st.cache_data(show_spinner=False)
def cached_scrape_url(url: str) -> dict[str, Any]:
    return scrape_url(url)


def _init_state() -> None:
    defaults = {
        "competitor_count": 1,
        "analysis_results": None,
        "last_inputs_hash": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


_init_state()

st.title("Content Quality Analyzer")
st.subheader("Final Dashboard: Scrape, benchmark, score, and prioritize SEO improvements.")

with st.expander("How to Use", expanded=False):
    st.markdown(
        """
1. Enter your primary keyword and choose URL mode or paste mode.
2. Add your article + competitor content.
3. (Optional) Add Gemini API key for deeper AI insights.
4. Click **Analyze** to get score, action items, and competitor benchmark.
5. Use **Download Report** to export a markdown summary.
        """
    )

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


def _show_extraction_block(label: str, result: dict[str, Any]) -> None:
    if result.get("error"):
        st.error(f"{label}: {result['error']}")
        st.info("Tip: If this URL blocks scraping, switch to **Paste Content** mode and paste the article text/HTML directly.")
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

    if int(result.get("word_count", 0) or 0) < 200:
        st.warning("Very short content detected (<200 words). Score may be limited due to low depth.")
    if not result.get("h2"):
        st.warning("No H2 tags detected. Add section headings to improve readability and structure.")


def _show_hero(score_data: dict[str, Any], partial_ai: bool = False) -> None:
    total = int(score_data.get("total_score", 0))
    rating = score_data.get("rating", "Unknown")
    color = _color_for_score(total)
    summary = _summary_for_rating(rating)
    partial_label = "<div style='margin-top:0.5rem;color:#b45309;font-weight:600;'>Partial Analysis — AI unavailable</div>" if partial_ai else ""

    st.markdown(
        f"""
        <div style="padding: 1rem 1.25rem; border-radius: 0.75rem; border: 1px solid #e5e7eb; background: #fafafa;">
          <div style="font-size: 0.95rem; color: #6b7280;">Overall Content Score</div>
          <div style="display:flex; align-items:end; gap:1rem;">
            <div style="font-size: 3rem; font-weight: 700; color: {color}; line-height:1;">{total}</div>
            <div style="font-size: 1.15rem; font-weight: 600; color: {color}; margin-bottom:0.3rem;">{rating}</div>
          </div>
          <div style="margin-top:0.6rem; color:#374151;">{summary}</div>
          {partial_label}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _show_score_breakdown(score_data: dict[str, Any]) -> None:
    st.markdown("### Score Breakdown")
    for cat, values in score_data.get("category_scores", {}).items():
        score = float(values.get("score", 0))
        max_score = float(values.get("max", 1))
        ratio = score / max_score if max_score else 0
        label = cat.replace("_", " ").title()
        st.write(f"**{label}** — {int(score)}/{int(max_score)}")
        st.progress(min(max(ratio, 0.0), 1.0))


def _show_action_items(score_data: dict[str, Any]) -> None:
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
) -> None:
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


def _build_report_markdown(results: dict[str, Any]) -> str:
    score = results.get("my_score", {})
    comparison = results.get("comparison", {})
    ai = results.get("ai_results", {})
    lines = [
        "# Content Quality Analyzer Report",
        "",
        f"- Overall Score: **{score.get('total_score', 0)} / 100**",
        f"- Rating: **{score.get('rating', 'Unknown')}**",
        "",
        "## Top Improvements",
    ]
    for item in score.get("top_improvements", [])[:10]:
        lines.append(f"- {item}")

    lines.extend(["", "## Category Scores"])
    for cat, values in score.get("category_scores", {}).items():
        lines.append(f"- {cat.replace('_', ' ').title()}: {values.get('score', 0)}/{values.get('max', 0)}")

    lines.extend(["", "## Competitive Notes"])
    if comparison.get("weaker_areas"):
        for item in comparison["weaker_areas"]:
            lines.append(f"- {item}")
    elif comparison.get("note"):
        lines.append(f"- {comparison['note']}")

    lines.extend(["", "## AI Status"])
    if ai.get("error"):
        lines.append(f"- AI unavailable: {ai['error']}")
    else:
        lines.append(f"- Intent: {ai.get('user_intent', {}).get('classification', 'N/A')}")
        lines.append(f"- Depth vs competitors: {ai.get('content_depth', {}).get('vs_competitors', 'N/A')}")

    return "\n".join(lines)


def _run_pipeline(extracted_results: dict[str, dict[str, Any]], labels: list[str], primary_keyword_value: str, gemini_key: str) -> dict[str, Any]:
    analyses: dict[str, dict[str, Any]] = {}
    ai_results: dict[str, Any] = {"error": "AI analysis unavailable"}

    progress = st.progress(0, text="Scraping...")

    for label in labels:
        ext = extracted_results[label]
        analyses[label] = {"extracted": ext, "rule": {}}
    progress.progress(25, text="Analyzing structure...")

    for label in labels:
        analyses[label]["rule"] = run_rule_analysis(analyses[label]["extracted"], primary_keyword_value)

    comparison = compare_rule_analysis(
        analyses.get("Your Article", {}).get("rule", {"error": "Missing analysis"}),
        [analyses[label]["rule"] for label in labels if label.startswith("Competitor")],
    )

    progress.progress(60, text="Running AI analysis...")
    if gemini_key.strip():
        try:
            configure_gemini(gemini_key)
            my_content = analyses.get("Your Article", {}).get("extracted", {})
            competitors = [
                analyses[label]["extracted"]
                for label in labels
                if label.startswith("Competitor") and not analyses[label]["extracted"].get("error")
            ]
            ai_payload = {
                "my_rule_analysis": analyses.get("Your Article", {}).get("rule", {}),
                "competitor_rule_analysis": {label: analyses[label]["rule"] for label in labels if label.startswith("Competitor")},
                "comparison": comparison,
            }
            ai_results = run_ai_analysis(my_content, competitors, primary_keyword_value, ai_payload)
        except Exception as exc:
            ai_results = {"error": f"Unable to run AI analysis: {exc}"}
    else:
        ai_results = {"error": "No Gemini API key provided."}

    progress.progress(85, text="Calculating score...")
    for label in labels:
        rule = analyses[label]["rule"]
        if rule.get("error"):
            analyses[label]["error"] = rule.get("error")
            analyses[label]["score"] = {"total_score": 0, "rating": "Poor", "category_scores": {}, "top_improvements": []}
            continue

        rule_with_context = dict(rule)
        rule_with_context["comparison_context"] = {"avg_competitor_word_count": _avg_comp_word_count(analyses, exclude=label)}
        ai_for_label = ai_results if label == "Your Article" and not ai_results.get("error") else None
        analyses[label]["score"] = calculate_score(rule_with_context, ai_for_label)
        analyses[label]["rule"] = rule_with_context

    progress.progress(100, text="Done")

    return {
        "labels": labels,
        "analyses": analyses,
        "comparison": comparison,
        "ai_results": ai_results,
        "my_score": analyses.get("Your Article", {}).get("score", {"total_score": 0, "rating": "Poor", "category_scores": {}, "top_improvements": []}),
        "partial_ai": bool(ai_results.get("error")),
    }


def _render_results(results: dict[str, Any]) -> None:
    labels = results["labels"]
    analyses = results["analyses"]
    comparison = results["comparison"]
    ai_results = results["ai_results"]
    my_score = results["my_score"]

    st.markdown("### Extraction Results")
    with st.expander("Show raw extraction status", expanded=False):
        for label in labels:
            _show_extraction_block(label, analyses[label]["extracted"])

    if ai_results.get("error"):
        st.warning("Partial Analysis — AI unavailable. Rule-based scoring is still shown.")
        if "429" in ai_results.get("error", ""):
            st.warning("Gemini rate limit hit (429). Please wait about 60 seconds and retry.")

    _show_hero(my_score, partial_ai=bool(ai_results.get("error")))
    _show_score_breakdown(my_score)
    _show_action_items(my_score)

    competitor_table = _build_comparison_table(analyses)
    st.markdown("### Competitor Scores")
    if competitor_table.empty:
        st.info("No competitor scores available.")
    else:
        st.dataframe(competitor_table, use_container_width=True)

    _render_tabs(analyses.get("Your Article", {}).get("rule", {}), ai_results, comparison, competitor_table)

    report_text = _build_report_markdown(results)
    st.download_button(
        label="Download Report",
        data=report_text,
        file_name="content_quality_report.md",
        mime="text/markdown",
    )


if input_method == "Enter URLs":
    your_url = st.text_input("Your Article URL", placeholder="https://example.com/your-article")

    st.markdown("#### Competitor URLs")
    competitor_urls: list[str] = []
    for i in range(st.session_state.competitor_count):
        val = st.text_input(
            f"Competitor URL {i + 1}{' (required)' if i == 0 else ' (optional)'}",
            placeholder=f"https://competitor{i+1}.com/article",
            key=f"comp_url_{i}",
        )
        competitor_urls.append(val)

    add_col, _ = st.columns([1, 3])
    with add_col:
        if st.button("Add Another Competitor", disabled=st.session_state.competitor_count >= 3):
            st.session_state.competitor_count = min(3, st.session_state.competitor_count + 1)
            st.rerun()

    if st.button("Analyze", type="primary"):
        if not your_url.strip():
            st.error("Your Article URL is required.")
        elif not competitor_urls[0].strip():
            st.error("At least Competitor URL 1 is required.")
        else:
            url_inputs = [("Your Article", your_url.strip())]
            for idx, url in enumerate(competitor_urls, start=1):
                if url.strip():
                    url_inputs.append((f"Competitor {idx}", url.strip()))

            extracted_results: dict[str, dict[str, Any]] = {}
            for label, url in url_inputs:
                extracted_results[label] = cached_scrape_url(url)

            labels = [label for label, _ in url_inputs]
            st.session_state.analysis_results = _run_pipeline(extracted_results, labels, primary_keyword, gemini_api_key)

else:
    your_content = st.text_area(
        "Your Article Content (HTML or plain text)",
        height=220,
        placeholder="Paste your article HTML or plain text here...",
    )
    competitor_content_1 = st.text_area("Competitor Content 1", height=220, placeholder="Paste competitor content here...")
    competitor_content_2 = st.text_area("Competitor Content 2 (optional)", height=220, placeholder="Paste optional second competitor content here...")

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
            for label, content in provided:
                extracted_results[label] = parse_pasted_content(content)

            labels = [label for label, _ in provided]
            st.session_state.analysis_results = _run_pipeline(extracted_results, labels, primary_keyword, gemini_api_key)

if st.session_state.analysis_results:
    _render_results(st.session_state.analysis_results)

st.markdown("---")
st.caption(f"Content Quality Analyzer {APP_VERSION}")
