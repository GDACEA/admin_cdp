import streamlit as st
import streamlit.components.v1 as components

def render():
    st.title("Cumplimiento de terreno")

    powerbi_url = "https://app.powerbi.com/view?r=eyJrIjoiYjI3MTMwZWMtOTg4NS00NjQ4LTg0MDQtMjc4ZDk5MTM3Y2U3IiwidCI6ImU2YzcyN2QxLTVmODUtNDcxMy1iYzI0LTJjMzgyZTVkM2E5OSJ9"

    scale = 0.60
    iframe_width = 100 / scale
    iframe_height = 1680
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