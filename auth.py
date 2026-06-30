"""Capa centralizada de autenticación Microsoft Entra ID para Streamlit."""
from __future__ import annotations

import html
import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

import msal
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

AUTH_SESSION_KEYS = (
    "authenticated", "email", "username", "display_name",
    "tenant_id", "roles", "login_time",
)


class AuthenticationError(Exception):
    """Error de configuración, protocolo o validación de identidad."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise AuthenticationError(f"Falta configurar la variable {name}.")
    return value


def _config() -> dict[str, Any]:
    tenant_id = _required_env("MICROSOFT_TENANT_ID")
    allowed_tenant = _required_env("ALLOWED_TENANT_ID")
    domains = {
        item.strip().lower().lstrip("@")
        for item in _required_env("ALLOWED_EMAIL_DOMAINS").split(",")
        if item.strip()
    }
    if not domains:
        raise AuthenticationError("ALLOWED_EMAIL_DOMAINS no contiene dominios válidos.")
    try:
        session_max_age = int(_required_env("AUTH_SESSION_MAX_AGE_SECONDS"))
        state_max_age = int(_required_env("AUTH_STATE_MAX_AGE_SECONDS"))
    except ValueError as exc:
        raise AuthenticationError("AUTH_SESSION_MAX_AGE_SECONDS debe ser un entero.") from exc
    if session_max_age <= 0:
        raise AuthenticationError("AUTH_SESSION_MAX_AGE_SECONDS debe ser mayor que cero.")
    if state_max_age <= 0:
        raise AuthenticationError("AUTH_STATE_MAX_AGE_SECONDS debe ser mayor que cero.")

    return {
        "client_id": _required_env("MICROSOFT_CLIENT_ID"),
        "client_secret": _required_env("MICROSOFT_CLIENT_SECRET"),
        "tenant_id": tenant_id,
        "allowed_tenant_id": allowed_tenant,
        "domains": domains,
        "redirect_uri": _required_env("MICROSOFT_REDIRECT_URI"),
        "app_base_url": _required_env("APP_BASE_URL").rstrip("/"),
        "authority": f"{_required_env('MICROSOFT_AUTHORITY_BASE_URL').rstrip('/')}/{tenant_id}",
        "issuer": f"{_required_env('MICROSOFT_AUTHORITY_BASE_URL').rstrip('/')}/{tenant_id}/v2.0",
        "session_max_age": session_max_age,
        "state_max_age": state_max_age,
    }


def _msal_app(config: dict[str, Any]) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=config["client_id"],
        client_credential=config["client_secret"],
        authority=config["authority"],
    )


def _redirect(url: str) -> None:
    """Emite únicamente la redirección; no construye una pantalla de acceso."""
    safe_url = html.escape(url, quote=True)
    st.markdown(
        f'<meta http-equiv="refresh" content="0;url={safe_url}">',
        unsafe_allow_html=True,
    )
    st.stop()


def _clear_oauth_query() -> None:
    for key in ("code", "state", "session_state", "error", "error_description"):
        if key in st.query_params:
            del st.query_params[key]


def clear_authentication() -> None:
    for key in AUTH_SESSION_KEYS:
        st.session_state.pop(key, None)


def _create_state(config: dict[str, Any]) -> str:
    payload = {
        "iat": int(time.time()),
        "nonce": secrets.token_urlsafe(24),
        "csrf": secrets.token_urlsafe(24),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(
        config["client_secret"].encode("utf-8"), encoded.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{encoded}.{signature}"


def _validate_state(state: str, config: dict[str, Any]) -> dict[str, Any]:
    try:
        encoded, signature = state.split(".", 1)
        expected = hmac.new(
            config["client_secret"].encode("utf-8"),
            encoded.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = encoded + "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded).decode("utf-8"))
        age = int(time.time()) - int(payload["iat"])
        if age < 0 or age > config["state_max_age"] or not payload.get("nonce"):
            raise ValueError
        return payload
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise AuthenticationError("La respuesta de autenticación no tiene un state válido.") from exc


def _email_from_claims(claims: dict[str, Any]) -> str:
    return str(
        claims.get("preferred_username")
        or claims.get("email")
        or claims.get("upn")
        or ""
    ).strip().lower()


def _validate_claims(claims: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    tenant_id = str(claims.get("tid", "")).strip()
    issuer = str(claims.get("iss", "")).rstrip("/")
    if tenant_id != config["tenant_id"] or tenant_id != config["allowed_tenant_id"]:
        raise AuthenticationError("La cuenta no pertenece al tenant autorizado.")
    if issuer != config["issuer"]:
        raise AuthenticationError("El emisor del token no es válido.")
    if claims.get("aud") != config["client_id"]:
        raise AuthenticationError("El token no fue emitido para esta aplicación.")
    if int(claims.get("exp", 0) or 0) <= int(time.time()):
        raise AuthenticationError("La autenticación de Microsoft ha expirado.")

    email = _email_from_claims(claims)
    if "@" not in email:
        raise AuthenticationError("Microsoft Entra ID no entregó un correo válido.")
    username, domain = email.rsplit("@", 1)
    if not username or domain not in config["domains"]:
        raise AuthenticationError("El dominio del correo no está autorizado.")

    roles = claims.get("roles", [])
    if isinstance(roles, str):
        roles = [roles]
    return {
        "authenticated": True,
        "email": email,
        "username": username,
        "display_name": str(claims.get("name") or username),
        "tenant_id": tenant_id,
        "roles": list(roles),
        "login_time": datetime.now(timezone.utc).isoformat(),
    }


def _session_is_current(config: dict[str, Any]) -> bool:
    if not st.session_state.get("authenticated", False):
        return False
    try:
        login_time = datetime.fromisoformat(st.session_state["login_time"])
        age = (datetime.now(timezone.utc) - login_time).total_seconds()
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= age < config["session_max_age"]


def _begin_login(config: dict[str, Any]) -> None:
    state = _create_state(config)
    payload = _validate_state(state, config)
    auth_uri = _msal_app(config).get_authorization_request_url(
        scopes=[],
        redirect_uri=config["redirect_uri"],
        state=state,
        nonce=payload["nonce"],
        response_mode="query",
    )
    if not auth_uri:
        raise AuthenticationError("No se pudo iniciar el flujo de Microsoft Entra ID.")
    _redirect(auth_uri)


def require_authentication() -> dict[str, Any]:
    """Bloquea toda la aplicación hasta completar y validar OIDC."""
    config = _config()
    if _session_is_current(config):
        return {key: st.session_state.get(key) for key in AUTH_SESSION_KEYS}
    if st.session_state.get("authenticated"):
        clear_authentication()

    oauth_error = st.query_params.get("error")
    if oauth_error:
        description = st.query_params.get("error_description", "Error devuelto por Microsoft.")
        clear_authentication()
        _clear_oauth_query()
        raise AuthenticationError(f"Microsoft Entra ID rechazó el acceso: {description}")

    if st.query_params.get("code"):
        state_payload = _validate_state(st.query_params.get("state", ""), config)
        try:
            result = _msal_app(config).acquire_token_by_authorization_code(
                code=st.query_params["code"],
                scopes=[],
                redirect_uri=config["redirect_uri"],
                nonce=state_payload["nonce"],
            )
        except ValueError as exc:
            _clear_oauth_query()
            raise AuthenticationError("Falló la validación CSRF/state de OAuth.") from exc

        _clear_oauth_query()
        if "error" in result:
            message = result.get("error_description") or result.get("error")
            raise AuthenticationError(f"No fue posible completar la autenticación: {message}")
        identity = _validate_claims(result.get("id_token_claims", {}), config)
        for key, value in identity.items():
            st.session_state[key] = value
        # Los tokens nunca se guardan en session_state ni se registran.
        st.rerun()

    _begin_login(config)
    raise AssertionError("unreachable")


def logout() -> None:
    config = _config()
    clear_authentication()
    query = urlencode({"post_logout_redirect_uri": config["app_base_url"]})
    _redirect(f"{config['authority']}/oauth2/v2.0/logout?{query}")
