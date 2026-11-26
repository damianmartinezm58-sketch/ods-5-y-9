from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote

import streamlit as st


ROOT = Path(__file__).resolve().parent
HTML_FILE = ROOT / "index.html"
STYLESHEET = ROOT / "css" / "estilos.css"

_LOCAL_SCRIPT = re.compile(
    r"<script\b[^>]*\bsrc=[\"'](?P<path>[^\"']+)[\"'][^>]*>\s*</script>",
    re.IGNORECASE,
)
_LOCAL_IMAGE = re.compile(
    r"(?P<prefix><img\b[^>]*\bsrc=[\"'])(?P<path>[^\"']+)(?P<suffix>[\"'])",
    re.IGNORECASE,
)
_CSS_URL = re.compile(
    r"url\(\s*(?P<quote>[\"']?)(?P<path>[^\"')]+)(?P=quote)\s*\)",
    re.IGNORECASE,
)


def _asset_path(base: Path, reference: str) -> Path:
    asset = (base / unquote(reference)).resolve()
    try:
        asset.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"Asset path is outside the site directory: {reference}") from error
    if not asset.is_file():
        raise FileNotFoundError(f"Site asset not found: {asset}")
    return asset


def _data_url(path: Path) -> str:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix.lower() == ".woff2":
        content_type = "font/woff2"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{content_type};base64,{encoded}"


def _inline_css_assets(css: str) -> str:
    def replace_url(match: re.Match[str]) -> str:
        reference = match.group("path").strip()
        if reference.startswith(("data:", "http:", "https:", "//", "#")):
            return match.group(0)
        return f'url("{_data_url(_asset_path(STYLESHEET.parent, reference))}")'

    return _CSS_URL.sub(replace_url, css)


def _build_page() -> str:
    page = HTML_FILE.read_text(encoding="utf-8-sig")
    css = _inline_css_assets(STYLESHEET.read_text(encoding="utf-8-sig"))
    stylesheet_tag = re.compile(
        r"<link\b(?=[^>]*\bhref=[\"']css/estilos\.css[\"'])[^>]*>",
        re.IGNORECASE,
    )
    page, stylesheet_count = stylesheet_tag.subn(
        lambda _: f"<style>\n{css}\n</style>",
        page,
    )
    if stylesheet_count != 1:
        raise ValueError("Expected exactly one local stylesheet link in index.html")

    page = re.sub(
        r"\s*<link\b(?=[^>]*\brel=[\"']preload[\"'])[^>]*>",
        "",
        page,
        flags=re.IGNORECASE,
    )
    logo_url = _data_url(_asset_path(ROOT, "img/emblema.png"))
    page = page.replace('href="img/emblema.png"', f'href="{logo_url}"')

    def inline_image(match: re.Match[str]) -> str:
        url = _data_url(_asset_path(ROOT, match.group("path")))
        return f'{match.group("prefix")}{url}{match.group("suffix")}'

    page = _LOCAL_IMAGE.sub(inline_image, page)

    def inline_script(match: re.Match[str]) -> str:
        reference = match.group("path")
        if reference.startswith(("http:", "https:", "//", "data:")):
            return match.group(0)
        script = _asset_path(ROOT, reference).read_text(encoding="utf-8-sig")
        return f"<script>\n{script}\n</script>"

    page, _ = _LOCAL_SCRIPT.subn(inline_script, page)
    return page


st.set_page_config(
    page_title="Industry, Innovation & Equality · SDG 5 + SDG 9",
    layout="wide",
    initial_sidebar_state="collapsed",
)
st.markdown(
    """
    <style>
      [data-testid="stAppViewContainer"] { background: #e7d3ec; }
      [data-testid="stMainBlockContainer"] {
        max-width: none;
        padding: 0;
      }
      header, footer, #MainMenu { visibility: hidden; }
      iframe { border: 0; }
    </style>
    """,
    unsafe_allow_html=True,
)
# This iframe runs scripts from the repository-owned site files assembled above.
st.iframe(_build_page(), width="stretch", height=900)
