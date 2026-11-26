from __future__ import annotations

import base64
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote

import streamlit as st
import streamlit.components.v1 as components


ROOT = Path(__file__).resolve().parent
SCRIPT_TAG = re.compile(
    r"(?P<opening><script\b[^>]*\bsrc=(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)[^>]*>)\s*</script>",
    re.IGNORECASE | re.DOTALL,
)
STYLESHEET_TAG = re.compile(
    r"<link\b(?=[^>]*\brel=['\"]stylesheet['\"])[^>]*>",
    re.IGNORECASE,
)
PRELOAD_TAG = re.compile(
    r"<link\b(?=[^>]*\brel=['\"]preload['\"])[^>]*>",
    re.IGNORECASE,
)
ASSET_ATTRIBUTE = re.compile(
    r"(?P<attribute>\b(?:src|href)\s*=\s*)(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
    re.IGNORECASE,
)
CSS_URL = re.compile(
    r"url\(\s*(?P<quote>['\"]?)(?P<path>[^'\")]+)(?P=quote)\s*\)",
    re.IGNORECASE,
)


def _asset_path(relative_path: str, base: Path = ROOT) -> Path:
    asset = (base / unquote(relative_path.split("?", 1)[0].split("#", 1)[0])).resolve()
    try:
        asset.relative_to(ROOT)
    except ValueError as error:
        raise ValueError(f"Asset path is outside the site directory: {relative_path}") from error
    if not asset.is_file():
        raise FileNotFoundError(f"Site asset not found: {relative_path}")
    return asset


def _data_uri(asset: Path) -> str:
    media_type = {
        ".js": "text/javascript",
        ".woff2": "font/woff2",
    }.get(asset.suffix.lower(), mimetypes.guess_type(asset.name)[0])
    if media_type is None:
        raise ValueError(f"Cannot determine the media type for {asset.name}")
    encoded = base64.b64encode(asset.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


def _inline_css(css: str, stylesheet: Path) -> str:
    def replace_url(match: re.Match[str]) -> str:
        resource = match.group("path").strip()
        if resource.startswith(("data:", "http:", "https:", "#", "//")):
            return match.group(0)
        uri = _data_uri(_asset_path(resource, stylesheet.parent))
        return f"url('{uri}')"

    return CSS_URL.sub(replace_url, css)


def build_site_document() -> str:
    document = (ROOT / "index.html").read_text(encoding="utf-8")
    document = PRELOAD_TAG.sub("", document)

    def inline_script(match: re.Match[str]) -> str:
        script = _asset_path(match.group("path")).read_text(encoding="utf-8")
        opening = re.sub(
            r"\s+src=(['\"]).*?\1",
            "",
            match.group("opening"),
            count=1,
            flags=re.IGNORECASE,
        )
        return f"{opening}{script}</script>"

    document = SCRIPT_TAG.sub(inline_script, document)

    def inline_stylesheet(match: re.Match[str]) -> str:
        href = re.search(r"\bhref=['\"]([^'\"]+)['\"]", match.group(0), re.IGNORECASE)
        if href is None:
            raise ValueError("The page stylesheet link has no href")
        stylesheet = _asset_path(href.group(1))
        css = _inline_css(stylesheet.read_text(encoding="utf-8"), stylesheet)
        return f"<style>\n{css}\n</style>"

    document = STYLESHEET_TAG.sub(inline_stylesheet, document)

    def inline_asset(match: re.Match[str]) -> str:
        resource = match.group("path")
        if resource.startswith(("data:", "http:", "https:", "#", "//")):
            return match.group(0)
        uri = _data_uri(_asset_path(resource))
        return f"{match.group('attribute')}{match.group('quote')}{uri}{match.group('quote')}"

    return ASSET_ATTRIBUTE.sub(inline_asset, document)


def main() -> None:
    st.set_page_config(
        page_title="ODS 5 + ODS 9 · Guanajuato",
        page_icon="🌞",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.markdown(
        """
        <style>
        .stAppHeader, #MainMenu, footer { display: none; }
        .stMainBlockContainer { padding: 0; max-width: 100%; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    components.html(build_site_document(), height=900, scrolling=True)


if __name__ == "__main__":
    main()
