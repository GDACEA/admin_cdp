import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text
import folium
from streamlit_folium import st_folium
import variables as vars
from io import BytesIO
import io
from collections.abc import Iterable
import config

engine = create_engine(
    config.GDA_DATABASE_URL,
    pool_pre_ping=config.DATABASE_POOL_PRE_PING,
)

engine1 = create_engine(
    config.EQUIS_V2_DATABASE_URL,
    pool_pre_ping=config.DATABASE_POOL_PRE_PING,
)


# ==========================
# HELPERS
# ==========================
def normalizar_txt(x):
    if x is None:
        return ""
    return str(x).strip().upper()


def asegurar_dict(x):
    if x is None:
        return {}
    if isinstance(x, dict):
        return x
    return {}


def normalizar_colaboradores(valor):
    if valor is None:
        return []

    if isinstance(valor, str):
        if not valor.strip():
            return []
        valor = valor.strip()
        if valor.startswith("[") and valor.endswith("]"):
            valor = valor[1:-1]
        valor = valor.replace("'", "").replace('"', "")
        txt = valor.replace(";", "|").replace(",", "|")
        colaboradores = [v.strip() for v in txt.split("|") if v.strip()]
        return list(dict.fromkeys(colaboradores))

    if isinstance(valor, Iterable):
        colaboradores = [str(v).strip() for v in valor if str(v).strip()]
        return list(dict.fromkeys(colaboradores))

    if pd.isna(valor):
        return []

    colaborador = str(valor).strip()
    return [colaborador] if colaborador else []


def limpiar_texto(valor):
    if valor is None:
        return None

    if pd.isna(valor):
        return None

    texto = str(valor).strip()
    return texto if texto else None


def formatear_fecha_chile(valor):
    if pd.isna(valor):
        return ""

    texto = str(valor).strip()

    if texto.isdigit() and len(texto) >= 12:
        fecha = pd.to_datetime(valor, errors="coerce", unit="ms")
    elif texto.isdigit() and len(texto) == 10:
        fecha = pd.to_datetime(valor, errors="coerce", unit="s")
    else:
        fecha = pd.to_datetime(valor, errors="coerce", dayfirst=True)

    if pd.isna(fecha):
        return ""

    return fecha.strftime("%d/%m/%Y")


def parsear_fecha_chile(valor):
    if pd.isna(valor):
        return None

    if not str(valor).strip():
        return None

    texto = str(valor).strip()

    if texto.isdigit() and len(texto) >= 12:
        fecha = pd.to_datetime(valor, errors="coerce", unit="ms")
    elif texto.isdigit() and len(texto) == 10:
        fecha = pd.to_datetime(valor, errors="coerce", unit="s")
    else:
        fecha = pd.to_datetime(valor, errors="coerce", dayfirst=True)

    if pd.isna(fecha):
        return None

    return fecha.date()


# ==========================
# CARGA DE DATOS
# ==========================
@st.cache_data(ttl=config.CACHE_TTL_LONG)
def cargar_proyectos():
    query = """
    SELECT cliente, codigo_proyecto, estado
    FROM dbo.dt_projects
    WHERE estado = 'Activo'
    ORDER BY cliente, codigo_proyecto
    """
    return pd.read_sql(query, con=engine)


@st.cache_data(ttl=config.CACHE_TTL_LONG)
def cargar_metodologias_equis():
    query = """
    SELECT descripcion
    FROM rf.metodologias_equis
    WHERE descripcion IS NOT NULL
    ORDER BY descripcion
    """
    df = pd.read_sql(query, con=engine1)
    return df["descripcion"].dropna().unique().tolist()


@st.cache_data(ttl=config.CACHE_TTL_LONG)
def cargar_colaboradores():
    query = """
    SELECT nombre, cargo, correo
    FROM dbo.cdp_credentials
    WHERE nombre IS NOT NULL
      AND estado = 'Activo'
    ORDER BY nombre
    """
    df = pd.read_sql(query, con=engine)
    return df[
        df["cargo"].isin(vars.cargos_aplicables)
        & ~df["cargo"].isin(vars.cargos_gestores_proyecto)
    ].copy()


@st.cache_data(ttl=config.CACHE_TTL_SHORT)
def cargar_monitoreos_proyecto(cliente, proyecto):
    query = """
    SELECT
        m.cliente,
        m.codigo_proyecto,
        m.nombre_monitoreo,
        m.nombre_plantilla_collect,
        m.descripcion,
        m.objetivo_343,
        STRING_AGG(mp.metodologia, ' | ' ORDER BY mp.metodologia) AS metodologias,
        STRING_AGG(mp.resultado_343, ' | ' ORDER BY mp.metodologia) AS resultados_343
    FROM rf.monitoreos m
    LEFT JOIN rf.metodologias_por_monitoreo mp
        ON m.cliente = mp.cliente
       AND m.codigo_proyecto = mp.codigo_proyecto
       AND m.nombre_monitoreo = mp.nombre_monitoreo
    WHERE m.cliente = %(cliente)s
      AND m.codigo_proyecto = %(proyecto)s
    GROUP BY
        m.cliente,
        m.codigo_proyecto,
        m.nombre_monitoreo,
        m.nombre_plantilla_collect,
        m.descripcion,
        m.objetivo_343
    ORDER BY m.nombre_monitoreo
    """
    return pd.read_sql(
        query,
        con=engine1,
        params={"cliente": cliente, "proyecto": proyecto}
    )


@st.cache_data(ttl=config.CACHE_TTL_SHORT)
def cargar_nombres_monitoreos(cliente, proyecto):
    query = """
    SELECT nombre_monitoreo
    FROM rf.monitoreos
    WHERE cliente = %(cliente)s
      AND codigo_proyecto = %(proyecto)s
    ORDER BY nombre_monitoreo
    """
    df = pd.read_sql(
        query,
        con=engine1,
        params={"cliente": cliente, "proyecto": proyecto}
    )
    return df["nombre_monitoreo"].dropna().tolist()


@st.cache_data(ttl=config.CACHE_TTL_SHORT)
def cargar_campanas_monitoreo(cliente, proyecto, monitoreo):
    query = """
    SELECT
        c.cliente,
        c.codigo_proyecto,
        c.nombre_monitoreo,
        c.campana,
        c.fecha_inicio,
        c.fecha_fin,
        c.frecuencia,
        c.comentario_343,
        c.fecha_inicio_terreno,
        c.duracion_terreno_dias,
        STRING_AGG(cp.colaborador, ' | ' ORDER BY cp.colaborador) AS colaboradores
    FROM rf.campanas_por_monitoreo c
    LEFT JOIN rf.colaboradores_por_campana cp
        ON c.cliente = cp.cliente
       AND c.codigo_proyecto = cp.codigo_proyecto
       AND c.nombre_monitoreo = cp.nombre_monitoreo
       AND c.campana = cp.campana
    WHERE c.cliente = %(cliente)s
      AND c.codigo_proyecto = %(proyecto)s
      AND c.nombre_monitoreo = %(monitoreo)s
    GROUP BY
        c.cliente,
        c.codigo_proyecto,
        c.nombre_monitoreo,
        c.campana,
        c.fecha_inicio,
        c.fecha_fin,
        c.frecuencia,
        c.comentario_343,
        c.fecha_inicio_terreno,
        c.duracion_terreno_dias
    ORDER BY c.fecha_inicio, c.campana
    """
    return pd.read_sql(
        query,
        con=engine1,
        params={
            "cliente": cliente,
            "proyecto": proyecto,
            "monitoreo": monitoreo,
        }
    )


