import streamlit as st
import pandas as pd
import json
from sqlalchemy import create_engine, text
import config
import variables as vars


# ==========================
# DB
# ==========================
engine = create_engine(config.GDA_DATABASE_URL, pool_pre_ping=config.DATABASE_POOL_PRE_PING)


# ==========================
# HELPERS
# ==========================
def asegurar_dict(x):
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    if isinstance(x, str):
        try:
            return json.loads(x)
        except Exception:
            return {}
    return {}


def dumps_json(x):
    return json.dumps(x, ensure_ascii=False)


def normalizar_txt(x):
    return str(x or "").strip().upper()


def orden_jerarquia_cargo(cargo):
    jerarquia = {
        "ADMIN": 0,
        "GERENTE DE PROYECTO": 1,
        "GERENTE DE PROYECTOS": 1,
        "JEFE DE PROYECTO": 2,
        "JEFE DE PROYECTOS": 2,
        "COORDINADOR DE PROYECTO": 3,
        "COORDINADOR DE PROYECTOS": 3,
        "PROFESIONAL AMBIENTAL": 4,
        "ANALISTA DE DATOS AMBIENTALES": 5,
        "ESPECIALISTA": 6,
        "ANALISTA": 7,
        "PROFESIONAL": 8,
        "TECNICO": 9,
        "TÉCNICO": 9,
    }
    return jerarquia.get(normalizar_txt(cargo), 99)


# ==========================
# DATA
# ==========================
@st.cache_data(ttl=config.CACHE_TTL_LONG)
def cargar_personas_admin():
    query = """
    SELECT
        uuid,
        nombre,
        cargo,
        correo,
        estado,
        permisos,
        permisos_clientes
    FROM dbo.cdp_credentials
    WHERE estado = 'Activo'
    ORDER BY nombre ASC
    """
    return pd.read_sql(query, con=engine)


@st.cache_data(ttl=config.CACHE_TTL_LONG)
def cargar_proyectos_admin():
    query = """
    SELECT
        cliente,
        codigo_proyecto,
        estado
    FROM dbo.dt_projects
    ORDER BY cliente, codigo_proyecto
    """
    return pd.read_sql(query, con=engine)


# ==========================
# DB ACTIONS
# ==========================
def proyecto_existe(codigo_proyecto):
    query = text("""
        SELECT COUNT(*) AS n
        FROM dbo.dt_projects
        WHERE codigo_proyecto = :codigo_proyecto
    """)

    with engine.begin() as conn:
        result = conn.execute(
            query,
            {"codigo_proyecto": codigo_proyecto}
        ).scalar()

    return result > 0


def guardar_proyecto(cliente, codigo_proyecto, estado):
    cliente = cliente.strip().upper()
    codigo_proyecto = codigo_proyecto.strip().upper()

    if proyecto_existe(codigo_proyecto):
        query = text("""
            UPDATE dbo.dt_projects
            SET
                cliente = :cliente,
                estado = :estado
            WHERE codigo_proyecto = :codigo_proyecto
        """)
    else:
        query = text("""
            INSERT INTO dbo.dt_projects (
                cliente,
                codigo_proyecto,
                estado
            )
            VALUES (
                :cliente,
                :codigo_proyecto,
                :estado
            )
        """)

    with engine.begin() as conn:
        conn.execute(query, {
            "cliente": cliente,
            "codigo_proyecto": codigo_proyecto,
            "estado": estado,
        })


def sincronizar_cliente_proyecto_en_todos_los_usuarios(cliente, codigo_proyecto):
    cliente = cliente.strip().upper()
    codigo_proyecto = codigo_proyecto.strip().upper()

    df_users = pd.read_sql(
        """
        SELECT uuid, nombre, permisos, permisos_clientes
        FROM dbo.cdp_credentials
        """,
        con=engine
    )

    update_query = text("""
        UPDATE dbo.cdp_credentials
        SET
            permisos = CAST(:permisos AS jsonb),
            permisos_clientes = CAST(:permisos_clientes AS jsonb)
        WHERE uuid = :uuid
    """)

    with engine.begin() as conn:
        for _, row in df_users.iterrows():
            permisos = asegurar_dict(row["permisos"])
            permisos_clientes = asegurar_dict(row["permisos_clientes"])

            nombre_usuario = str(row.get("nombre", "")).strip().lower()

            if nombre_usuario == "admin":
                permisos[codigo_proyecto] = 1
                permisos_clientes[cliente] = 1
            else:
                if codigo_proyecto not in permisos:
                    permisos[codigo_proyecto] = 0
                if cliente not in permisos_clientes:
                    permisos_clientes[cliente] = 0

            conn.execute(update_query, {
                "uuid": row["uuid"],
                "permisos": dumps_json(permisos),
                "permisos_clientes": dumps_json(permisos_clientes),
            })


