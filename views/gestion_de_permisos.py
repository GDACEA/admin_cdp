import streamlit as st
import pandas as pd
import json
from sqlalchemy import create_engine, text
import variables as vars


# ==========================
# DB
# ==========================
engine = create_engine(
    "postgresql://gda_prod:Cea2025.!@172.20.4.17:5432/GDA"
)


# ==========================
# HELPERS
# ==========================
def nombre_mostrar(nombre):
    partes = str(nombre).strip().split()
    if len(partes) >= 4:
        apellidos = partes[:2]
        nombres = partes[2:]
        return f"{' '.join(nombres)} {' '.join(apellidos)}"
    return nombre


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
        "GERENTE DE PROYECTO": 1,
        "GERENTE DE PROYECTOS": 1,
        "JEFE DE PROYECTO": 2,
        "JEFE DE PROYECTOS": 2,
        "COORDINADOR DE PROYECTO": 3,
        "COORDINADOR DE PROYECTOS": 3,
        "ANALISTA DE DATOS AMBIENTALES": 4,
        "PROFESIONAL AMBIENTAL": 5,
        "ESPECIALISTA": 6,
        "ANALISTA": 7,
        "PROFESIONAL": 8,
        "TECNICO": 9,
        "TÉCNICO": 9,
    }
    return jerarquia.get(normalizar_txt(cargo), 99)


def formato_colaborador(uuid, df):
    row = df.loc[df["uuid"] == uuid].iloc[0]
    nombre = nombre_mostrar(row["nombre"])
    return f"{nombre} ({row['cargo']})"


def es_usuario_logueado(row):
    keys_usuario = [
        "username",
        "usuario",
        "user",
        "nombre_usuario",
        "login",
        "correo",
        "email",
        "uuid",
        "user_uuid",
    ]

    ids_usuario = set()

    for key in keys_usuario:
        valor = st.session_state.get(key, "")
        valor_norm = normalizar_txt(valor)

        if valor_norm:
            ids_usuario.add(valor_norm)

            if "@" in valor_norm:
                ids_usuario.add(valor_norm.split("@")[0])

    row_nombre = normalizar_txt(row.get("nombre", ""))
    row_correo = normalizar_txt(row.get("correo", ""))
    row_uuid = normalizar_txt(row.get("uuid", ""))

    ids_fila = {row_nombre, row_correo, row_uuid}

    if row_correo and "@" in row_correo:
        ids_fila.add(row_correo.split("@")[0])

    return bool(ids_usuario.intersection(ids_fila))


# ==========================
# DATA
# ==========================
@st.cache_data(ttl=300)
def cargar_personas():
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


