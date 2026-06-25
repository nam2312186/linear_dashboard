from __future__ import annotations

from typing import Any

import streamlit as st


AUTH_PROVIDER = "logto"
REQUIRED_AUTH_KEYS = {
    "redirect_uri",
    "cookie_secret",
    "client_id",
    "client_secret",
    "server_metadata_url",
}


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
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 46px;
            height: 46px;
            margin-bottom: 18px;
            border-radius: 12px;
            color: #ffffff;
            background: linear-gradient(135deg, #2563eb, #0f766e);
            font-weight: 800;
            font-size: 1.05rem;
            letter-spacing: 0;
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
    st.markdown(
        """
        <div class="fanme-auth-card">
            <div class="fanme-auth-logo">F</div>
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
