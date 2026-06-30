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

        # Perfil bajo el último control de navegación.
        avatar_col, details_col = st.columns([1, 3], vertical_alignment="center")
        name = st.session_state.get("name") or st.session_state.get("display_name") or "Usuario"
        email = st.session_state.get("email", "")
        photo = st.session_state.get("profile_photo")
        with avatar_col:
            if photo:
                encoded_photo = base64.b64encode(photo).decode("ascii")
                st.markdown(
                    f'<img src="data:image/jpeg;base64,{encoded_photo}" '
                    'style="width:56px;height:56px;border-radius:50%;object-fit:cover" '
                    'alt="Foto de perfil">',
                    unsafe_allow_html=True,
                )
            else:
                initials = "".join(part[0] for part in name.split()[:2] if part).upper() or "U"
                st.markdown(
                    '<div style="width:56px;height:56px;border-radius:50%;background:#e5e7eb;'
                    'display:flex;align-items:center;justify-content:center;font-weight:700;'
                    f'color:#374151" aria-label="Avatar">{html.escape(initials)}</div>',
                    unsafe_allow_html=True,
                )
        with details_col:
            st.markdown(f"**{html.escape(name)}**")
            st.caption(email)

        if st.session_state.get("graph_notice"):
            st.caption(st.session_state["graph_notice"])

        if st.button("Cerrar sesión", use_container_width=True):
            logout()

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

if __name__ == "__main__":
    main()