@st.cache_data(ttl=config.CACHE_TTL_SHORT)
def cargar_estaciones_monitoreo(cliente, proyecto, monitoreo):
    query = """
    SELECT
        metodologia,
        sector,
        estacion_muestreo,
        id_estacion,
        ejecuciones_por_campana,
        latitud_inicial,
        longitud_inicial,
        latitud_final,
        longitud_final,
        latitud_central,
        longitud_central,
        largo_m,
        ancho_m,
        intervalo_cm,
        dias_instalacion,
        duracion_s
    FROM rf.estaciones_por_monitoreo
    WHERE cliente = %(cliente)s
      AND codigo_proyecto = %(proyecto)s
      AND nombre_monitoreo = %(monitoreo)s
    ORDER BY metodologia, sector, estacion_muestreo, id_estacion
    """
    return pd.read_sql(
        query,
        con=engine1,
        params={
            "cliente": cliente,
            "proyecto": proyecto,
            "monitoreo": monitoreo,
        }
    )


# ==========================
# GUARDADO
# ==========================
def guardar_monitoreo(
    cliente,
    proyecto,
    nombre_monitoreo,
    nombre_plantilla_collect,
    descripcion,
    objetivo_343,
    df_metodologias,
    usuario
):
    insert_monitoreo = text("""
        INSERT INTO rf.monitoreos (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            nombre_plantilla_collect,
            descripcion,
            objetivo_343,
            creado_por
        )
        VALUES (
            :cliente,
            :codigo_proyecto,
            :nombre_monitoreo,
            :nombre_plantilla_collect,
            :descripcion,
            :objetivo_343,
            :creado_por
        )
        ON CONFLICT (cliente, codigo_proyecto, nombre_monitoreo)
        DO UPDATE SET
            nombre_plantilla_collect = EXCLUDED.nombre_plantilla_collect,
            descripcion = EXCLUDED.descripcion,
            objetivo_343 = EXCLUDED.objetivo_343
    """)

    delete_metodologias = text("""
        DELETE FROM rf.metodologias_por_monitoreo
        WHERE cliente = :cliente
          AND codigo_proyecto = :codigo_proyecto
          AND nombre_monitoreo = :nombre_monitoreo
    """)

    insert_metodologia = text("""
        INSERT INTO rf.metodologias_por_monitoreo (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            metodologia,
            resultado_343,
            creado_por
        )
        VALUES (
            :cliente,
            :codigo_proyecto,
            :nombre_monitoreo,
            :metodologia,
            :resultado_343,
            :creado_por
        )
    """)

    with engine1.begin() as conn:
        conn.execute(insert_monitoreo, {
            "cliente": cliente,
            "codigo_proyecto": proyecto,
            "nombre_monitoreo": nombre_monitoreo,
            "nombre_plantilla_collect": nombre_plantilla_collect,
            "descripcion": descripcion,
            "objetivo_343": objetivo_343,
            "creado_por": usuario,
        })

        conn.execute(delete_metodologias, {
            "cliente": cliente,
            "codigo_proyecto": proyecto,
            "nombre_monitoreo": nombre_monitoreo,
        })

        for _, row in df_metodologias.iterrows():
            conn.execute(insert_metodologia, {
                "cliente": cliente,
                "codigo_proyecto": proyecto,
                "nombre_monitoreo": nombre_monitoreo,
                "metodologia": row["metodologia"],
                "resultado_343": row["resultado_343"],
                "creado_por": usuario,
            })


def valor_tiene_contenido(valor):
    """Retorna True si una celda del editor tiene contenido real."""
    if isinstance(valor, list):
        return len([v for v in valor if limpiar_texto(v) is not None]) > 0
    if isinstance(valor, tuple) or isinstance(valor, set):
        return len([v for v in valor if limpiar_texto(v) is not None]) > 0
    return limpiar_texto(valor) is not None


def limpiar_nan(valor):
    """Convierte NaN/NaT/pd.NA a None sin romper listas."""
    if valor is None:
        return None
    if isinstance(valor, (list, tuple, set, dict)):
        return valor
    try:
        if pd.isna(valor):
            return None
    except Exception:
        pass
    return valor


def limpiar_entero(valor):
    valor = limpiar_nan(valor)
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))
    except Exception:
        return None


def guardar_campanas(cliente, proyecto, monitoreo, df_campanas, usuario):
    """Guarda campañas y colaboradores en una única transacción.

    Reemplaza los colaboradores de cada campaña guardada para que la tabla
    rf.colaboradores_por_campana quede exactamente igual a lo seleccionado
    en el editor.
    """

    insert_campana = text("""
        INSERT INTO rf.campanas_por_monitoreo (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            campana,
            fecha_inicio,
            fecha_fin,
            frecuencia,
            comentario_343,
            creado_por,
            fecha_inicio_terreno,
            duracion_terreno_dias
        )
        VALUES (
            :cliente,
            :codigo_proyecto,
            :nombre_monitoreo,
            :campana,
            :fecha_inicio,
            :fecha_fin,
            :frecuencia,
            :comentario_343,
            :creado_por,
            :fecha_inicio_terreno,
            :duracion_terreno_dias
        )
        ON CONFLICT (cliente, codigo_proyecto, nombre_monitoreo, campana)
        DO UPDATE SET
            fecha_inicio = EXCLUDED.fecha_inicio,
            fecha_fin = EXCLUDED.fecha_fin,
            frecuencia = EXCLUDED.frecuencia,
            comentario_343 = EXCLUDED.comentario_343,
            fecha_inicio_terreno = EXCLUDED.fecha_inicio_terreno,
            duracion_terreno_dias = EXCLUDED.duracion_terreno_dias
    """)

    delete_colaboradores = text("""
        DELETE FROM rf.colaboradores_por_campana
        WHERE cliente = :cliente
          AND codigo_proyecto = :codigo_proyecto
          AND nombre_monitoreo = :nombre_monitoreo
          AND campana = :campana
    """)

    insert_colaborador = text("""
        INSERT INTO rf.colaboradores_por_campana (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            campana,
            fecha_inicio,
            fecha_fin,
            colaborador,
            creado_por
        )
        VALUES (
            :cliente,
            :codigo_proyecto,
            :nombre_monitoreo,
            :campana,
            :fecha_inicio,
            :fecha_fin,
            :colaborador,
            :creado_por
        )
    """)

    campanas_guardadas = 0
    colaboradores_guardados = 0
    campanas_procesadas = []

    with engine1.begin() as conn:
        for _, row in df_campanas.iterrows():
            campana = limpiar_texto(row.get("Campaña"))
            fecha_inicio = parsear_fecha_chile(row.get("Fecha Inicio"))
            fecha_fin = parsear_fecha_chile(row.get("Fecha Fin"))

            if not campana or fecha_inicio is None or fecha_fin is None:
                continue

            if fecha_fin < fecha_inicio:
                raise ValueError(
                    f"La campaña '{campana}' tiene Fecha Fin anterior a Fecha Inicio."
                )

            colaboradores = [
                limpiar_texto(c)
                for c in normalizar_colaboradores(row.get("Colaboradores"))
            ]
            colaboradores = [c for c in colaboradores if c]
            colaboradores = list(dict.fromkeys(colaboradores))

            params_campana = {
                "cliente": cliente,
                "codigo_proyecto": proyecto,
                "nombre_monitoreo": monitoreo,
                "campana": campana,
                "fecha_inicio": fecha_inicio,
                "fecha_fin": fecha_fin,
                "frecuencia": limpiar_texto(row.get("Frecuencia")),
                "comentario_343": limpiar_texto(row.get("Comentario 343")),
                "creado_por": limpiar_texto(usuario),
                "fecha_inicio_terreno": parsear_fecha_chile(row.get("Fecha Inicio Terreno")),
                "duracion_terreno_dias": limpiar_entero(row.get("Duración Terreno (días)")),
            }

            conn.execute(insert_campana, params_campana)
            campanas_guardadas += 1
            campanas_procesadas.append(campana)

            conn.execute(delete_colaboradores, {
                "cliente": cliente,
                "codigo_proyecto": proyecto,
                "nombre_monitoreo": monitoreo,
                "campana": campana,
            })

            for colaborador in colaboradores:
                conn.execute(insert_colaborador, {
                    "cliente": cliente,
                    "codigo_proyecto": proyecto,
                    "nombre_monitoreo": monitoreo,
                    "campana": campana,
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "colaborador": colaborador,
                    "creado_por": limpiar_texto(usuario),
                })
                colaboradores_guardados += 1

    return {
        "campanas_guardadas": campanas_guardadas,
        "colaboradores_guardados": colaboradores_guardados,
        "campanas_procesadas": campanas_procesadas,
    }


