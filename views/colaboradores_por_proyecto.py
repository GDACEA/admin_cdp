import streamlit as st
import pandas as pd
import variables as vars
import uuid
import time

from sqlalchemy import create_engine, text
from datetime import datetime, date


# ==========================
# DB
# ==========================
engine = create_engine(
    "postgresql://gda_prod:Cea2025.!@172.20.4.17:5432/GDA"
)


# ==========================
# HELPERS
# ==========================
def es_formato_yyyy_mm_dd(texto: str) -> bool:
    try:
        datetime.strptime(texto, "%Y-%m-%d")
        return True
    except ValueError:
        return False


@st.cache_data(ttl=300)
def cargar_proyectos_colaboradores():
    query_proy = """
    SELECT *
    FROM dbo.dt_projects
    """
    return pd.read_sql(query_proy, con=engine)


@st.cache_data(ttl=120)
def cargar_colaboradores_por_proyecto(proyecto):
    query = text("""
    SELECT nombre, cargo, correo, permisos
    FROM dbo.cdp_credentials
    WHERE jsonb_extract_path_text(permisos, :proyecto)::int = 1
    """)

    df = pd.read_sql(query, engine, params={"proyecto": proyecto})
    df = df[df["nombre"] != "admin"]

    return df


def crear_proyecto_en_bd(
    add_uuid,
    add_nombre,
    add_codigo,
    add_gerente,
    add_correo,
    fecha_inicio,
    fecha_termino,
    add_tipo,
    add_cliente,
    add_uen,
    add_estado,
):
    insert_query = text("""
        INSERT INTO dbo.dt_projects (
            uuid,
            nombre_proyecto,
            codigo_proyecto,
            gerente_de_proyecto,
            email_gerente_de_proyecto,
            fecha_inicio,
            fecha_fin,
            tipo_de_proyecto,
            cliente,
            uen,
            estado
        )
        VALUES (
            :uuid,
            :nombre_proyecto,
            :codigo_proyecto,
            :gerente_de_proyecto,
            :email_gerente_de_proyecto,
            :fecha_inicio,
            :fecha_fin,
            :tipo_de_proyecto,
            :cliente,
            :uen,
            :estado
        )
    """)

    update_project_permissions = text("""
        UPDATE dbo.cdp_credentials
        SET permisos = COALESCE(permisos, '{}'::jsonb) ||
            jsonb_build_object(
                :codigo_proyecto,
                CASE WHEN nombre = 'admin' THEN 1 ELSE 0 END
            )
    """)

    update_client_permissions = text("""
        UPDATE dbo.cdp_credentials
        SET permisos_clientes =
            COALESCE(permisos_clientes, '{}'::jsonb) ||
            jsonb_build_object(
                LEFT(:codigo_proyecto, 3),
                GREATEST(
                    COALESCE(
                        (permisos_clientes ->> LEFT(:codigo_proyecto, 3))::int,
                        0
                    ),
                    CASE WHEN nombre = 'admin' THEN 1 ELSE 0 END
                )
            )
    """)

    with engine.begin() as conn:
        conn.execute(
            insert_query,
            {
                "uuid": add_uuid,
                "nombre_proyecto": add_nombre,
                "codigo_proyecto": add_codigo,
                "gerente_de_proyecto": add_gerente,
                "email_gerente_de_proyecto": add_correo,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_termino,
                "tipo_de_proyecto": add_tipo,
                "cliente": add_cliente,
                "uen": add_uen,
                "estado": add_estado,
            },
        )

        conn.execute(
            update_project_permissions,
            {"codigo_proyecto": add_codigo},
        )

        conn.execute(
            update_client_permissions,
            {"codigo_proyecto": add_codigo},
        )


