import sys
from pathlib import Path
import streamlit as st

# Ensure project root path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from frontend.components import inject_assets, lottie_animation, command_palette_hint


def page():
    st.set_page_config(page_title="AI Study Mentor — Hero", layout="wide")
    inject_assets()

    st.markdown("""
    <div class="hero-gradient">
      <h1 style="margin:0;font-size:3rem;color:#fff;">AI Study Mentor</h1>
      <p style="font-size:1.1rem;color:#e2e8f0;">Apple-level polish, Notion-like smoothness, RAG-powered tutoring.</p>
      <div style="margin-top:12px;">
        <span class="badge">RAG-powered</span>
        <span class="badge">Privacy-first</span>
        <span class="badge">Gemini Cloud</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([0.55, 0.45])
    with col1:
        st.markdown("""
        <div class="glass-card glass-strong">
          <h3 style="margin-top:0">Feature Showcase</h3>
          <ul style="color:#cbd5e1">
            <li>Concept Map Generator (interactive + export)</li>
            <li>Socratic Tutor Mode (guiding questions)</li>
            <li>Multi-Document Synthesis (compare & unify)</li>
            <li>Adaptive Tutor (ELI5 → Expert)</li>
            <li>LaTeX Math Rendering with steps</li>
          </ul>
          <div style="margin-top:10px">
            <button class="btn-animated" onclick="window.location.href='/'">Enter App</button>
            <button class="btn-animated" onclick="window._aim_ui && window._aim_ui.confetti()" style="margin-left:8px">Celebrate</button>
          </div>
        </div>
        """, unsafe_allow_html=True)
        command_palette_hint()
    with col2:
        # Minimal lottie data (a simple pulsating circle animation)
        lottie_animation({
            "v": "5.7.4",
            "fr": 30,
            "ip": 0,
            "op": 60,
            "w": 400,
            "h": 200,
            "nm": "pulse",
            "ddd":0,
            "assets":[],
            "layers":[{
                "ddd":0,"ty":4,"nm":"circle","sr":1,
                "ks":{"o":{"a":0,"k":100},"r":{"a":0,"k":0},
                    "p":{"a":0,"k":[200,100,0]},
                    "a":{"a":0,"k":[0,0,0]},
                    "s":{"a":1,"k":[{"i":{"x":[0.667,0.667,0.667],"y":[0.667,0.667,0.667]},"o":{"x":[0.333,0.333,0.333],"y":[0.333,0.333,0.333]},"t":0,"s":[80,80,100]},{"t":60,"s":[120,120,100]}]}
                },
                "shapes":[{"ty":"el","p":{"a":0,"k":[0,0]},"s":{"a":0,"k":[80,80]},"nm":"Ellipse"},{"ty":"fl","c":{"a":0,"k":[0.486,0.227,0.929,1]},"o":{"a":0,"k":90},"nm":"Fill"}]
            }]}, width=600, height=260, loop=True)

    st.markdown("""
    <div class="glass-card" style="margin-top:12px">
      <h3 style="margin-top:0">Trust & Quality</h3>
      <p style="color:#cbd5e1">GitHub-quality dark mode, Linear-style animations, Notion-level smoothness.</p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    page()