def validar_df_campanas(df_campanas):
    """Valida el editor antes de guardar y retorna un DataFrame limpio."""
    df = df_campanas.copy().reindex(columns=COLUMNAS_CAMPANAS)

    df["Campaña"] = df["Campaña"].apply(limpiar_texto)
    df["Fecha Inicio Parsed"] = df["Fecha Inicio"].apply(parsear_fecha_chile)
    df["Fecha Fin Parsed"] = df["Fecha Fin"].apply(parsear_fecha_chile)
    df["Fecha Inicio Terreno Parsed"] = df["Fecha Inicio Terreno"].apply(parsear_fecha_chile)

    filas_con_algo = df[COLUMNAS_CAMPANAS].apply(
        lambda row: any(valor_tiene_contenido(v) for v in row),
        axis=1,
    )

    filas_validas = (
        df["Campaña"].notna()
        & df["Fecha Inicio Parsed"].notna()
        & df["Fecha Fin Parsed"].notna()
    )

    filas_incompletas = filas_con_algo & ~filas_validas
    if filas_incompletas.any():
        indices = (df.index[filas_incompletas] + 1).tolist()
        raise ValueError(
            "Hay campañas incompletas o con fechas inválidas en las filas "
            f"{indices}. Completa Campaña, Fecha Inicio y Fecha Fin en formato dd/mm/aaaa."
        )

    df_validado = df.loc[filas_validas].copy()

    if df_validado.empty:
        raise ValueError(
            "Debes ingresar al menos una campaña válida con nombre, fecha inicio y fecha fin."
        )

    fechas_invalidas = df_validado["Fecha Fin Parsed"] < df_validado["Fecha Inicio Parsed"]
    if fechas_invalidas.any():
        campanas = df_validado.loc[fechas_invalidas, "Campaña"].tolist()
        raise ValueError(
            "Estas campañas tienen Fecha Fin anterior a Fecha Inicio: "
            + ", ".join(campanas)
        )

    terreno_invalido = (
        df_validado["Fecha Inicio Terreno"].apply(valor_tiene_contenido)
        & df_validado["Fecha Inicio Terreno Parsed"].isna()
    )
    if terreno_invalido.any():
        indices = (df_validado.index[terreno_invalido] + 1).tolist()
        raise ValueError(
            "Hay fechas de inicio de terreno inválidas en las filas "
            f"{indices}. Usa formato dd/mm/aaaa."
        )

    duplicadas = df_validado["Campaña"].duplicated(keep=False)
    if duplicadas.any():
        campanas = sorted(df_validado.loc[duplicadas, "Campaña"].dropna().unique().tolist())
        raise ValueError(
            "Hay campañas duplicadas en la tabla: " + ", ".join(campanas)
        )

    df_validado["Colaboradores"] = df_validado["Colaboradores"].apply(normalizar_colaboradores)
    df_validado = df_validado.drop(
        columns=["Fecha Inicio Parsed", "Fecha Fin Parsed", "Fecha Inicio Terreno Parsed"]
    )
    return df_validado


def actualizar_comentarios_campanas(cliente, proyecto, monitoreo, df_campanas):
    def limpiar_comentario(valor):
        if pd.isna(valor):
            return None
        return str(valor).strip() if str(valor).strip() else None

    update_query = text("""
        UPDATE rf.campanas_por_monitoreo
        SET comentario_343 = :comentario_343
        WHERE cliente = :cliente
          AND codigo_proyecto = :codigo_proyecto
          AND nombre_monitoreo = :nombre_monitoreo
          AND campana = :campana
    """)

    with engine1.begin() as conn:
        for _, row in df_campanas.iterrows():
            conn.execute(update_query, {
                "cliente": cliente,
                "codigo_proyecto": proyecto,
                "nombre_monitoreo": monitoreo,
                "campana": row["Campaña"],
                "comentario_343": limpiar_comentario(row.get("Comentario 343")),
            })


def guardar_estaciones(cliente, proyecto, monitoreo, df_estaciones, usuario):
    insert_estacion = text("""
        INSERT INTO rf.estaciones_por_monitoreo (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            metodologia,
            sector,
            estacion_muestreo,
            id_estacion,
            ejecuciones_por_campana,
            latitud_inicial,
            longitud_inicial,
            latitud_final,
            longitud_final,
            latitud_central,
            longitud_central,
            largo_m,
            ancho_m,
            intervalo_cm,
            dias_instalacion,
            duracion_s,
            creado_por
        )
        VALUES (
            :cliente,
            :codigo_proyecto,
            :nombre_monitoreo,
            :metodologia,
            :sector,
            :estacion_muestreo,
            :id_estacion,
            :ejecuciones_por_campana,
            :latitud_inicial,
            :longitud_inicial,
            :latitud_final,
            :longitud_final,
            :latitud_central,
            :longitud_central,
            :largo_m,
            :ancho_m,
            :intervalo_cm,
            :dias_instalacion,
            :duracion_s,
            :creado_por
        )
        ON CONFLICT (
            cliente,
            codigo_proyecto,
            nombre_monitoreo,
            metodologia,
            sector,
            estacion_muestreo,
            id_estacion
        )
        DO UPDATE SET
            ejecuciones_por_campana = EXCLUDED.ejecuciones_por_campana,
            latitud_inicial = EXCLUDED.latitud_inicial,
            longitud_inicial = EXCLUDED.longitud_inicial,
            latitud_final = EXCLUDED.latitud_final,
            longitud_final = EXCLUDED.longitud_final,
            latitud_central = EXCLUDED.latitud_central,
            longitud_central = EXCLUDED.longitud_central,
            largo_m = EXCLUDED.largo_m,
            ancho_m = EXCLUDED.ancho_m,
            intervalo_cm = EXCLUDED.intervalo_cm,
            dias_instalacion = EXCLUDED.dias_instalacion,
            duracion_s = EXCLUDED.duracion_s
    """)

    def limpiar_nan(valor):
        if pd.isna(valor):
            return None
        return valor

    with engine1.begin() as conn:
        for _, row in df_estaciones.iterrows():
            conn.execute(insert_estacion, {
                "cliente": cliente,
                "codigo_proyecto": proyecto,
                "nombre_monitoreo": monitoreo,
                "metodologia": limpiar_nan(row.get("Metodología")),
                "sector": limpiar_nan(row.get("Sector")),
                "estacion_muestreo": limpiar_nan(row.get("Estación de muestreo")),
                "id_estacion": limpiar_nan(row.get("ID estación")),
                "ejecuciones_por_campana": limpiar_nan(row.get("Ejecuciones por campaña", 1)),
                "latitud_inicial": limpiar_nan(row.get("Latitud inicial")),
                "longitud_inicial": limpiar_nan(row.get("Longitud inicial")),
                "latitud_final": limpiar_nan(row.get("Latitud final")),
                "longitud_final": limpiar_nan(row.get("Longitud final")),
                "latitud_central": limpiar_nan(row.get("Latitud Central")),
                "longitud_central": limpiar_nan(row.get("Longitud Central")),
                "largo_m": limpiar_nan(row.get("Largo (m)")),
                "ancho_m": limpiar_nan(row.get("Ancho (m)")),
                "intervalo_cm": limpiar_nan(row.get("Intervalo (cm)")),
                "dias_instalacion": limpiar_nan(row.get("Días de instalación")),
                "duracion_s": limpiar_nan(row.get("Duración (s)")),
                "creado_por": usuario,
            })

