from __future__ import annotations

from typing import Optional, Dict, Any
import json

import streamlit as st
import os
from pathlib import Path


def inject_assets() -> None:
    """Inject global CSS and JS assets for glassmorphism and micro-interactions."""
    css_path = Path(__file__).resolve().parent / "static" / "style.css"
    # Also load the hackathon polished dark theme if available
    enhanced_css = Path(__file__).resolve().parent / "styles.css"
    js_path = Path(__file__).resolve().parent / "static" / "app.js"
    try:
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)
    except Exception:
        pass
    # Load enhanced dark theme for gradient, cards, badges, pipeline, etc.
    try:
        if enhanced_css.exists():
            st.markdown(f"<style>{enhanced_css.read_text()}</style>", unsafe_allow_html=True)
    except Exception:
        pass
    try:
        st.components.v1.html(
            f"""
            <script>{js_path.read_text()}</script>
            """,
            height=0,
        )
    except Exception:
        pass


def lottie_animation(src_json: str | Dict[str, Any], width: int = 600, height: int = 260, loop: bool = True) -> None:
    """Render a Lottie animation using lottie-web via CDN.

    - src_json: a JSON string or dict of the animation data
    """
    try:
        if isinstance(src_json, dict):
            data = json.dumps(src_json)
        else:
            data = src_json
        st.components.v1.html(
            f"""
            <div id="lottie-container" style="width:{width}px;height:{height}px"></div>
            <script src="https://cdnjs.cloudflare.com/ajax/libs/bodymovin/5.10.2/lottie.min.js"></script>
            <script>
              var animData = {data};
              var anim = lottie.loadAnimation({{
                container: document.getElementById('lottie-container'),
                renderer: 'svg',
                loop: {str(loop).lower()},
                autoplay: true,
                animationData: animData
              }});
            </script>
            """,
            height=height + 10,
        )
    except Exception as e:
        st.warning(f"Could not render Lottie: {e}")


def command_palette_hint() -> None:
    st.caption("Keyboard: Cmd+K opens command palette, Cmd+/ toggles sidebar")