# ==========================
# VIEW
# ==========================
def render():

    # ==========================
    # SESSION STATE
    # ==========================
    if "add_project_mode" not in st.session_state:
        st.session_state.add_project_mode = False

    # ==========================
    # DATA
    # ==========================
    df_proy = cargar_proyectos_colaboradores()

    df_activos = df_proy[df_proy["estado"] == "Activo"].copy()

    list_proyectos = sorted(
        df_proy["codigo_proyecto"].dropna().unique().tolist()
    )

    list_clientes = sorted(
        df_proy["cliente"].dropna().unique().tolist()
    )

    permisos_clientes = st.session_state.get("permits_json", {})

    if not isinstance(permisos_clientes, dict):
        permisos_clientes = {}

    if st.session_state.get("admin", False):
        clientes_permitidos = list_clientes
    else:
        clientes_permitidos = [
            c for c in list_clientes
            if permisos_clientes.get(c) == 1
        ]

    # ==========================
    # UI
    # ==========================
    st.title("Gestión de Permisos - Colaboradores por Proyecto")

    # ==========================
    # SIDEBAR FILTERS
    # ==========================
    with st.sidebar:
        st.write("---")
        st.subheader("Filtros de proyecto")

        cliente = st.selectbox(
            "Listado de Clientes",
            ["(Todos)"] + clientes_permitidos,
            key="colab_proyecto_cliente",
        )

        if cliente == "(Todos)":
            proyectos_filtrados = sorted(list_proyectos)

            if not st.session_state.get("admin", False):
                proyectos_filtrados = [
                    p for p in proyectos_filtrados
                    if any(
                        p.startswith(c)
                        for c in clientes_permitidos
                    )
                ]

        else:
            proyectos_filtrados = [
                p for p in list_proyectos
                if cliente in p
            ]

        proyecto = st.selectbox(
            "Listado de Proyectos",
            ["Ninguno"] + proyectos_filtrados,
            key="colab_proyecto_proyecto",
        )

        st.write("---")

        add_proyect = st.button(
            "Agregar Proyecto",
            key="colab_proyecto_agregar_proyecto",
        )

    # ==========================
    # MAIN PAGE
    # ==========================
    if proyecto == "Ninguno":
        if not st.session_state.add_project_mode:
            st.info("Por favor seleccione un proyecto")

    else:
        st.subheader(f"Colaboradores de Proyecto {proyecto}")

        df = cargar_colaboradores_por_proyecto(proyecto)

        if df.empty:
            st.info("No hay colaboradores asignados a este proyecto.")
        else:
            st.dataframe(
                df[["nombre", "cargo", "correo"]].sort_values(
                    by="nombre"
                ),
                use_container_width=True,
                hide_index=True,
            )

            st.write("---")

    if add_proyect:
        st.session_state.add_project_mode = True
        st.rerun()

    # ==========================
    # ADD PROJECT FORM
    # ==========================
    if st.session_state.add_project_mode:

        st.write("---")
        st.subheader("Agregar nuevo proyecto")

        add_uuid = uuid.uuid4()

        add_nombre = st.text_input(
            "Nombre del proyecto (Máx. 255 caracteres)",
            key="add_project_nombre",
        )

        add_codigo = st.text_input(
            "Código del Proyecto",
            key="add_project_codigo",
        )

        add_gerente = st.text_input(
            "Gerente a cargo",
            key="add_project_gerente",
        )

        add_correo = st.text_input(
            "Correo de Gerente a cargo",
            key="add_project_correo",
        )

        fecha_inicio = st.date_input(
            "Fecha de inicio (dd/mm/aaaa)",
            format="DD/MM/YYYY",
            value=date(2020, 1, 1),
            key="add_project_fecha_inicio",
        )

        fecha_termino = st.date_input(
            "Fecha de Término (dd/mm/aaaa)",
            format="DD/MM/YYYY",
            min_value=fecha_inicio,
            key="add_project_fecha_termino",
        )

        add_tipo = st.selectbox(
            "Señale el tipo de proyecto",
            ["", "Monitoreo / línea base", "Estudio", "Faena"],
            key="add_project_tipo",
        )

        add_cliente = st.text_input(
            "Cliente",
            key="add_project_cliente",
        )

        add_uen = st.selectbox(
            "Señale la unidad encargada",
            ["", "Cumplimiento", "Desarrollo", "Consultoría"],
            key="add_project_uen",
        )

        add_estado = "Activo"

        campos_faltantes = []

        if not add_nombre:
            campos_faltantes.append("nombre del proyecto")

        if not add_codigo:
            campos_faltantes.append("código del proyecto")

        if not add_gerente:
            campos_faltantes.append("gerente")

        if not add_correo:
            campos_faltantes.append("correo gerente")

        if not fecha_inicio:
            campos_faltantes.append("fecha inicio")

        if not fecha_termino:
            campos_faltantes.append("fecha término")

        if add_tipo == "":
            campos_faltantes.append("tipo de proyecto")

        if not add_cliente:
            campos_faltantes.append("cliente")

        if add_uen == "":
            campos_faltantes.append("unidad encargada")

        if campos_faltantes:
            st.warning(
                "Campos pendientes: "
                + ", ".join(campos_faltantes)
            )

        st.write("---")

        col1, col2, col3 = st.columns([1, 2, 1])

        with col1:
            if st.button(
                "Cancelar",
                key="add_project_cancelar",
            ):
                st.session_state.add_project_mode = False
                st.rerun()

        with col2:
            if st.button(
                "Confirmar creación",
                key="add_project_confirmar",
            ):

                if campos_faltantes:
                    st.error("Complete todos los campos por favor.")
                    return

                crear_proyecto_en_bd(
                    add_uuid=add_uuid,
                    add_nombre=add_nombre,
                    add_codigo=add_codigo,
                    add_gerente=add_gerente,
                    add_correo=add_correo,
                    fecha_inicio=fecha_inicio,
                    fecha_termino=fecha_termino,
                    add_tipo=add_tipo,
                    add_cliente=add_cliente,
                    add_uen=add_uen,
                    add_estado=add_estado,
                )

                st.cache_data.clear()
                st.success("Proyecto agregado exitosamente")

                time.sleep(1.0)

                st.session_state.add_project_mode = False
                st.rerun()