COLUMNAS_CAMPANAS = [
    "Campaña",
    "Fecha Inicio",
    "Fecha Fin",
    "Fecha Inicio Terreno",
    "Duración Terreno (días)",
    "Frecuencia",
    "Comentario 343",
    "Colaboradores",
]

COLUMNAS_FECHA_CAMPANAS = [
    "Fecha Inicio",
    "Fecha Fin",
    "Fecha Inicio Terreno",
]

COLUMNAS_TEXTO_CAMPANAS = [
    "Campaña",
    "Frecuencia",
    "Comentario 343",
]


def preparar_df_campanas_editor(df, normalizador_colaboradores=None):
    """Prepara datos para st.data_editor sin convertir fechas a texto.

    Mantener las fechas como date/datetime permite que DateColumn maneje el
    estado interno sin rechazar entradas parciales ni forzar reruns incómodos.
    """
    df = df.reindex(columns=COLUMNAS_CAMPANAS).copy()

    for col in COLUMNAS_TEXTO_CAMPANAS:
        df[col] = df[col].astype("string").fillna("")

    for col in COLUMNAS_FECHA_CAMPANAS:
        df[col] = pd.to_datetime(
            df[col],
            errors="coerce",
            dayfirst=True,
        ).dt.date

    df["Duración Terreno (días)"] = pd.to_numeric(
        df["Duración Terreno (días)"],
        errors="coerce",
    )

    if normalizador_colaboradores is None:
        normalizador_colaboradores = normalizar_colaboradores

    df["Colaboradores"] = df["Colaboradores"].apply(normalizador_colaboradores)

    return df


COLUMN_CONFIG_CAMPANAS = {
    # IMPORTANTE:
    # Usar DateColumn evita que Streamlit valide texto mientras el usuario todavía
    # está digitando una fecha parcial. Ese era uno de los motivos por los que
    # el editor parecía "refrescarse" y perder el valor ingresado.
    "Fecha Inicio": st.column_config.DateColumn(
        "Inicio",
        format="DD/MM/YYYY",
        width="medium",
    ),
    "Fecha Fin": st.column_config.DateColumn(
        "Fin",
        format="DD/MM/YYYY",
        width="medium",
    ),
    "Fecha Inicio Terreno": st.column_config.DateColumn(
        "Inicio terreno",
        format="DD/MM/YYYY",
        width="medium",
    ),
    "Duración Terreno (días)": st.column_config.NumberColumn(
        "Días terreno",
        min_value=0,
        step=1,
        width="small",
    ),
    "Comentario 343": st.column_config.TextColumn(
        "Comentario 343",
        width="large",
    ),
    # En el popup se sobrescribe como MultiselectColumn.
    # En la tabla de visualización/comentarios queda como texto.
    "Colaboradores": st.column_config.TextColumn(
        "Colaboradores",
        width="large",
    ),
}

def generar_excel_ejemplo_campanas():
    df = pd.DataFrame(columns=COLUMNAS_CAMPANAS)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="campanas")

    buffer.seek(0)
    return buffer