def actualizar_permisos_usuario(uuid, permisos, permisos_clientes):
    query = text("""
        UPDATE dbo.cdp_credentials
        SET
            permisos = CAST(:permisos AS jsonb),
            permisos_clientes = CAST(:permisos_clientes AS jsonb)
        WHERE uuid = :uuid
    """)

    with engine.begin() as conn:
        conn.execute(query, {
            "uuid": uuid,
            "permisos": dumps_json(permisos),
            "permisos_clientes": dumps_json(permisos_clientes),
        })


def set_permiso_usuario_proyecto(row_usuario, cliente, codigo_proyecto, valor):
    permisos = asegurar_dict(row_usuario["permisos"])
    permisos_clientes = asegurar_dict(row_usuario["permisos_clientes"])

    permisos[codigo_proyecto] = int(valor)

    if valor == 1:
        permisos_clientes[cliente] = 1

    if valor == 0:
        df_proy = cargar_proyectos_admin()
        proyectos_cliente = df_proy.loc[
            df_proy["cliente"] == cliente,
            "codigo_proyecto"
        ].dropna().tolist()

        tiene_otro_proyecto_cliente = any(
            permisos.get(p, 0) == 1
            for p in proyectos_cliente
            if p != codigo_proyecto
        )

        permisos_clientes[cliente] = 1 if tiene_otro_proyecto_cliente else 0

    actualizar_permisos_usuario(
        uuid=row_usuario["uuid"],
        permisos=permisos,
        permisos_clientes=permisos_clientes,
    )


