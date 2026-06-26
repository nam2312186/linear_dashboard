from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import streamlit as st


AUTH_PROVIDER = "logto"
LOGO_PATH = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
REQUIRED_AUTH_KEYS = {
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
}


def _post_logout_redirect_uri(redirect_uri: str) -> str:
    parsed = urlsplit(redirect_uri)
    path = parsed.path
    if path.endswith("/oauth2callback"):
        path = path[: -len("oauth2callback")]
    elif path.endswith("oauth2callback"):
        path = path[: -len("oauth2callback")]

    if not path.endswith("/"):
        path = f"{path}/"

    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def patch_streamlit_logout_redirect() -> None:
    from streamlit.auth_util import build_logout_url, get_validated_redirect_uri
    from streamlit.web.server.starlette import starlette_auth_routes as auth_routes
    from streamlit.web.server.starlette.starlette_server_config import (
        TOKENS_COOKIE_NAME,
        USER_COOKIE_NAME,
    )

    if getattr(auth_routes, "_fanme_logout_redirect_patch", False):
        return

    async def fanme_provider_logout_url(request):
        cookie_value = auth_routes._get_cookie_value_from_request(request, USER_COOKIE_NAME)
        if not cookie_value:
            return None

        try:
            user_info = json.loads(cookie_value)
            provider = user_info.get("provider")
            if not provider:
                return None

            client, _ = auth_routes._create_oauth_client(provider)
            metadata = await client.load_server_metadata()
            end_session_endpoint = metadata.get("end_session_endpoint")
            if not end_session_endpoint:
                return None

            redirect_uri = get_validated_redirect_uri()
            if redirect_uri is None:
                return None

            id_token = None
            tokens_cookie_value = auth_routes._get_cookie_value_from_request(
                request,
                TOKENS_COOKIE_NAME,
            )
            if tokens_cookie_value:
                tokens = json.loads(tokens_cookie_value)
                id_token = tokens.get("id_token")

            return build_logout_url(
                end_session_endpoint=end_session_endpoint,
                client_id=client.client_id,
                post_logout_redirect_uri=_post_logout_redirect_uri(redirect_uri),
                id_token=id_token,
            )
        except Exception:
            return None

    auth_routes._get_provider_logout_url = fanme_provider_logout_url
    auth_routes._fanme_logout_redirect_patch = True


def _auth_secrets() -> dict[str, Any]:
    try:
        auth = st.secrets.get("auth", {})
    except Exception:
        return {}

    provider = auth.get(AUTH_PROVIDER, {}) if hasattr(auth, "get") else {}
    return {
        "redirect_uri": auth.get("redirect_uri") if hasattr(auth, "get") else None,
        "cookie_secret": auth.get("cookie_secret") if hasattr(auth, "get") else None,
        "client_id": provider.get("client_id") if hasattr(provider, "get") else None,
        "client_secret": provider.get("client_secret") if hasattr(provider, "get") else None,
        "server_metadata_url": provider.get("server_metadata_url")
        if hasattr(provider, "get")
        else None,
    }


def missing_auth_keys() -> list[str]:
    secrets = _auth_secrets()
    return sorted(key for key in REQUIRED_AUTH_KEYS if not secrets.get(key))


def _user_label() -> str:
    user = st.user
    return (
        user.get("email")
        or user.get("name")
        or user.get("preferred_username")
        or user.get("sub")
        or "Authenticated user"
    )


def logo_data_uri() -> str:
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_login_page() -> None:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"],
        div[data-testid="stSidebarNav"],
        div[data-testid="collapsedControl"],
        header[data-testid="stHeader"],
        div[data-testid="stToolbar"],
        div[data-testid="stDecoration"] {
            display: none !important;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(37, 99, 235, 0.12), transparent 34%),
                radial-gradient(circle at bottom right, rgba(20, 184, 166, 0.10), transparent 30%),
                #f6f8fb !important;
        }

        .block-container {
            max-width: 520px !important;
            min-height: 100vh;
            padding: 0 22px !important;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        div[data-testid="stVerticalBlock"]:has(.fanme-auth-card) {
            width: min(100%, 460px);
            margin: 0 auto;
            padding: 34px 34px 30px;
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 18px;
            background: rgba(255, 255, 255, 0.94);
            box-shadow: 0 22px 60px rgba(15, 23, 42, 0.14);
        }

        .fanme-auth-card {
            text-align: center;
        }

        .fanme-auth-logo {
            display: block;
            width: 72px;
            height: 72px;
            margin: 0 auto 20px;
            border-radius: 18px;
            box-shadow: 0 14px 30px rgba(37, 99, 235, 0.24);
        }

        .fanme-auth-title {
            margin: 0;
            color: #0f172a;
            font-size: 1.62rem;
            line-height: 1.2;
            font-weight: 780;
            letter-spacing: 0;
        }

        .fanme-auth-subtitle {
            margin-top: 8px;
            color: #2563eb;
            font-size: 0.9rem;
            font-weight: 700;
        }

        .fanme-auth-description {
            margin: 16px auto 24px;
            max-width: 340px;
            color: #64748b;
            font-size: 0.92rem;
            line-height: 1.55;
        }

        div[data-testid="stVerticalBlock"]:has(.fanme-auth-card) .stButton {
            display: flex;
            justify-content: center;
        }

        div[data-testid="stVerticalBlock"]:has(.fanme-auth-card) .stButton > button {
            width: 100%;
            min-height: 46px;
            border-radius: 10px;
            font-weight: 740;
            font-size: 0.94rem;
            box-shadow: 0 10px 22px rgba(37, 99, 235, 0.22);
        }

        @media (max-width: 640px) {
            .block-container {
                padding: 0 16px !important;
            }

            div[data-testid="stVerticalBlock"]:has(.fanme-auth-card) {
                padding: 28px 22px 24px;
                border-radius: 14px;
            }

            .fanme-auth-title {
                font-size: 1.38rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    logo_src = logo_data_uri()
    st.markdown(
        f"""
        <div class="fanme-auth-card">
            <img class="fanme-auth-logo" src="{logo_src}" alt="Fanme logo" />
            <h1 class="fanme-auth-title">Fanme Linear Operations</h1>
            <div class="fanme-auth-subtitle">Secure internal dashboard</div>
            <div class="fanme-auth-description">
                Please sign in with your authorized Fanme account to continue.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.button(
        "Login with Logto",
        type="primary",
        on_click=st.login,
        args=[AUTH_PROVIDER],
        use_container_width=True,
    )


def require_login() -> None:
    patch_streamlit_logout_redirect()

    missing = missing_auth_keys()
    if missing:
        st.error(
            "Logto auth is enabled, but Streamlit auth secrets are incomplete: "
            + ", ".join(missing)
        )
        st.info(
            "Create .streamlit/secrets.toml from .streamlit/secrets.example.toml, "
            "then restart the Streamlit container."
        )
        st.stop()

    if not st.user.is_logged_in:
        render_login_page()
        st.stop()

    st.sidebar.caption(f"Signed in: {_user_label()}")
    st.sidebar.button("Log out", on_click=st.logout)