@st.cache_data(ttl=300)
def cargar_proyectos():
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
        df_proy = cargar_proyectos()

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

    st.title("Gestión de Permisos CDP")
    st.caption("Asignación de colaboradores a proyectos bajo tu administración.")

    df_people = cargar_personas()
    df_proy = cargar_proyectos()

    df_activos = df_proy[df_proy["estado"] == "Activo"].copy()

    if df_activos.empty:
        st.info("No hay proyectos activos registrados.")
        st.stop()

    # ==========================
    # Permisos del usuario logueado
    # ==========================
    es_admin = st.session_state.get("admin", False)

    permisos_proyectos_usuario = asegurar_dict(
        st.session_state.get("permits_projects", {})
    )

    if es_admin:
        df_proyectos_permitidos = df_activos.copy()
    else:
        df_proyectos_permitidos = df_activos[
            df_activos["codigo_proyecto"].apply(
                lambda p: permisos_proyectos_usuario.get(p, 0) == 1
            )
        ].copy()

    if df_proyectos_permitidos.empty:
        st.warning("No tienes proyectos asignados para administrar.")
        st.stop()

    # ==========================
    # Filtros en sidebar
    # ==========================
    clientes = sorted(
        df_proyectos_permitidos["cliente"].dropna().unique().tolist()
    )

    with st.sidebar:
        st.markdown("---")
        st.markdown("### Filtros")

        cliente_sel = st.selectbox(
            "Cliente",
            clientes,
            key="gest_perm_cliente_sel"
        )

        proyectos_cliente = sorted(
            df_proyectos_permitidos.loc[
                df_proyectos_permitidos["cliente"] == cliente_sel,
                "codigo_proyecto"
            ].dropna().unique().tolist()
        )

        proyecto_sel = st.selectbox(
            "Proyecto",
            proyectos_cliente,
            key="gest_perm_proyecto_sel"
        )

    # ==========================
    # Cargos
    # ==========================
    cargos_aplicables_norm = [
        normalizar_txt(cargo) for cargo in vars.cargos_aplicables
    ]

    cargos_gestores_norm = [
        normalizar_txt(cargo) for cargo in vars.cargos_gestores_proyecto
    ]

    cargos_visibles_norm = list(
        set(cargos_aplicables_norm + cargos_gestores_norm)
    )

    # ==========================
    # Base personas, sin admin
    # ==========================
    df_people_base = df_people.copy()

    df_people_base = df_people_base[
        df_people_base["nombre"].astype(str).str.lower().str.strip() != "admin"
    ].copy()

    # ==========================
    # Personas visibles asignadas
    # cargos_aplicables + cargos_gestores_proyecto
    # ==========================
    df_tmp = df_people_base.copy()
    df_tmp["cargo_norm"] = df_tmp["cargo"].apply(normalizar_txt)

    df_tmp = df_tmp[
        df_tmp["cargo_norm"].isin(cargos_visibles_norm)
    ].copy()

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
    # Personas disponibles para agregar
    # solo cargos_aplicables
    # ==========================
    df_people_perm = df_people_base.copy()
    df_people_perm["cargo_norm"] = df_people_perm["cargo"].apply(normalizar_txt)

    df_people_perm = df_people_perm[
        df_people_perm["cargo_norm"].isin(cargos_aplicables_norm)
    ].copy()

    df_people_perm = df_people_perm.drop(columns=["cargo_norm"])

    if df_people_perm.empty:
        st.warning("No hay colaboradores disponibles con cargos aplicables.")
        st.stop()

    # ==========================
    # Proyecto seleccionado
    # ==========================
    st.markdown("## Proyecto seleccionado")

    c1, c2, c3 = st.columns(3)
    c1.metric("Cliente", cliente_sel)
    c2.metric("Proyecto", proyecto_sel)
    c3.metric("Asignados", len(df_asignados))

    st.write("---")

    # ==========================
    # Agregar colaborador
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

        df_disponibles = df_disponibles.sort_values(
            by=["cargo", "nombre"],
            ascending=[True, True]
        )

        if df_disponibles.empty:
            st.success("Todos los colaboradores disponibles ya están asignados.")
        else:
            col_select, col_info, col_btn = st.columns(
                [2.2, 1.4, 0.9],
                vertical_alignment="bottom"
            )

            with col_select:
                colaborador_add_uuid = st.selectbox(
                    "Colaborador",
                    options=df_disponibles["uuid"].tolist(),
                    format_func=lambda uuid: formato_colaborador(
                        uuid,
                        df_disponibles
                    ),
                    key=f"gest_perm_add_colaborador_{cliente_sel}_{proyecto_sel}"
                )

            row_add = df_disponibles[
                df_disponibles["uuid"] == colaborador_add_uuid
            ].iloc[0]

            with col_info:
                st.caption(f"{row_add['cargo']} · {row_add['correo']}")

            with col_btn:
                if st.button(
                    "Agregar",
                    type="primary",
                    use_container_width=True,
                    key=f"gest_perm_btn_add_{cliente_sel}_{proyecto_sel}"
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
    # Colaboradores asignados
    # ==========================
    with st.container(border=True):
        st.markdown("### Colaboradores asignados")

        if df_asignados.empty:
            st.warning(
                f"No hay colaboradores asignados al proyecto {proyecto_sel}."
            )
        else:
            for _, row in df_asignados.iterrows():
                cargo_norm = normalizar_txt(row["cargo"])
                cargo_usuario_logueado = normalizar_txt(st.session_state.get("cargo", st.session_state.get("role", "")))
                es_gestor = (cargo_norm in cargos_gestores_norm or cargo_usuario_logueado in cargos_gestores_norm)
                es_actual = es_usuario_logueado(row)
                puede_quitar = not (es_actual and es_gestor)

                with st.container(border=True):
                    col_cargo, col_nombre, col_correo, col_btn = st.columns(
                        [1.5, 2.0, 2.0, 0.8],
                        vertical_alignment="center"
                    )

                    with col_cargo:
                        st.markdown(f"**{row['cargo']}**")

                    with col_nombre:
                        st.write(nombre_mostrar(row["nombre"]))

                    with col_correo:
                        st.caption(row["correo"])

                    with col_btn:
                        if puede_quitar:
                            if st.button(
                                "Quitar",
                                key=f"gest_perm_quitar_{row['uuid']}_{proyecto_sel}",
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
                        else:
                            st.caption("Usuario actual")