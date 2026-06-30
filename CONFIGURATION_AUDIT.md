# Auditoria de configuracion

## 1. Resumen

- Archivos del repositorio revisados: 18 (incluidos Python, Docker, YAML, archivos ocultos de configuracion e imagenes).
- Configuraciones hardcodeadas migradas o consolidadas: 24 ubicaciones.
- Archivos creados o modificados por la migracion: 14, incluido el `.env` local ignorado por Git.
- Variables centralizadas: 43.
- Credenciales heredadas eliminadas del codigo: 7 entradas del diccionario local, mas 7 cadenas de conexion repetidas.

## 2. Variables encontradas

| Variable encontrada | Archivo y linea original | Valor anterior | Nueva variable `.env` |
|---|---|---|---|
| Conexion GDA | `app.py:24`, `variables.py:8`, cuatro vistas | Credenciales PostgreSQL embebidas (redactadas) | `POSTGRES_*` + `GDA_DATABASE` |
| Conexion EQUIS V2 | `views/gestion_de_terrenos.py:32` | Credenciales PostgreSQL embebidas (redactadas) | `POSTGRES_*` + `EQUIS_V2_DATABASE` |
| Usuarios locales heredados | `variables.py:11-19` | Contraseñas y hashes embebidos (redactados) | Eliminados; la aplicacion usa Entra ID y la base de datos |
| Ruta NAS | `variables.py:1` | `/mnt/bd_historico` | `NAS_PATH` |
| Ruta de agrupados | `variables.py:5` | `/mnt/bd_historico/TECK/096/data` | `TECK_GROUPED_DATA_PATH` |
| Nombre de salida | `variables.py:3` | `CreacionMasivaFichas` | `TECK_OUTPUT_NAME` |
| URL Power BI | `views/cumplimiento_de_terreno.py:7` | URL publica embebida (redactada) | `POWERBI_URL` |
| Escala y alto Power BI | `views/cumplimiento_de_terreno.py:9-11` | `0.60`, `1680` | `POWERBI_SCALE`, `POWERBI_IFRAME_HEIGHT` |
| Teselas ArcGIS | `views/gestion_de_terrenos.py:1265` | URL de ArcGIS | `ARCGIS_WORLD_IMAGERY_URL` |
| TTL de cache | 14 decoradores Streamlit | `60`, `120`, `300` | `CACHE_TTL_SHORT`, `CACHE_TTL_MEDIUM`, `CACHE_TTL_LONG` |
| Imagen, contenedor, red, subred y reinicio | `Dockerfile`, `docker-compose.yml` | Valores Docker embebidos | Variables `DOCKER_*` y `PYTHON_IMAGE` |
| Puertos y direccion | `Dockerfile`, `docker-compose.yml` | `8501`, `8519`, `0.0.0.0` | `STREAMLIT_SERVER_*`, `APP_PORT` |
| URLs y tiempos de autenticacion | `auth.py` | Base Microsoft y 600/3600 segundos | `MICROSOFT_AUTHORITY_BASE_URL`, `AUTH_*` |

## 3. Archivos modificados

- `.env` (local, ignorado por Git)
- `.env.example`
- `CONFIGURATION_AUDIT.md`
- `config.py`
- `Dockerfile`
- `docker-compose.yml`
- `app.py`
- `auth.py`
- `variables.py`
- `views/administracion.py`
- `views/colaboradores_por_proyecto.py`
- `views/cumplimiento_de_terreno.py`
- `views/gestion_de_permisos.py`
- `views/gestion_de_terrenos.py`

## 4. Variables agregadas al `.env`

`APP_NAME`, `APP_BASE_URL`, `APP_PORT`, `APP_PAGE_ICON`, `APP_LOGO`,
`CACHE_TTL_SHORT`, `CACHE_TTL_MEDIUM`, `CACHE_TTL_LONG`,
`STREAMLIT_SERVER_ADDRESS`, `STREAMLIT_SERVER_PORT`, `POSTGRES_DRIVER`,
`POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`,
`GDA_DATABASE`, `EQUIS_V2_DATABASE`, `DATABASE_POOL_PRE_PING`,
`MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT_ID`,
`MICROSOFT_REDIRECT_URI`, `MICROSOFT_AUTHORITY_BASE_URL`, `ALLOWED_TENANT_ID`,
`ALLOWED_EMAIL_DOMAINS`, `AUTH_SESSION_MAX_AGE_SECONDS`,
`AUTH_STATE_MAX_AGE_SECONDS`, `NAS_PATH`, `TECK_GROUPED_DATA_PATH`,
`TECK_OUTPUT_NAME`, `POWERBI_URL`, `POWERBI_SCALE`, `POWERBI_IFRAME_HEIGHT`,
`ARCGIS_WORLD_IMAGERY_URL`, `PYTHON_IMAGE`, `APP_WORKDIR`,
`PYTHONDONTWRITEBYTECODE`, `PYTHONUNBUFFERED`, `DOCKER_IMAGE_NAME`,
`DOCKER_CONTAINER_NAME`, `DOCKER_NETWORK`, `DOCKER_SUBNET` y
`DOCKER_RESTART_POLICY`.

## 5. Variables eliminadas

Se eliminaron de `variables.py` `ruta_nas`, `output_teck`, `ruta_agrupados`,
`engine_string_prod` y `USERS_GDA`. Las rutas se trasladaron al entorno. El
diccionario de usuarios no tenia consumidores y duplicaba un mecanismo de
autenticacion inseguro, por lo que no se traslado al `.env`.

## 6. Variables duplicadas

Las siete conexiones PostgreSQL repetidas se consolidaron en `config.py`. GDA
y EQUIS V2 comparten driver, host, puerto y credenciales, y solo parametrizan
por separado el nombre de la base. Los TTL repetidos se consolidaron en tres
niveles. Los puertos de Docker y Streamlit usan una unica pareja de variables.

## 7. Configuraciones que no pudieron migrarse

- Los nombres de tablas, columnas y esquemas dentro de SQL son parte de las
  consultas y de la logica de negocio. Parametrizarlos alteraria las consultas,
  expresamente fuera del alcance indicado.
- Etiquetas, roles, iconos de navegacion y dimensiones CSS son contenido y
  comportamiento de interfaz, no configuracion de despliegue.
- `.env` conserva en local los valores encontrados para compatibilidad, salvo
  los valores Microsoft que no existian. `.env.example` deja vacios secretos,
  credenciales y la URL especifica de Power BI.

## 8. Recomendaciones

1. Rotar inmediatamente la contraseña PostgreSQL expuesta previamente en Git.
2. Completar las variables Microsoft Entra ID antes de iniciar la aplicacion.
3. Mantener `.env` fuera del control de versiones y usar un gestor de secretos
   en produccion.
4. Eliminar del historial de Git los secretos antiguos y dejar de versionar
   archivos `__pycache__/*.pyc`, que ya estan ignorados pero siguen rastreados.
5. Validar conectividad real con PostgreSQL, Entra ID y Power BI en el entorno
   de despliegue; esas integraciones externas no pueden probarse sin acceso.