# ==========================
# VIEW
# ==========================
def render():

    if not st.session_state.get("admin", False):
        st.warning("No tienes permisos de administrador para acceder a esta página.")
        st.stop()

    df_people = cargar_personas_admin()
    df_proy = cargar_proyectos_admin()

    if "admin_tab_activo" not in st.session_state:
        st.session_state["admin_tab_activo"] = "🔐 Asignar permisos"

    df_activos = df_proy[df_proy["estado"] == "Activo"].copy()

    # ==========================
    # HEADER
    # ==========================
    st.title("Administrador CDP")
    st.caption("Gestión de clientes, proyectos y permisos de acceso.")

    tab_activo = st.radio(
        "Sección",
        [
            "➕ Cliente / Proyecto",
            "🔐 Asignar permisos",
        ],
        horizontal=True,
        key="admin_tab_activo",
        label_visibility="collapsed",
    )

    # ==========================
    # SIDEBAR FILTROS
    # ==========================
    cliente_sel = None
    proyecto_sel = None

    if tab_activo == "🔐 Asignar permisos":
        with st.sidebar:
            st.subheader("Filtros")

            if df_activos.empty:
                st.warning("No hay proyectos activos.")
            else:
                clientes = sorted(df_activos["cliente"].dropna().unique().tolist())

                cliente_sel = st.selectbox(
                    "Cliente",
                    clientes,
                    key="admin_sidebar_cliente"
                )

                proyectos_cliente = sorted(
                    df_activos.loc[
                        df_activos["cliente"] == cliente_sel,
                        "codigo_proyecto"
                    ].dropna().unique().tolist()
                )

                proyecto_sel = st.selectbox(
                    "Proyecto",
                    proyectos_cliente,
                    key="admin_sidebar_proyecto"
                )

    # ==========================
    # HEADER
    # ==========================
    st.title("Administrador CDP")
    st.caption("Gestión de clientes, proyectos y permisos de acceso.")

    if tab_activo == "🔐 Asignar permisos" and cliente_sel and proyecto_sel:
        st.subheader("Proyecto seleccionado")

        c1, c2, c3 = st.columns(3)
        c1.metric("Cliente", cliente_sel)
        c2.metric("Proyecto", proyecto_sel)
        c3.metric("Usuario", st.session_state.get("user", "admin"))

    st.write("---")

    # =====================================================
    # TAB 1: CREAR CLIENTE / PROYECTO
    # =====================================================
    if tab_activo == "➕ Cliente / Proyecto":
        st.subheader("Agregar nuevo cliente-proyecto")

        st.info(
            "Al crear un nuevo cliente-proyecto, se agregan automáticamente "
            "las llaves en los JSON de todos los usuarios. El usuario admin queda habilitado automáticamente."
        )

        with st.container(border=True):
            col1, col2, col3 = st.columns([1, 1, 1])

            with col1:
                cliente_new = st.text_input(
                    "Código cliente",
                    placeholder="Ej: STK"
                )

            with col2:
                proyecto_new = st.text_input(
                    "Código proyecto",
                    placeholder="Ej: STK001"
                )

            with col3:
                estado_new = st.selectbox(
                    "Estado",
                    ["Activo", "Inactivo"]
                )

            if st.button(
                "Guardar cliente-proyecto",
                type="primary",
                use_container_width=True
            ):
                if not cliente_new or not proyecto_new:
                    st.error("Debes ingresar cliente y código de proyecto.")
                    st.stop()

                cliente_new = cliente_new.strip().upper()
                proyecto_new = proyecto_new.strip().upper()

                guardar_proyecto(
                    cliente=cliente_new,
                    codigo_proyecto=proyecto_new,
                    estado=estado_new,
                )

                sincronizar_cliente_proyecto_en_todos_los_usuarios(
                    cliente=cliente_new,
                    codigo_proyecto=proyecto_new,
                )

                st.cache_data.clear()
                st.success(
                    f"Cliente-proyecto {cliente_new} / {proyecto_new} guardado "
                    "y sincronizado en todos los usuarios."
                )
                st.rerun()

        st.write("### Proyectos registrados")

        st.dataframe(
            df_proy,
            use_container_width=True,
            hide_index=True
        )

    # =====================================================
    # TAB 2: ASIGNAR PERMISOS
    # =====================================================
    if tab_activo == "🔐 Asignar permisos":
        st.subheader("Asignar colaboradores a proyecto")

        if df_activos.empty:
            st.info("No hay proyectos activos registrados.")
            st.stop()

        if not cliente_sel or not proyecto_sel:
            st.info("Selecciona cliente y proyecto desde el sidebar.")
            st.stop()

        df_people_perm = df_people[
            df_people["nombre"].astype(str).str.lower().str.strip() != "admin"
        ].copy()

        df_people_perm = df_people_perm[
            df_people_perm["cargo"].isin(vars.cargos_gestores_proyecto)
        ].copy()

        if df_people_perm.empty:
            st.warning("No hay jefes/coordinadores disponibles para asignar.")
            st.stop()

        df_tmp = df_people_perm.copy()
        df_tmp["permisos_dict"] = df_tmp["permisos"].apply(asegurar_dict)

        df_asignados = df_tmp[
            df_tmp["permisos_dict"].apply(
                lambda d: d.get(proyecto_sel, 0) == 1
            )
        ].copy()

        if not df_asignados.empty:
            df_asignados["orden_cargo"] = df_asignados["cargo"].apply(
                orden_jerarquia_cargo
            )

            df_asignados = df_asignados.sort_values(
                by=["orden_cargo", "nombre"],
                ascending=[True, True]
            )

        # ==========================
        # AGREGAR COLABORADOR
        # ==========================
        with st.container(border=True):
            st.markdown("### Agregar colaborador")

            uuids_asignados = (
                df_asignados["uuid"].tolist()
                if not df_asignados.empty
                else []
            )

            df_disponibles = df_people_perm[
                ~df_people_perm["uuid"].isin(uuids_asignados)
            ].copy()

            if df_disponibles.empty:
                st.success("Todos los colaboradores activos ya están asignados.")
            else:
                col_a, col_b, col_c = st.columns([2, 2, 1])

                with col_a:
                    colaborador_add = st.selectbox(
                        "Colaborador",
                        df_disponibles["nombre"].tolist(),
                        key=f"add_colaborador_{cliente_sel}_{proyecto_sel}"
                    )

                row_add = df_disponibles[
                    df_disponibles["nombre"] == colaborador_add
                ].iloc[0]

                with col_b:
                    st.write("Cargo / Correo")
                    st.caption(f"{row_add['cargo']} · {row_add['correo']}")

                with col_c:
                    st.write("")
                    st.write("")
                    if st.button(
                        "Agregar",
                        type="primary",
                        use_container_width=True,
                        key=f"btn_add_{cliente_sel}_{proyecto_sel}"
                    ):
                        set_permiso_usuario_proyecto(
                            row_usuario=row_add,
                            cliente=cliente_sel,
                            codigo_proyecto=proyecto_sel,
                            valor=1,
                        )
                        st.cache_data.clear()
                        st.success("Colaborador agregado al proyecto.")
                        st.rerun()

        st.write("---")

        # ==========================
        # COLABORADORES ASIGNADOS
        # ==========================
        with st.container(border=True):
            st.markdown("### Colaboradores asignados")

            c1, c2, c3 = st.columns(3)
            c1.metric("Cliente", cliente_sel)
            c2.metric("Proyecto", proyecto_sel)
            c3.metric("Asignados", len(df_asignados))

            if df_asignados.empty:
                st.warning(
                    f"No hay colaboradores asignados al proyecto {proyecto_sel}."
                )
            else:
                for _, row in df_asignados.iterrows():
                    with st.container(border=True):
                        col_cargo, col_nombre, col_correo, col_btn = st.columns(
                            [1.3, 2.0, 2.0, 0.8],
                            vertical_alignment="center"
                        )

                        with col_cargo:
                            st.markdown(f"**{row['cargo']}**")

                        with col_nombre:
                            st.write(row["nombre"])

                        with col_correo:
                            st.caption(row["correo"])

                        with col_btn:
                            if st.button(
                                "Quitar",
                                key=f"quitar_{row['uuid']}_{proyecto_sel}",
                                use_container_width=True
                            ):
                                set_permiso_usuario_proyecto(
                                    row_usuario=row,
                                    cliente=cliente_sel,
                                    codigo_proyecto=proyecto_sel,
                                    valor=0,
                                )
                                st.cache_data.clear()
                                st.success("Colaborador removido del proyecto.")
                                st.rerun()
