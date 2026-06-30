"""Configuracion centralizada de la aplicacion, cargada exclusivamente desde .env."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy import URL

load_dotenv()


class ConfigurationError(RuntimeError):
    """Indica que falta una variable requerida o que su valor es invalido."""


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ConfigurationError(f"Falta configurar la variable {name}.")
    return value


def integer(name: str) -> int:
    value = required(name)
    try:
        return int(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} debe ser un entero.") from exc


def number(name: str) -> float:
    value = required(name)
    try:
        return float(value)
    except ValueError as exc:
        raise ConfigurationError(f"{name} debe ser numerico.") from exc


def boolean(name: str) -> bool:
    value = required(name).lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} debe ser un booleano.")


def database_url(database_env: str) -> URL:
    return URL.create(
        drivername=required("POSTGRES_DRIVER"),
        username=required("POSTGRES_USER"),
        password=required("POSTGRES_PASSWORD"),
        host=required("POSTGRES_HOST"),
        port=integer("POSTGRES_PORT"),
        database=required(database_env),
    )


GDA_DATABASE_URL = database_url("GDA_DATABASE")
EQUIS_V2_DATABASE_URL = database_url("EQUIS_V2_DATABASE")
APP_NAME = required("APP_NAME")
APP_PAGE_ICON = required("APP_PAGE_ICON")
APP_LOGO = required("APP_LOGO")
NAS_PATH = required("NAS_PATH")
TECK_GROUPED_DATA_PATH = required("TECK_GROUPED_DATA_PATH")
TECK_OUTPUT_NAME = required("TECK_OUTPUT_NAME")
POWERBI_URL = required("POWERBI_URL")
POWERBI_SCALE = number("POWERBI_SCALE")
POWERBI_IFRAME_HEIGHT = integer("POWERBI_IFRAME_HEIGHT")
ARCGIS_WORLD_IMAGERY_URL = required("ARCGIS_WORLD_IMAGERY_URL")
CACHE_TTL_SHORT = integer("CACHE_TTL_SHORT")
CACHE_TTL_MEDIUM = integer("CACHE_TTL_MEDIUM")
CACHE_TTL_LONG = integer("CACHE_TTL_LONG")
DATABASE_POOL_PRE_PING = boolean("DATABASE_POOL_PRE_PING")
