from __future__ import annotations

from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from readability import Document

DEFAULT_TIMEOUT = 15
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}


REMOVE_SELECTORS = [
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "aside",
    "header",
    ".sidebar",
    ".menu",
    ".navigation",
    ".advertisement",
    ".ads",
    "[role='navigation']",
    "[role='complementary']",
    "[aria-label*='breadcrumb' i]",
]


def _normalize_text(text: str) -> str:
    return " ".join(text.split()).strip()


def _is_html(content: str) -> bool:
    lowered = content.strip().lower()
    return "<html" in lowered or "<!doctype html" in lowered or ("<" in lowered and ">" in lowered and "</" in lowered)


def _extract_from_html(html: str, base_url: str | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html5lib")

    title_tag = _normalize_text(soup.title.get_text(" ", strip=True)) if soup.title else ""

    meta_description = ""
    meta_tag = soup.find("meta", attrs={"name": lambda v: isinstance(v, str) and v.lower() == "description"})
    if meta_tag and isinstance(meta_tag, Tag):
        meta_description = _normalize_text(meta_tag.get("content", ""))

    headings_map: dict[str, list[str]] = {level: [] for level in ("h1", "h2", "h3", "h4")}
    heading_hierarchy: list[dict[str, str]] = []

    for tag in soup.find_all(["h1", "h2", "h3", "h4"]):
        if not isinstance(tag, Tag):
            continue
        tag_name = tag.name.lower()
        text = _normalize_text(tag.get_text(" ", strip=True))
        if text:
            headings_map[tag_name].append(text)
            heading_hierarchy.append({"level": tag_name, "text": text})

    content_soup = BeautifulSoup(html, "html5lib")
    for selector in REMOVE_SELECTORS:
        for node in content_soup.select(selector):
            node.decompose()

    body_text = _normalize_text(content_soup.get_text(" ", strip=True))
    word_count = len(body_text.split()) if body_text else 0

    internal_links: list[str] = []
    external_links: list[dict[str, str]] = []
    gov_edu_sources: list[str] = []

    base_domain = urlparse(base_url).netloc.lower() if base_url else ""

    for a_tag in soup.find_all("a", href=True):
        if not isinstance(a_tag, Tag):
            continue

        href = a_tag.get("href", "").strip()
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            continue

        absolute_url = urljoin(base_url, href) if base_url else href
        parsed = urlparse(absolute_url)
        if not parsed.scheme.startswith("http"):
            continue

        domain = parsed.netloc.lower()
        anchor = _normalize_text(a_tag.get_text(" ", strip=True))

        is_internal = bool(base_domain) and (domain == base_domain or domain.endswith(f".{base_domain}"))

        if is_internal:
            internal_links.append(absolute_url)
        else:
            external_links.append({"url": absolute_url, "anchor_text": anchor})

        if domain.endswith(".gov") or domain.endswith(".edu"):
            gov_edu_sources.append(absolute_url)

    images: list[dict[str, str]] = []
    missing_alt = 0

    for image in soup.find_all("img"):
        if not isinstance(image, Tag):
            continue
        src = image.get("src", "").strip()
        alt = image.get("alt", "")
        alt_text = _normalize_text(alt) if isinstance(alt, str) else ""

        images.append({"src": urljoin(base_url, src) if base_url and src else src, "alt": alt_text})
        if not alt_text:
            missing_alt += 1

    return {
        "title_tag": title_tag,
        "meta_description": meta_description,
        "h1": headings_map["h1"],
        "h2": headings_map["h2"],
        "h3": headings_map["h3"],
        "h4": headings_map["h4"],
        "heading_hierarchy": heading_hierarchy,
        "body_text": body_text,
        "word_count": word_count,
        "internal_links": sorted(set(internal_links)),
        "internal_link_count": len(set(internal_links)),
        "external_links": external_links,
        "external_link_count": len(external_links),
        "gov_edu_sources": sorted(set(gov_edu_sources)),
        "gov_edu_count": len(set(gov_edu_sources)),
        "images": images,
        "images_missing_alt": missing_alt,
        "raw_html": html,
    }


def extract_readable_text(html: str) -> str:
    """Extracts main article-like content using readability-lxml and returns clean text."""
    try:
        readable_doc = Document(html)
        summary_html = readable_doc.summary(html_partial=True)
    except Exception:
        summary_html = html

    soup = BeautifulSoup(summary_html, "html5lib")
    for selector in REMOVE_SELECTORS:
        for node in soup.select(selector):
            node.decompose()

    return _normalize_text(soup.get_text(" ", strip=True))


def scrape_url(url: str) -> dict[str, Any]:
    """Scrapes a URL and returns extracted page metadata/content details."""
    if not url or not isinstance(url, str):
        return {"error": "Please provide a valid URL."}

    cleaned_url = url.strip()
    parsed = urlparse(cleaned_url)
    if not parsed.scheme:
        cleaned_url = f"https://{cleaned_url}"

    try:
        response = requests.get(cleaned_url, headers=DEFAULT_HEADERS, timeout=DEFAULT_TIMEOUT)

        if response.status_code >= 400:
            return {
                "error": f"HTTP {response.status_code}: Unable to access URL. The site may block requests or the page may not exist.",
                "status_code": response.status_code,
                "url": cleaned_url,
            }

        content_type = response.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return {
                "error": f"Unsupported content type: {content_type or 'unknown'}",
                "url": cleaned_url,
            }

        extracted = _extract_from_html(response.text, base_url=response.url)
        extracted["url"] = response.url
        extracted["readable_text"] = extract_readable_text(response.text)
        return extracted

    except requests.Timeout:
        return {"error": "Request timed out while fetching the URL. Please try again."}
    except requests.TooManyRedirects:
        return {"error": "Too many redirects encountered for this URL."}
    except requests.ConnectionError:
        return {"error": "Connection error. Check the URL and your internet connection."}
    except requests.RequestException as exc:
        return {"error": f"Request failed: {str(exc)}"}
    except Exception as exc:  # safeguard for unexpected parsing failures
        return {"error": f"Unexpected error while scraping URL: {str(exc)}"}


def parse_pasted_content(html_or_text: str) -> dict[str, Any]:
    """Parses pasted HTML or plain text and returns structured content details."""
    if not html_or_text or not html_or_text.strip():
        return {"error": "No content provided. Please paste HTML or text."}

    content = html_or_text.strip()

    try:
        if _is_html(content):
            extracted = _extract_from_html(content)
            extracted["readable_text"] = extract_readable_text(content)
            return extracted

        normalized_text = _normalize_text(content)
        lines = [line.strip() for line in html_or_text.splitlines() if line.strip()]
        inferred_headings = [line for line in lines if len(line.split()) <= 12 and line.istitle()][:10]

        return {
            "title_tag": "",
            "meta_description": "",
            "h1": [],
            "h2": inferred_headings,
            "h3": [],
            "h4": [],
            "heading_hierarchy": [{"level": "h2", "text": h} for h in inferred_headings],
            "body_text": normalized_text,
            "word_count": len(normalized_text.split()) if normalized_text else 0,
            "internal_links": [],
            "internal_link_count": 0,
            "external_links": [],
            "external_link_count": 0,
            "gov_edu_sources": [],
            "gov_edu_count": 0,
            "images": [],
            "images_missing_alt": 0,
            "raw_html": html_or_text,
            "readable_text": normalized_text,
            "note": "Plain text detected. Heading/link/image analysis is limited.",
        }
    except Exception as exc:
        return {"error": f"Unable to parse pasted content: {str(exc)}"}
