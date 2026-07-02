import importlib
import base64
import html

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

import config
import variables as vars
from auth import AuthenticationError, logout, require_authentication


# ==========================
# CONFIG GENERAL
# ==========================
st.set_page_config(
    page_title=config.APP_NAME,
    layout="wide",
    page_icon=config.APP_PAGE_ICON,
)

# ==========================
# DB
# ==========================
engine = create_engine(config.GDA_DATABASE_URL, pool_pre_ping=config.DATABASE_POOL_PRE_PING)


# ==========================
# HELPERS
# ==========================
def limpiar_fondo_login():
    st.markdown(
        """
        <style>
        :root {
            color-scheme: dark;
        }

        [data-testid="stAppViewContainer"] {
            background: #050816 !important;
            color: #f8fafc !important;
        }

        [data-testid="stAppViewContainer"]::before {
            display: none !important;
        }

        .main, .block-container {
            background-color: rgba(5, 8, 20, 0.94) !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            box-shadow: 0 0 50px rgba(0, 0, 0, 0.24) !important;
        }

        [data-testid="stSidebar"] > div:first-child {
            background: #070b19 !important;
            color: #f8fafc !important;
            display: flex !important;
            flex-direction: column !important;
            min-height: 100vh !important;
            padding: 1rem 0.75rem 1.25rem !important;
        }

        button,
        input[type="submit"],
        input[type="button"],
        .stButton>button,
        .stDownloadButton button,
        [data-testid="stSidebar"] .stButton>button,
        [data-testid="stSidebar"] button,
        [data-testid="stAppViewContainer"] button {
            background-color: rgb(0, 47, 203) !important;
            color: #ffffff !important;
            border-color: rgba(0, 47, 203, 0.75) !important;
            box-shadow: none !important;
        }

        input[type="checkbox"],
        input[type="radio"] {
            accent-color: rgb(0, 47, 203) !important;
            border-color: rgb(0, 47, 203) !important;
        }

        [data-testid="stSidebar"] .stRadio input[type="radio"],
        [data-testid="stSidebar"] .stRadio input[type="radio"] + label::before,
        [data-testid="stSidebar"] .stRadio input[type="radio"] + label::after {
            border-color: rgb(0, 47, 203) !important;
        }

        [data-testid="stSidebar"] .stRadio input[type="radio"]:checked + label::before,
        [data-testid="stSidebar"] .stRadio input[type="radio"]:checked + label::after {
            background-color: rgb(0, 47, 203) !important;
            border-color: rgb(0, 47, 203) !important;
            box-shadow: 0 0 0 0.15rem rgba(0, 47, 203, 0.24) !important;
        }

        [data-testid="stSidebar"] .stRadio label,
        [data-testid="stSidebar"] .stRadio>div>div>label,
        [data-testid="stSidebar"] .stRadio>div>div>div {
            color: #f8fafc !important;
        }

        [data-testid="stSidebar"] .stRadio>div>div>label {
            display: inline-flex;
            align-items: center;
        }

        [data-testid="stSidebar"] .stRadio>div>div>label::before {
            content: "";
            display: inline-block;
            width: 18px;
            height: 18px;
            margin-right: 0.5rem;
            flex-shrink: 0;
            background-size: contain;
            background-repeat: no-repeat;
            background-position: center;
        }

        [data-testid="stSidebar"] .stRadio>div>div:nth-of-type(1) label::before {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='rgb(0,47,203)' d='M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5c-1.38 0-2.5-1.12-2.5-2.5S10.62 6.5 12 6.5s2.5 1.12 2.5 2.5S13.38 11.5 12 11.5z'/%3E%3C/svg%3E");
        }

        [data-testid="stSidebar"] .stRadio>div>div:nth-of-type(2) label::before {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='rgb(0,47,203)' d='M12 2a5 5 0 0 0-5 5v3H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8a2 2 0 0 0-2-2h-1V7a5 5 0 0 0-5-5zm0 2a3 3 0 0 1 3 3v3H9V7a3 3 0 0 1 3-3zm-5 10h10v6H7v-6z'/%3E%3C/svg%3E");
        }

        [data-testid="stSidebar"] .stRadio>div>div:nth-of-type(3) label::before {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='rgb(0,47,203)' d='M9 16.2l-3.5-3.5 1.4-1.4L9 13.4l7.1-7.1 1.4 1.4L9 16.2z'/%3E%3C/svg%3E");
        }

        [data-testid="stSidebar"] .stRadio>div>div:nth-of-type(4) label::before {
            background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='rgb(0,47,203)' d='M19.14 12.94a7.07 7.07 0 0 0 0-1.88l2.03-1.58a.5.5 0 0 0 .12-.63l-1.92-3.32a.5.5 0 0 0-.61-.22l-2.39.96a7.05 7.05 0 0 0-1.62-.94L14.9 2.81a.5.5 0 0 0-.5-.31h-3.8a.5.5 0 0 0-.5.31l-.38 2.42a7.05 7.05 0 0 0-1.62.94l-2.39-.96a.5.5 0 0 0-.61.22L2.7 8.85a.5.5 0 0 0 .12.63l2.03 1.58a7.07 7.07 0 0 0 0 1.88L2.82 14.5a.5.5 0 0 0-.12.63l1.92 3.32c.14.25.44.35.7.22l2.39-.96c.5.37 1.04.66 1.62.94l.38 2.42c.05.28.29.48.57.48h3.8c.28 0 .52-.2.57-.48l.38-2.42c.58-.28 1.12-.57 1.62-.94l2.39.96c.26.11.56.03.7-.22l1.92-3.32a.5.5 0 0 0-.12-.63l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 15.5 12 3.5 3.5 0 0 1 12 15.5z'/%3E%3C/svg%3E");
        }

        [data-testid="stDataEditor"] [aria-selected="true"],
        [data-testid="stDataEditor"] [data-selected="true"],
        [data-testid="stDataEditor"] [role="gridcell"][aria-selected="true"],
        [data-testid="stDataEditor"] [role="gridcell"][data-selected="true"] {
            outline: 2px solid rgb(0, 47, 203) !important;
            border-color: rgb(0, 47, 203) !important;
            box-shadow: inset 0 0 0 1px rgb(0, 47, 203) !important;
            background-color: rgba(0, 47, 203, 0.08) !important;
        }

        [data-testid="stSidebar"] .stRadio>div>div>label,
        [data-testid="stSidebar"] .stRadio>div>div>div {
            color: #f8fafc !important;
        }

        [data-testid="stSidebar"] .stSelectbox>div>div,
        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] select {
            background-color: rgba(255, 255, 255, 0.05) !important;
            color: #f8fafc !important;
            border-color: rgba(255, 255, 255, 0.14) !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile {
            margin-top: auto !important;
            margin-bottom: 1rem !important;
            padding-top: 1rem !important;
            border-top: 1px solid rgba(255, 255, 255, 0.08) !important;
            order: 999 !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile-row {
            display: flex !important;
            align-items: center !important;
            gap: 0.75rem !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile-avatar,
        [data-testid="stSidebar"] .sidebar-user-profile-avatar .avatar-img,
        [data-testid="stSidebar"] .sidebar-user-profile-avatar .avatar-placeholder {
            width: 56px !important;
            height: 56px !important;
            min-width: 56px !important;
            min-height: 56px !important;
            border-radius: 50% !important;
            overflow: hidden !important;
            display: inline-flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: rgba(255, 255, 255, 0.08) !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile-avatar .avatar-img {
            width: 100% !important;
            height: 100% !important;
            object-fit: cover !important;
            border-radius: 50% !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile-avatar .avatar-placeholder {
            color: #ffffff !important;
            font-weight: 700 !important;
            font-size: 1rem !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile .user-name {
            color: #ffffff !important;
            font-weight: 700 !important;
        }

        [data-testid="stSidebar"] .sidebar-user-profile .user-email {
            color: rgba(255, 255, 255, 0.72) !important;
            font-size: 0.9rem !important;
        }

        [data-testid="stSidebar"] input,
        [data-testid="stSidebar"] textarea,
        [data-testid="stSidebar"] select,
        [data-testid="stSidebar"] .stSelectbox>div>div {
            background-color: rgba(255, 255, 255, 0.04) !important;
            color: #f8fafc !important;
            border-color: rgba(255, 255, 255, 0.12) !important;
        }

        [data-testid="stAppViewContainer"] a {
            color: rgb(0, 47, 203) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=config.CACHE_TTL_LONG)
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
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def cargar_autorizacion_sso(username):
    """Carga sin cambios el rol y los permisos internos del usuario Entra."""
    df_people = cargar_usuarios()
    users_validos = df_people[
        df_people["cargo"].isin(["ADMIN"] + vars.cargos_gestores_proyecto)
    ].copy()
    coincidencias = users_validos[
        users_validos["usuario"].astype(str).str.strip().str.lower() == username
    ]

    if coincidencias.empty:
        st.error("Tu cuenta está autenticada, pero no tiene acceso habilitado en CDP.")
        st.stop()

    user_row = coincidencias.iloc[0]
    st.session_state["user"] = username
    st.session_state["cargo"] = user_row["cargo"]
    st.session_state["admin"] = (
        username == "admin" or user_row["cargo"] == "ADMIN"
    )
    st.session_state["permits_json"] = user_row.get("permisos_clientes", {})
    st.session_state["permits_projects"] = user_row.get("permisos", {})


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
        p['label']
        for p in pages
    ]

    with st.sidebar:
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


def render_sidebar_profile():
    name = st.session_state.get("name") or st.session_state.get("display_name") or "Usuario"
    email = st.session_state.get("email", "")
    photo = st.session_state.get("profile_photo")

    if photo:
        encoded_photo = base64.b64encode(photo).decode("ascii")
        avatar_html = (
            f'<img src="data:image/jpeg;base64,{encoded_photo}" '
            'class="avatar-img" alt="Foto de perfil">'
        )
    else:
        initials = "".join(part[0] for part in name.split()[:2] if part).upper() or "U"
        avatar_html = (
            '<div class="avatar-placeholder">'
            f'{html.escape(initials)}'
            '</div>'
        )

    profile_html = f"""
    <div class='sidebar-user-profile'>
        <div class='sidebar-user-profile-row'>
            <div class='sidebar-user-profile-avatar'>
                {avatar_html}
            </div>
            <div class='sidebar-user-profile-details'>
                <div class='user-name'>{html.escape(name)}</div>
                {'<div class="user-email">' + html.escape(email) + '</div>' if email else ''}
            </div>
        </div>
    </div>
    """

    with st.sidebar:
        st.markdown(profile_html, unsafe_allow_html=True)
        if st.session_state.get("graph_notice"):
            st.markdown(
                f'<div class="user-email">{html.escape(st.session_state["graph_notice"])}</div>',
                unsafe_allow_html=True,
            )
        if st.button("Cerrar Sesión", use_container_width=True):
            logout()


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
    try:
        identity = require_authentication()
    except AuthenticationError as exc:
        st.error(str(exc))
        st.stop()

    inicializar_session_state()
    cargar_autorizacion_sso(identity["username"])

    st.logo(
        config.APP_LOGO,
        size="large",
        icon_image=config.APP_LOGO,
    )

    limpiar_fondo_login()

    selected_page = render_sidebar()

    cargar_vista(selected_page)
    render_sidebar_profile()

if __name__ == "__main__":
    main()
