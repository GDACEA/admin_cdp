import streamlit as st
import streamlit.components.v1 as components
import config

def render():
    st.title("Cumplimiento de terreno")

    powerbi_url = config.POWERBI_URL

    scale = config.POWERBI_SCALE
    iframe_width = 100 / scale
    iframe_height = config.POWERBI_IFRAME_HEIGHT
    container_height = int(iframe_height * scale)

    components.html(
        f"""
        <div style="
            width:100%;
            height:{container_height}px;
            overflow:hidden;
            background:#0a0f16;
        ">
            <iframe
                src="{powerbi_url}"
                scrolling="no"
                style="
                    width:{iframe_width}%;
                    height:{iframe_height}px;
                    border:0;
                    transform:scale({scale});
                    transform-origin:top left;
                    display:block;
                    overflow:hidden;
                "
                allowfullscreen>
            </iframe>
        </div>
        """,
        height=container_height,
        scrolling=False,
    )
