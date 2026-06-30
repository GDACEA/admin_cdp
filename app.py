import base64
import hashlib
import importlib

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

import variables as vars


# ==========================
# CONFIG GENERAL
# ==========================
st.set_page_config(
    page_title="Gestión CDP",
    layout="wide",
    page_icon="images/favicon-32x32.png",
)

st.logo(
    "images/LogoCDP.png",
    size="large",
    icon_image="images/LogoCDP.png",
)


# ==========================
# DB
# ==========================
engine = create_engine(
    "postgresql://gda_prod:Cea2025.!@172.20.4.17:5432/GDA"
)


# ==========================
# HELPERS
# ==========================
def add_bg_from_local(image_file):
    with open(image_file, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown(
        f"""
        <style>
        [data-testid="stAppViewContainer"] {{
            background: url("data:image/png;base64,{encoded}") no-repeat top center fixed;
            background-size: cover;
        }}

        [data-testid="stAppViewContainer"]::before {{
            content: "";
            position: absolute;
            inset: 0;
            background: rgba(0,0,0,0.45);
            z-index: 0;
        }}

        .main, .block-container {{
            background-color: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def limpiar_fondo_login():
    st.markdown(
        """
        <style>
        [data-testid="stAppViewContainer"] {
            background: none !important;
        }

        [data-testid="stAppViewContainer"]::before {
            display: none !important;
        }

        .main, .block-container {
            background-color: transparent !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=300)
def cargar_usuarios():
    query = """
    SELECT *
    FROM dbo.cdp_credentials
    ORDER BY nombre
    """
    return pd.read_sql(query, con=engine)


def inicializar_session_state():
    defaults = {
        "authenticated": False,
        "admin": False,
        "user": None,
        "cargo": None,
        "permits_json": {},
        "permits_projects": {},
        "login_username": "",
        "login_password": "",
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def login():
    add_bg_from_local("images/home_upload_2.jpeg")

    df_people = cargar_usuarios()

    users_validos = df_people[
        df_people["cargo"].isin(["ADMIN"] + vars.cargos_gestores_proyecto)
    ].copy()

    left, center, right = st.columns([1, 2, 1])

    with center:
        with st.container(border=True):
            st.title("Iniciar sesión")

            with st.form("login_form", clear_on_submit=False):
                username = st.text_input(
                    "Usuario",
                    key="login_username",
                    autocomplete="username",
                )

                password = st.text_input(
                    "Contraseña",
                    type="password",
                    key="login_password",
                    autocomplete="current-password",
                )

                submitted = st.form_submit_button(
                    "Ingresar",
                    use_container_width=True,
                )

            if submitted:
                username = username.strip()

                existe_usuario = username in users_validos["usuario"].values

                if not existe_usuario:
                    st.error("Usuario o contraseña incorrectos")
                    return

                user_row = users_validos.loc[
                    users_validos["usuario"] == username
                ].iloc[0]

                password_hash = hashlib.sha256(
                    password.encode("utf-8")
                ).hexdigest()

                if user_row["contraseña"] != password_hash:
                    st.error("Usuario o contraseña incorrectos")
                    return

                st.session_state["authenticated"] = True
                st.session_state["user"] = username
                st.session_state["cargo"] = user_row["cargo"]
                st.session_state["admin"] = (
                    username == "admin" or user_row["cargo"] == "ADMIN"
                )

                st.session_state["permits_json"] = user_row.get(
                    "permisos_clientes",
                    {},
                )

                st.session_state["permits_projects"] = user_row.get(
                    "permisos",
                    {},
                )

                st.success(f"Bienvenido/a {username}")
                st.rerun()


def cerrar_sesion():
    claves_a_limpiar = [
        "authenticated",
        "admin",
        "user",
        "cargo",
        "permits_json",
        "permits_projects",
        "main_navigation",
        "login_username",
        "login_password",
    ]

    for key in claves_a_limpiar:
        if key in st.session_state:
            del st.session_state[key]

    st.rerun()


def obtener_paginas_disponibles():
    cargo = st.session_state.get("cargo")
    es_admin = st.session_state.get("admin", False)

    pages = []

    for page in vars.PAGES_CONFIG:
        if not page.get("enabled", True):
            continue

        roles = page.get("roles", [])

        if es_admin or not roles or cargo in roles:
            pages.append(page)

    return sorted(
        pages,
        key=lambda x: x.get("order", 999),
    )


def render_sidebar():
    pages = obtener_paginas_disponibles()

    if not pages:
        st.sidebar.warning("No tienes vistas disponibles.")
        st.stop()

    labels = [
        f"{p.get('icon', '')} {p['label']}"
        for p in pages
    ]

    with st.sidebar:
        st.caption("Usuario")
        st.write(f"**{st.session_state.get('user', '')}**")

        st.caption("Cargo")
        st.write(f"**{st.session_state.get('cargo', '')}**")

        st.write("---")

        st.subheader("Menú")

        selected_label = st.radio(
            "Selecciona una vista",
            labels,
            key="main_navigation",
            label_visibility="collapsed",
        )

        selected_page = pages[labels.index(selected_label)]

        st.write("---")

        return selected_page


def cargar_vista(selected_page):
    try:
        module = importlib.import_module(selected_page["view"])
    except ModuleNotFoundError as e:
        st.error(
            f"No se pudo cargar la vista: {selected_page['view']}"
        )
        st.exception(e)
        st.stop()

    if not hasattr(module, "render"):
        st.error(
            f"La vista `{selected_page['view']}` no tiene función render()."
        )
        st.stop()

    module.render()


# ==========================
# APP
# ==========================
def main():
    inicializar_session_state()

    if not st.session_state["authenticated"]:
        login()
        st.stop()

    limpiar_fondo_login()

    selected_page = render_sidebar()

    cargar_vista(selected_page)

    with st.sidebar:
        st.write("---")
        st.subheader("Sesión")

        if st.button("Cerrar sesión", use_container_width=True):
            cerrar_sesion()


if __name__ == "__main__":
    main()