def cargar_planilla_campanas():
    col1, col2 = st.columns([1, 2])

    with col1:
        st.download_button(
            "Descargar formato",
            data=generar_excel_ejemplo_campanas(),
            file_name="formato_campanas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

    with col2:
        archivo = st.file_uploader(
            "Cargar campañas desde Excel",
            type=["xlsx"],
            key="upload_campanas_excel",
        )

    if archivo is None:
        return None

    df = pd.read_excel(archivo)

    if list(df.columns) != COLUMNAS_CAMPANAS:
        st.error("La planilla no coincide con el formato esperado.")
        st.write("Columnas esperadas:", COLUMNAS_CAMPANAS)
        st.write("Columnas recibidas:", list(df.columns))
        return None

    st.success("Planilla cargada correctamente.")
    return df

# ==========================
# VIEW
# ==========================
def render():
    global cliente, proyecto, usuario

    # ==========================
    # PERMISOS
    # ==========================
    df_proy = cargar_proyectos()

    list_clientes = sorted(df_proy["cliente"].dropna().unique().tolist())

    usuario = st.session_state.get("user", "")
    cargo = normalizar_txt(st.session_state.get("cargo", ""))

    permisos_clientes = asegurar_dict(st.session_state.get("permits_json", {}))
    permisos_proyectos = asegurar_dict(st.session_state.get("permits_projects", {}))

    es_admin = usuario == "admin" or cargo == "ADMIN"

    if es_admin:
        clientes_permitidos = list_clientes
    else:
        clientes_permitidos = [
            c for c in list_clientes
            if permisos_clientes.get(c, 0) == 1
        ]

    if not clientes_permitidos:
        st.warning("No tienes clientes asignados.")
        st.stop()


    # ==========================
    # SIDEBAR
    # ==========================
    st.title("Gestión de Terrenos")

    with st.sidebar:
        st.subheader("Filtros")

        cliente = st.selectbox(
            "Cliente",
            clientes_permitidos,
            key="terrenos_cliente"
        )

        df_cliente = df_proy[df_proy["cliente"] == cliente].copy()

        proyectos_cliente = sorted(
            df_cliente["codigo_proyecto"].dropna().unique().tolist()
        )

        if not es_admin:
            proyectos_cliente = [
                p for p in proyectos_cliente
                if permisos_proyectos.get(p, 0) == 1
            ]

        if not proyectos_cliente:
            st.warning("No tienes proyectos asignados para este cliente.")
            st.stop()

        proyecto = st.selectbox(
            "Proyecto",
            proyectos_cliente,
            key="terrenos_proyecto"
        )


    # ==========================
    # CONTENIDO PRINCIPAL
    # ==========================
    st.subheader("Proyecto seleccionado")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Cliente", cliente)

    with col2:
        st.metric("Proyecto", proyecto)

    with col3:
        st.metric("Usuario", usuario)

    st.write("---")


    # ==========================
    # ESTADOS POPUPS
    # ==========================
    if "show_popup_crear_monitoreo" not in st.session_state:
        st.session_state["show_popup_crear_monitoreo"] = False

    if "show_popup_crear_campanas" not in st.session_state:
        st.session_state["show_popup_crear_campanas"] = False

    if "show_popup_crear_estaciones" not in st.session_state:
        st.session_state["show_popup_crear_estaciones"] = False


    # ==========================
    # MONITOREOS DEL PROYECTO
    # ==========================
    with st.container(border=True):
        col_titulo, col_boton = st.columns([4, 1])

        with col_titulo:
            st.subheader("Monitoreos del proyecto")

        with col_boton:
            if st.button("Crear monitoreo", use_container_width=True):
                st.session_state["show_popup_crear_monitoreo"] = True
                st.rerun()

        df_monitoreos = cargar_monitoreos_proyecto(cliente, proyecto)

        if df_monitoreos.empty:
            st.info("Este proyecto todavía no tiene monitoreos registrados.")
        else:
            df_display = df_monitoreos.copy()
            df_display["metodologias"] = df_display["metodologias"].fillna("")
            df_display["resultados_343"] = df_display["resultados_343"].fillna("")

            df_display = df_display.rename(columns={
                "nombre_monitoreo": "Monitoreo",
                "nombre_plantilla_collect": "Plantilla Collect",
                "objetivo_343": "Objetivo 343",
                "metodologias": "Metodologías",
                "resultados_343": "Resultados 343",
            })

            st.dataframe(
                df_display[
                    [
                        "Monitoreo",
                        "Plantilla Collect",
                        "Objetivo 343",
                        "Metodologías",
                        "Resultados 343",
                    ]
                ],
                use_container_width=True,
                hide_index=True
            )


    # ==========================
    # CAMPAÑAS DEL MONITOREO
    # ==========================
    st.write("---")

    with st.container(border=True):
        col_titulo, col_selector, col_boton = st.columns([2, 2, 1])

        with col_titulo:
            st.subheader("Campañas del monitoreo")

        monitoreos_disponibles = cargar_nombres_monitoreos(cliente, proyecto)

        with col_selector:
            if monitoreos_disponibles:
                monitoreo_sel = st.selectbox(
                    "Monitoreo",
                    monitoreos_disponibles,
                    key="campanas_monitoreo_sel"
                )
            else:
                monitoreo_sel = None
                st.info("Primero debes crear un monitoreo.")

        with col_boton:
            st.write("")
            if st.button(
                "Crear campañas",
                use_container_width=True,
                disabled=monitoreo_sel is None
            ):
                st.session_state["show_popup_crear_campanas"] = True
                st.rerun()

        if monitoreo_sel:
            df_campanas = cargar_campanas_monitoreo(
                cliente,
                proyecto,
                monitoreo_sel
            )

            if df_campanas.empty:
                st.info("Este monitoreo todavía no tiene campañas registradas.")
            else:
                df_display_campanas = df_campanas.copy()
                df_display_campanas["colaboradores"] = df_display_campanas["colaboradores"].fillna("")

                df_display_campanas = df_display_campanas.loc[
                    :,
                    [
                        "campana",
                        "fecha_inicio",
                        "fecha_fin",
                        "fecha_inicio_terreno",
                        "duracion_terreno_dias",
                        "frecuencia",
                        "comentario_343",
                        "colaboradores",
                    ],
                ].rename(columns={
                    "campana": "Campaña",
                    "fecha_inicio": "Fecha Inicio",
                    "fecha_fin": "Fecha Fin",
                    "frecuencia": "Frecuencia",
                    "comentario_343": "Comentario 343",
                    "colaboradores": "Colaboradores",
                    "fecha_inicio_terreno": "Fecha Inicio Terreno",
                    "duracion_terreno_dias": "Duración Terreno (días)",
                })

                for col_fecha in COLUMNAS_FECHA_CAMPANAS:
                    df_display_campanas[col_fecha] = pd.to_datetime(
                        df_display_campanas[col_fecha],
                        errors="coerce",
                        dayfirst=True,
                    ).dt.date

                df_display_campanas["Comentario 343"] = df_display_campanas[
                    "Comentario 343"
                ].fillna("")

                df_campanas_editado = st.data_editor(
                    df_display_campanas,
                    column_order=COLUMNAS_CAMPANAS,
                    column_config=COLUMN_CONFIG_CAMPANAS,
                    use_container_width=True,
                    hide_index=True,
                    disabled=[
                        col for col in COLUMNAS_CAMPANAS
                        if col != "Comentario 343"
                    ],
                    key=f"editor_comentarios_343_{cliente}_{proyecto}_{monitoreo_sel}",
                )

                if st.button(
                    "Guardar comentarios 343",
                    type="primary",
                    use_container_width=True,
                    key=f"guardar_comentarios_343_{cliente}_{proyecto}_{monitoreo_sel}",
                ):
                    actualizar_comentarios_campanas(
                        cliente=cliente,
                        proyecto=proyecto,
                        monitoreo=monitoreo_sel,
                        df_campanas=df_campanas_editado,
                    )
                    st.cache_data.clear()
                    st.success("Comentarios 343 actualizados correctamente.")
                    st.rerun()


    # ==========================
    # ESTACIONES DEL MONITOREO
    # ==========================
    st.write("---")

    TABLE_HEIGHT = 260
    MAP_HEIGHT = 360

    with st.container(border=True):
        col_titulo, col_selector, col_boton = st.columns([2, 2, 1])

        with col_titulo:
            st.subheader("Estaciones de muestreo")

        monitoreos_disponibles_est = cargar_nombres_monitoreos(cliente, proyecto)

        with col_selector:
            if monitoreos_disponibles_est:
                monitoreo_est_sel = st.selectbox(
                    "Monitoreo",
                    monitoreos_disponibles_est,
                    key="estaciones_monitoreo_sel"
                )
            else:
                monitoreo_est_sel = None
                st.info("Primero debes crear un monitoreo.")

        with col_boton:
            st.write("")
            if st.button(
                "Crear estaciones",
                use_container_width=True,
                disabled=monitoreo_est_sel is None
            ):
                st.session_state["show_popup_crear_estaciones"] = True
                st.rerun()

        if monitoreo_est_sel:
            df_estaciones = cargar_estaciones_monitoreo(
                cliente,
                proyecto,
                monitoreo_est_sel
            )

            if df_estaciones.empty:
                st.info("Este monitoreo todavía no tiene estaciones registradas.")
            else:
                df_display_est = df_estaciones.copy().rename(columns={
                    "metodologia": "Metodología",
                    "sector": "Sector",
                    "estacion_muestreo": "Estación de muestreo",
                    "id_estacion": "ID estación",
                    "ejecuciones_por_campana": "Ejecuciones por campaña",
                    "latitud_inicial": "Latitud inicial",
                    "longitud_inicial": "Longitud inicial",
                    "latitud_final": "Latitud final",
                    "longitud_final": "Longitud final",
                    "latitud_central": "Latitud Central",
                    "longitud_central": "Longitud Central",
                    "largo_m": "Largo (m)",
                    "ancho_m": "Ancho (m)",
                    "intervalo_cm": "Intervalo (cm)",
                    "dias_instalacion": "Días de instalación",
                    "duracion_s": "Duración (s)",
                })

                st.dataframe(
                    df_display_est,
                    use_container_width=True,
                    height=TABLE_HEIGHT,
                    hide_index=True
                )

                st.markdown("#### Mapa de estaciones")

                df_mapa = df_display_est.copy()
                df_mapa = df_mapa.dropna(
                    subset=[
                        "Latitud inicial",
                        "Longitud inicial",
                        "Latitud final",
                        "Longitud final",
                        "Latitud Central",
                        "Longitud Central",
                    ],
                    how="all"
                )

                if df_mapa.empty:
                    st.warning("Las estaciones no tienen coordenadas suficientes para desplegar el mapa.")
                else:
                    valid_center_lat = df_mapa["Latitud Central"].combine_first(
                        df_mapa["Latitud inicial"]
                    )
                    valid_center_lon = df_mapa["Longitud Central"].combine_first(
                        df_mapa["Longitud inicial"]
                    )

                    lat_centro = valid_center_lat.mean()
                    lon_centro = valid_center_lon.mean()

                    mapa = folium.Map(
                        location=[lat_centro, lon_centro],
                        zoom_start=13,
                        max_zoom=25,
                        tiles=None,
                        control_scale=True,
                        width="100%",
                        height=f"{MAP_HEIGHT}px",
                    )

                    folium.TileLayer(
                        tiles=config.ARCGIS_WORLD_IMAGERY_URL,
                        attr="Esri",
                        name="Esri Satellite",
                        overlay=False,
                        control=True
                    ).add_to(mapa)

                    bounds = []

                    for _, row in df_mapa.iterrows():
                        popup_html = f"""
                        <b>Sector:</b> {row.get("Sector", "")}<br>
                        <b>Estación:</b> {row.get("Estación de muestreo", "")}<br>
                        <b>ID estación:</b> {row.get("ID estación", "")}
                        """

                        lat_ini = row.get("Latitud inicial")
                        lon_ini = row.get("Longitud inicial")
                        lat_fin = row.get("Latitud final")
                        lon_fin = row.get("Longitud final")
                        lat_cent = row.get("Latitud Central")
                        lon_cent = row.get("Longitud Central")

                        if (
                            pd.notna(lat_ini)
                            and pd.notna(lon_ini)
                            and pd.notna(lat_fin)
                            and pd.notna(lon_fin)
                        ):
                            start = [lat_ini, lon_ini]
                            end = [lat_fin, lon_fin]
                            bounds.extend([start, end])

                            folium.PolyLine(
                                locations=[start, end],
                                color="#002fcb",
                                weight=4,
                                opacity=0.75,
                                dash_array="5, 8",
                                tooltip=row.get("Estación de muestreo", ""),
                                popup=folium.Popup(popup_html, max_width=300),
                            ).add_to(mapa)

                            for location in [start, end]:
                                folium.Marker(
                                    location=location,
                                    icon=folium.DivIcon(
                                        html=(
                                            '<div style="width:12px;height:12px;background:#002fcb;'
                                            'border-radius:2px;"></div>'
                                        ),
                                        icon_size=(12, 12),
                                        icon_anchor=(6, 6),
                                    ),
                                    tooltip=row.get("Estación de muestreo", ""),
                                ).add_to(mapa)

                        else:
                            location = None

                            if pd.notna(lat_cent) and pd.notna(lon_cent):
                                location = [lat_cent, lon_cent]
                            elif pd.notna(lat_ini) and pd.notna(lon_ini):
                                location = [lat_ini, lon_ini]
                            elif pd.notna(lat_fin) and pd.notna(lon_fin):
                                location = [lat_fin, lon_fin]

                            if location:
                                bounds.append(location)

                                folium.CircleMarker(
                                    location=location,
                                    radius=8,
                                    color="#002fcb",
                                    fill=True,
                                    fill_color="#002fcb",
                                    fill_opacity=1,
                                    weight=0,
                                    popup=folium.Popup(popup_html, max_width=300),
                                    tooltip=row.get("Estación de muestreo", ""),
                                ).add_to(mapa)

                                folium.CircleMarker(
                                    location=location,
                                    radius=5,
                                    color="#ffffff",
                                    fill=True,
                                    fill_color="#ffffff",
                                    fill_opacity=1,
                                    weight=0,
                                ).add_to(mapa)

                    if bounds:
                        mapa.fit_bounds(bounds, padding=(40, 40))

                    st_folium(
                        mapa,
                        use_container_width=True,
                        height=MAP_HEIGHT,
                        key="mapa_estaciones",
                        returned_objects=[],
                    )


    # ==========================
    # POPUP CREAR MONITOREO
    # ==========================
    @st.dialog("Crear monitoreo")
    def popup_crear_monitoreo():
        metodologias_disponibles = cargar_metodologias_equis()

        nombre_monitoreo = st.text_input("Nombre del monitoreo")
        nombre_plantilla_collect = st.text_input("Nombre de plantilla Collect")
        descripcion_monitoreo = st.text_area("Descripción del monitoreo")
        objetivo_343 = st.text_area("Objetivo 343 del monitoreo")

        st.write("### Metodologías asociadas")

        if "df_metodologias_monitoreo" not in st.session_state:
            st.session_state["df_metodologias_monitoreo"] = pd.DataFrame({
                "metodologia": [None],
                "resultado_343": [None],
            })

        df_editado = st.data_editor(
            st.session_state["df_metodologias_monitoreo"],
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "metodologia": st.column_config.SelectboxColumn(
                    "Metodología",
                    options=metodologias_disponibles,
                    required=True,
                ),
                "resultado_343": st.column_config.SelectboxColumn(
                    "Resultado 343",
                    options=[
                        "NA",
                        "Presencia/ausencia",
                        "Abundancia",
                        "Biomasa",
                        "Cobertura",
                    ],
                    required=True,
                ),
            },
            key="editor_metodologias_monitoreo"
        )

        col_guardar, col_cancelar = st.columns(2)

        with col_guardar:
            if st.button("Guardar", use_container_width=True, key="btn_guardar_monitoreo"):
                if not nombre_monitoreo:
                    st.error("Debe ingresar el nombre del monitoreo.")
                    st.stop()

                df_validado = df_editado.dropna(
                    subset=["metodologia", "resultado_343"]
                )

                if df_validado.empty:
                    st.error("Debe agregar al menos una metodología válida.")
                    st.stop()

                guardar_monitoreo(
                    cliente=cliente,
                    proyecto=proyecto,
                    nombre_monitoreo=nombre_monitoreo,
                    nombre_plantilla_collect=nombre_plantilla_collect,
                    descripcion=descripcion_monitoreo,
                    objetivo_343=objetivo_343,
                    df_metodologias=df_validado,
                    usuario=usuario,
                )

                st.session_state["show_popup_crear_monitoreo"] = False
                st.session_state.pop("df_metodologias_monitoreo", None)
                st.cache_data.clear()
                st.success("Monitoreo creado correctamente.")
                st.rerun()

        with col_cancelar:
            if st.button("Cancelar", use_container_width=True, key="btn_cancelar_monitoreo"):
                st.session_state["show_popup_crear_monitoreo"] = False
                st.session_state.pop("df_metodologias_monitoreo", None)
                st.rerun()


    # ==========================
    # POPUP CREAR CAMPAÑAS
    # ==========================
    @st.dialog("Crear campañas", width="large")
    def popup_crear_campanas():
        monitoreo_actual = st.session_state.get("campanas_monitoreo_sel")

        colaboradores_disponibles = (
            cargar_colaboradores()["nombre"]
            .dropna()
            .astype(str)
            .str.strip()
            .sort_values()
            .unique()
            .tolist()
        )

        colaboradores_por_nombre_normalizado = {
            normalizar_txt(colaborador): colaborador
            for colaborador in colaboradores_disponibles
        }

        def colaboradores_validos(valor):
            salida = []
            for colaborador in normalizar_colaboradores(valor):
                clave = normalizar_txt(colaborador)
                if clave in colaboradores_por_nombre_normalizado:
                    salida.append(colaboradores_por_nombre_normalizado[clave])
            return list(dict.fromkeys(salida))

        st.markdown("### Crear campañas")
        st.write(f"Monitoreo seleccionado: **{monitoreo_actual}**")

        contexto_editor = f"{cliente}__{proyecto}__{monitoreo_actual}"
        data_key = "df_campanas_editor_data"
        contexto_key = "df_campanas_editor_contexto"
        version_key = "df_campanas_editor_version"
        upload_key = "df_campanas_editor_upload_signature"

        # Importante: inicializar solo cuando cambia el contexto.
        # No reescribir el DataFrame en cada rerun, porque eso borra la última edición del usuario.
        if st.session_state.get(contexto_key) != contexto_editor:
            st.session_state[data_key] = preparar_df_campanas_editor(
                pd.DataFrame([{}]),
                normalizador_colaboradores=colaboradores_validos,
            )
            st.session_state[contexto_key] = contexto_editor
            st.session_state[version_key] = 0
            st.session_state.pop(upload_key, None)

        col_descarga, col_carga = st.columns([1, 2])

        with col_descarga:
            st.download_button(
                label="Descargar formato",
                data=generar_excel_ejemplo_campanas(),
                file_name="formato_campanas.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key=f"download_formato_campanas_{contexto_editor}",
            )

        with col_carga:
            archivo_campanas = st.file_uploader(
                "Cargar campañas desde Excel",
                type=["xlsx"],
                key=f"upload_campanas_excel_{contexto_editor}",
            )

        if archivo_campanas is not None:
            signature = (
                archivo_campanas.name,
                getattr(archivo_campanas, "size", None),
                contexto_editor,
            )

            # Procesar cada archivo solo una vez. Si no, cada rerun pisa las ediciones manuales.
            if st.session_state.get(upload_key) != signature:
                try:
                    df_excel = pd.read_excel(archivo_campanas)
                    df_excel.columns = [str(c).strip() for c in df_excel.columns]

                    if list(df_excel.columns) != COLUMNAS_CAMPANAS:
                        st.error("La planilla cargada no coincide con el formato esperado.")
                        st.write("Columnas esperadas:", COLUMNAS_CAMPANAS)
                        st.write("Columnas recibidas:", list(df_excel.columns))
                    else:
                        st.session_state[data_key] = preparar_df_campanas_editor(
                            df_excel,
                            normalizador_colaboradores=colaboradores_validos,
                        )
                        st.session_state[upload_key] = signature
                        st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
                        st.success("Planilla cargada correctamente.")
                        st.rerun()

                except Exception as e:
                    st.error(f"No se pudo leer la planilla: {e}")

        st.markdown("""
        <style>
        div[data-testid="stDialog"] div[role="dialog"] {
            width: 95vw;
            max-width: 95vw;
        }

        [data-testid="stDataEditor"] {
            min-height: 360px;
        }
        </style>
        """, unsafe_allow_html=True)

        column_config_editor_campanas = {
            "Campaña": st.column_config.TextColumn(
                "Campaña",
                required=True,
                width=120,
            ),

            "Fecha Inicio": st.column_config.DateColumn(
                "Inicio",
                format="DD/MM/YYYY",
                width=100,
            ),

            "Fecha Fin": st.column_config.DateColumn(
                "Fin",
                format="DD/MM/YYYY",
                width=100,
            ),

            "Fecha Inicio Terreno": st.column_config.DateColumn(
                "Inicio terreno",
                format="DD/MM/YYYY",
                width=120,
            ),

            "Duración Terreno (días)": st.column_config.NumberColumn(
                "Días",
                min_value=0,
                step=1,
                width=70,
            ),

            "Frecuencia": st.column_config.SelectboxColumn(
                "Frecuencia",
                options=[
                    "Única",
                    "Diaria",
                    "Semanal",
                    "Mensual",
                    "Trimestral",
                    "Semestral",
                    "Anual",
                    "Estacional",
                    "Particular",
                ],
                width=110,
            ),

            "Comentario 343": st.column_config.TextColumn(
                "Comentario",
                width=180,
            ),

            "Colaboradores": st.column_config.MultiselectColumn(
                "Colaboradores",
                options=colaboradores_disponibles,
                help="Solo muestra colaboradores activos con cargos operativos.",
                width=220,
            ),
        }

        editor_key = (
            f"editor_campanas_{contexto_editor}_"
            f"v{st.session_state.get(version_key, 0)}"
        )

        df_campanas_editado = st.data_editor(
            st.session_state[data_key],
            num_rows="dynamic",
            use_container_width=True,
            height=380,
            column_order=COLUMNAS_CAMPANAS,
            column_config=column_config_editor_campanas,
            hide_index=True,
            key=editor_key,
        )

        # NO guardar df_campanas_editado de vuelta en st.session_state en cada rerun.
        # El data_editor ya mantiene sus cambios usando su key. Sobrescribir la
        # fuente del widget inmediatamente después de renderizarlo puede pisar
        # la edición activa y provocar el efecto de "se borra lo que acabo de escribir".
        # Usamos df_campanas_editado solo cuando el usuario presiona Guardar.

        col_guardar, col_cancelar = st.columns(2)

        with col_guardar:
            guardar = st.button(
                "Guardar campañas",
                use_container_width=True,
                key=f"btn_guardar_campanas_{contexto_editor}",
            )

        with col_cancelar:
            cancelar = st.button(
                "Cancelar",
                use_container_width=True,
                key=f"btn_cancelar_campanas_{contexto_editor}",
            )

        if cancelar:
            st.session_state["show_popup_crear_campanas"] = False
            st.session_state.pop(data_key, None)
            st.session_state.pop(contexto_key, None)
            st.session_state.pop(version_key, None)
            st.session_state.pop(upload_key, None)
            st.rerun()

        if guardar:
            if monitoreo_actual is None:
                st.error("Debe seleccionar un monitoreo.")
                st.stop()

            try:
                df_para_guardar = df_campanas_editado.copy()
                df_para_guardar["Colaboradores"] = df_para_guardar["Colaboradores"].apply(
                    colaboradores_validos
                )

                df_validado = validar_df_campanas(df_para_guardar)

                total_colaboradores_seleccionados = sum(
                    len(normalizar_colaboradores(valor))
                    for valor in df_validado["Colaboradores"]
                )

                resultado = guardar_campanas(
                    cliente=cliente,
                    proyecto=proyecto,
                    monitoreo=monitoreo_actual,
                    df_campanas=df_validado,
                    usuario=usuario,
                )

                if total_colaboradores_seleccionados > 0 and resultado["colaboradores_guardados"] == 0:
                    st.warning(
                        "Se seleccionaron colaboradores, pero no se insertó ninguno. "
                        "Revisa si la tabla rf.colaboradores_por_campana tiene restricciones, "
                        "triggers o columnas obligatorias adicionales."
                    )

            except Exception as e:
                st.error(str(e))
                st.stop()

            st.session_state["show_popup_crear_campanas"] = False
            st.session_state.pop(data_key, None)
            st.session_state.pop(contexto_key, None)
            st.session_state.pop(version_key, None)
            st.session_state.pop(upload_key, None)
            st.cache_data.clear()
            st.success(
                "Campañas guardadas correctamente. "
                f"Campañas: {resultado['campanas_guardadas']}. "
                f"Colaboradores guardados: {resultado['colaboradores_guardados']}."
            )
            st.rerun()


    # ==========================
    # POPUP CREAR ESTACIONES
    # ==========================
    @st.dialog("Crear estaciones de muestreo", width="large")
    def popup_crear_estaciones():
        metodologias_disponibles = cargar_metodologias_equis()
        monitoreo_actual = st.session_state.get("estaciones_monitoreo_sel")

        columnas_estaciones = [
            "Metodología",
            "Sector",
            "Estación de muestreo",
            "ID estación",
            "Ejecuciones por campaña",
            "Latitud inicial",
            "Longitud inicial",
            "Latitud final",
            "Longitud final",
            "Latitud Central",
            "Longitud Central",
            "Largo (m)",
            "Ancho (m)",
            "Intervalo (cm)",
            "Días de instalación",
            "Duración (s)",
        ]

        st.write(f"Monitoreo seleccionado: **{monitoreo_actual}**")

        if "df_estaciones_editor" not in st.session_state:
            st.session_state["df_estaciones_editor"] = pd.DataFrame({
                "Metodología": [None],
                "Sector": [None],
                "Estación de muestreo": [None],
                "ID estación": [None],
                "Ejecuciones por campaña": [1],
                "Latitud inicial": [None],
                "Longitud inicial": [None],
                "Latitud final": [None],
                "Longitud final": [None],
                "Latitud Central": [None],
                "Longitud Central": [None],
                "Largo (m)": [None],
                "Ancho (m)": [None],
                "Intervalo (cm)": [None],
                "Días de instalación": [None],
                "Duración (s)": [None],
            })

        # ==========================
        # DESCARGAR / CARGAR FORMATO
        # ==========================
        col_descarga, col_carga = st.columns([1, 2])

        with col_descarga:
            buffer = BytesIO()
            st.session_state["df_estaciones_editor"].to_excel(
                buffer,
                index=False,
                sheet_name="estaciones"
            )
            buffer.seek(0)

            st.download_button(
                label="Descargar formato",
                data=buffer,
                file_name="formato_estaciones_muestreo.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

        with col_carga:
            archivo_cargado = st.file_uploader(
                "Cargar tabla",
                type=["xlsx"],
                key="uploader_estaciones"
            )

            if archivo_cargado is not None:
                try:
                    df_cargado = pd.read_excel(archivo_cargado)

                    columnas_cargadas = list(df_cargado.columns)

                    if columnas_cargadas != columnas_estaciones:
                        st.error(
                            "La tabla cargada no coincide con el formato esperado. "
                            "Descarga el formato y vuelve a cargarlo sin cambiar los nombres ni el orden de columnas."
                        )
                    else:
                        st.session_state["df_estaciones_editor"] = df_cargado
                        st.success("Tabla cargada correctamente.")
                        st.rerun()

                except Exception as e:
                    st.error(f"No se pudo leer el archivo cargado: {e}")

        st.markdown("""
            <style>
            div[data-testid="stDialog"] div[role="dialog"] {
                width: 95vw;
                max-width: 95vw;
            }
            [data-testid="stDataEditor"] {
                min-height: 420px;
            }
            </style>
            """, unsafe_allow_html=True)

        column_config={
                        "Metodología": st.column_config.SelectboxColumn(
                            "Metod.",
                            options=metodologias_disponibles,
                            required=True,
                            width=130,
                        ),
                        "Sector": st.column_config.TextColumn(
                            "Sector",
                            width=90,
                        ),
                        "Estación de muestreo": st.column_config.TextColumn(
                            "Estación",
                            required=True,
                            width=130,
                        ),
                        "ID estación": st.column_config.TextColumn(
                            "ID",
                            required=True,
                            width=90,
                        ),
                        "Ejecuciones por campaña": st.column_config.NumberColumn(
                            "Ejec.",
                            min_value=1,
                            step=1,
                            default=1,
                            width=75,
                        ),
                        "Latitud inicial": st.column_config.NumberColumn(
                            "Lat. ini",
                            format="%.6f",
                            width=90,
                        ),
                        "Longitud inicial": st.column_config.NumberColumn(
                            "Lon. ini",
                            format="%.6f",
                            width=90,
                        ),
                        "Latitud final": st.column_config.NumberColumn(
                            "Lat. fin",
                            format="%.6f",
                            width=90,
                        ),
                        "Longitud final": st.column_config.NumberColumn(
                            "Lon. fin",
                            format="%.6f",
                            width=90,
                        ),
                        "Latitud Central": st.column_config.NumberColumn(
                            "Lat. centro",
                            format="%.6f",
                            width=95,
                        ),
                        "Longitud Central": st.column_config.NumberColumn(
                            "Lon. centro",
                            format="%.6f",
                            width=95,
                        ),
                        "Largo (m)": st.column_config.NumberColumn(
                            "Largo",
                            min_value=0.0,
                            width=75,
                        ),
                        "Ancho (m)": st.column_config.NumberColumn(
                            "Ancho",
                            min_value=0.0,
                            width=75,
                        ),
                        "Intervalo (cm)": st.column_config.NumberColumn(
                            "Interv.",
                            min_value=0.0,
                            width=80,
                        ),
                        "Días de instalación": st.column_config.NumberColumn(
                            "Días",
                            min_value=0,
                            step=1,
                            width=75,
                        ),
                        "Duración (s)": st.column_config.NumberColumn(
                            "Dur.",
                            min_value=0.0,
                            width=75,
                        ),
                    }

        df_editado = st.data_editor(
                                    st.session_state["df_estaciones_editor"],
                                    num_rows="dynamic",
                                    use_container_width=True,
                                    height=420,
                                    column_config=column_config,
                                    key="editor_estaciones"
                                )

        col_guardar, col_cancelar = st.columns(2)

        with col_guardar:
            if st.button("Guardar estaciones", use_container_width=True, key="btn_guardar_estaciones"):
                if monitoreo_actual is None:
                    st.error("Debe seleccionar un monitoreo.")
                    st.stop()

                df_validado = df_editado.dropna(
                    subset=[
                        "Metodología",
                        "Estación de muestreo",
                        "ID estación",
                    ]
                )

                if df_validado.empty:
                    st.error("Debe agregar al menos una estación válida.")
                    st.stop()

                guardar_estaciones(
                    cliente=cliente,
                    proyecto=proyecto,
                    monitoreo=monitoreo_actual,
                    df_estaciones=df_validado,
                    usuario=usuario,
                )

                st.session_state["show_popup_crear_estaciones"] = False
                st.session_state.pop("df_estaciones_editor", None)
                st.cache_data.clear()
                st.success("Estaciones creadas correctamente.")
                st.rerun()

        with col_cancelar:
            if st.button("Cancelar", use_container_width=True, key="btn_cancelar_estaciones"):
                st.session_state["show_popup_crear_estaciones"] = False
                st.session_state.pop("df_estaciones_editor", None)
                st.rerun()


    # ==========================
    # EJECUCIÓN POPUPS
    # ==========================
    if st.session_state["show_popup_crear_monitoreo"]:
        popup_crear_monitoreo()

    if st.session_state["show_popup_crear_campanas"]:
        popup_crear_campanas()

    if st.session_state["show_popup_crear_estaciones"]:
        popup_crear_estaciones()
