"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 7: SaaS Dashboard — Kullanıcı Girişi + Abonelik

Çalıştır:
streamlit run dashboard_saas.py
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime

st.set_page_config(
    page_title="OPS Intelligence — E-Ticaret Analiz Platformu",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig
from ai_engine import AIConfig, run_full_analysis
from meta_ads import MetaConfig, run_meta_analysis
from onboarding import test_shopify_connection, test_meta_connection, SHOPIFY_GUIDE, META_GUIDE
from pdf_report import generate_pdf_report
from auth import get_db, PLANS
from stripe_payments import create_checkout_session, get_subscription_status, STRIPE_PUBLISHABLE_KEY

# ─────────────────────────────────────────────
# STİL — LÜKS & PROFESYONEL TEMA
# ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap');

/* ── Koyu modu tamamen kapat ── */
[data-theme="dark"] { filter: none !important; }

:root, [data-theme="light"], [data-theme="dark"] {
    --white:   #ffffff !important;
    --bg:      #f8f7f4 !important;
    --surface: #f0ede6 !important;
    --black:   #0d0c0a !important;
    --dark:    #1a1916 !important;
    --gold:    #c9963a !important;
    --gold-l:  #e8b84b !important;
    --text:    #2c2a25 !important;
    --muted:   #8a8070 !important;
    --border:  #e0d8cc !important;
    --danger:  #c0392b !important;
    --warn:    #d4ac0d !important;
    --success: #1a7a4a !important;
    color-scheme: light !important;
}

/* ── Tüm arkaplanları zorla beyaz/krem yap ── */
html, body, [class*="css"],
.main, .main > div,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > section,
[data-testid="block-container"],
.block-container,
[data-testid="stVerticalBlock"],
[data-testid="stHorizontalBlock"] {
    background-color: #ffffff !important;
    color: #2c2a25 !important;
    font-family: 'DM Sans', sans-serif !important;
    color-scheme: light !important;
}

h1, h2, h3 {
    font-family: 'Instrument Serif', serif !important;
    color: #0d0c0a !important;
    letter-spacing: -0.02em !important;
}
p, span, div, label { color: #2c2a25; }
hr { border-color: #e0d8cc !important; }
.block-container { padding-top: 2rem !important; max-width: 1200px; }

/* ── Sidebar ── */
section[data-testid="stSidebar"],
section[data-testid="stSidebar"] > div {
    background-color: #f8f7f4 !important;
    border-right: 1px solid #e0d8cc !important;
}

/* ── Tüm kartları ve div'leri beyaz yap ── */
[data-testid="stMarkdownContainer"] > div,
[data-testid="element-container"] > div {
    background: transparent !important;
}

/* ── Input ── */
.stTextInput > div > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
}
.stTextInput > div > div > input {
    background: #ffffff !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 100px !important;
    color: #2c2a25 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 14px !important;
    padding: 12px 18px !important;
    outline: none !important;
    box-shadow: none !important;
}
.stTextInput > div > div > input:focus {
    border-color: #c9963a !important;
    box-shadow: 0 0 0 2px rgba(201,150,58,0.12) !important;
    outline: none !important;
}
.stTextInput > label {
    color: #8a8070 !important;
    font-size: 13px !important;
    font-family: 'DM Sans', sans-serif !important;
}

/* ── Buton ── */
.stButton > button {
    background: #0d0c0a !important;
    color: #ffffff !important;
    border: none !important;
    border-radius: 100px !important;
    font-family: 'DM Sans', sans-serif !important;
    font-weight: 500 !important;
    font-size: 14px !important;
    padding: 12px 28px !important;
    transition: all 0.2s !important;
    letter-spacing: 0 !important;
    text-transform: none !important;
    width: 100%;
}
.stButton > button:hover {
    background: #1a1916 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 24px rgba(0,0,0,0.15) !important;
}
.stButton > button:focus {
    outline: none !important;
    box-shadow: 0 0 0 2px rgba(201,150,58,0.3) !important;
}

/* ── Tab ── */
.stTabs [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid #e0d8cc !important;
    gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif !important;
    font-size: 12px !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #8a8070 !important;
    background: transparent !important;
    border: none !important;
    padding: 12px 20px !important;
}
.stTabs [aria-selected="true"] {
    color: #0d0c0a !important;
    border-bottom: 2px solid #c9963a !important;
    background: transparent !important;
}
.stTabs [data-baseweb="tab-highlight"] { background-color: #c9963a !important; }
.stTabs [data-baseweb="tab-border"] { background-color: #e0d8cc !important; }

/* ── Metrik kartları ── */
[data-testid="stMetric"] {
    background: #f8f7f4 !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 16px !important;
    padding: 20px 24px !important;
    position: relative !important;
    overflow: hidden !important;
}
[data-testid="stMetric"]::before {
    content: '' !important;
    position: absolute !important;
    top: 0; left: 0 !important;
    width: 2px !important; height: 100% !important;
    background: linear-gradient(180deg, #c9963a, #e8b84b) !important;
}
[data-testid="stMetricLabel"] {
    color: #8a8070 !important;
    font-size: 11px !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}
[data-testid="stMetricValue"] {
    color: #0d0c0a !important;
    font-family: 'Instrument Serif', serif !important;
    font-size: 28px !important;
}

/* ── Özel kartlar ── */
.auth-card {
    background: #ffffff !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 16px !important;
    padding: 48px 52px !important;
    max-width: 460px !important;
    margin: 0 auto !important;
    box-shadow: 0 4px 24px rgba(0,0,0,0.06) !important;
}

.plan-card {
    background: #ffffff !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 16px !important;
    padding: 32px 28px !important;
    text-align: center !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
}
.plan-card:hover { transform: translateY(-4px) !important; box-shadow: 0 20px 60px rgba(0,0,0,0.08) !important; }
.plan-card.featured { background: #0d0c0a !important; border-color: #0d0c0a !important; }

/* Ana sayfa kartları (dark background sorunu) */
.home-card {
    background: #f8f7f4 !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 16px !important;
    padding: 28px 24px !important;
    transition: transform 0.2s, box-shadow 0.2s !important;
    color: #2c2a25 !important;
}
.home-card:hover { transform: translateY(-3px) !important; box-shadow: 0 16px 48px rgba(0,0,0,0.08) !important; }
.home-card-icon { font-size: 28px !important; margin-bottom: 12px !important; }
.home-card-title { font-family: 'Instrument Serif', serif !important; font-size: 18px !important; font-weight: 400 !important; color: #0d0c0a !important; margin-bottom: 8px !important; }
.home-card-desc { font-size: 13px !important; color: #8a8070 !important; line-height: 1.6 !important; }

/* ── Bulgu kartları ── */
.finding-card {
    background: #f8f7f4 !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 12px !important;
    padding: 20px 24px !important;
    margin-bottom: 10px !important;
    border-left: 3px solid !important;
    transition: transform 0.2s !important;
}
.finding-card:hover { transform: translateX(4px) !important; }
.finding-critical { border-left-color: #c0392b !important; }
.finding-warning  { border-left-color: #d4ac0d !important; }
.finding-ok       { border-left-color: #c9963a !important; }

.tag { display: inline-block !important; padding: 3px 10px !important; border-radius: 100px !important; font-size: 10px !important; letter-spacing: 0.08em !important; text-transform: uppercase !important; font-weight: 500 !important; }
.tag-critical { background: rgba(192,57,43,0.08) !important; color: #c0392b !important; border: 1px solid rgba(192,57,43,0.2) !important; }
.tag-warning  { background: rgba(212,172,13,0.08) !important; color: #a07c00 !important; border: 1px solid rgba(212,172,13,0.2) !important; }
.tag-ok       { background: rgba(201,150,58,0.08) !important; color: #c9963a !important; border: 1px solid rgba(201,150,58,0.2) !important; }

.finding-rec {
    font-size: 13px !important;
    margin-top: 12px !important;
    padding: 10px 16px !important;
    background: rgba(201,150,58,0.05) !important;
    border-radius: 8px !important;
    border-left: 2px solid #c9963a !important;
    color: #2c2a25 !important;
    line-height: 1.6 !important;
}

/* ── Quick wins ── */
.qw-item {
    background: #f8f7f4 !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 12px !important;
    padding: 14px 20px !important;
    margin-bottom: 10px !important;
    display: flex !important;
    align-items: flex-start !important;
    gap: 16px !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    color: #2c2a25 !important;
}
.qw-num {
    font-family: 'Instrument Serif', serif !important;
    font-size: 22px !important;
    font-weight: 400 !important;
    color: #c9963a !important;
    min-width: 32px !important;
    line-height: 1 !important;
}

/* ── Sağlık skoru ── */
.health-box {
    background: #f8f7f4 !important;
    border: 1px solid #e0d8cc !important;
    border-radius: 16px !important;
    padding: 28px 32px !important;
    text-align: center !important;
    position: relative !important;
    overflow: hidden !important;
}
.health-box::after {
    content: '' !important;
    position: absolute !important;
    bottom: 0; left: 0; right: 0 !important;
    height: 2px !important;
    background: linear-gradient(90deg, transparent, #c9963a, transparent) !important;
}
.score-num {
    font-family: 'Instrument Serif', serif !important;
    font-size: 68px !important;
    font-weight: 400 !important;
    line-height: 1 !important;
    letter-spacing: -2px !important;
}

/* ── Kilitli ── */
.locked-feature {
    background: #f8f7f4 !important;
    border: 1px dashed #e0d8cc !important;
    border-radius: 12px !important;
    padding: 24px !important;
    text-align: center !important;
    color: #8a8070 !important;
    font-size: 13px !important;
}

/* ── Dataframe ── */
.stDataFrame { border: 1px solid #e0d8cc !important; border-radius: 12px !important; overflow: hidden !important; }
.stDataFrame th { background: #f8f7f4 !important; color: #8a8070 !important; }
.stDataFrame td { color: #2c2a25 !important; }

/* ── Toggle & Radio ── */
div[data-testid="stForm"] { border: none !important; }
.stSelectbox > div > div { background: #ffffff !important; border-color: #e0d8cc !important; border-radius: 100px !important; }
.stRadio > div { gap: 8px !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: #f8f7f4; }
::-webkit-scrollbar-thumb { background: #e0d8cc; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #c9963a; }
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# YARDIMCILAR
# ─────────────────────────────────────────────

def score_color(s): return "#c9963a" if s>=75 else "#d4ac0d" if s>=50 else "#c0392b"

def plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans, sans-serif", color="#8a8070", size=11),
        xaxis=dict(gridcolor="#e0d8cc", linecolor="#e0d8cc"),
        yaxis=dict(gridcolor="#e0d8cc", linecolor="#e0d8cc"),
        margin=dict(l=0, r=0, t=30, b=0),
    )

def plan_badge(plan_key: str) -> str:
    colors = {"free":"#8a8070","starter":"#c9963a","pro":"#0d0c0a"}
    bg     = {"free":"#f0ede6","starter":"#fff8e8","pro":"#0d0c0a"}
    tc     = {"free":"#8a8070","starter":"#c9963a","pro":"#ffffff"}
    c = colors.get(plan_key,"#8a8070")
    b = bg.get(plan_key,"#f0ede6")
    t = tc.get(plan_key,"#8a8070")
    name = PLANS[plan_key].name
    return f'<span style="background:{b};border:1px solid {c};color:{t};padding:3px 12px;border-radius:100px;font-size:11px;letter-spacing:0.05em;font-family:DM Sans,sans-serif;font-weight:500">{name}</span>'


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

defaults = {
    "auth_page":   "login",   # login | register | forgot
    "user":        None,
    "app_page":    "home",    # home | connect | analysis | pricing
    "shopify_cfg": None,
    "meta_cfg":    None,
    "use_mock_shopify": True,
    "use_mock_meta":    True,
    "shop_name":   "",
    "result":      None,
    "meta_result": None,
    "analysis_running": False,
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

db = get_db()


# ─────────────────────────────────────────────
# SAYFA: GİRİŞ / KAYIT
# ─────────────────────────────────────────────

def page_auth():
    st.markdown("""
    <div style="text-align:center;padding:40px 0 32px">
        <div style="font-size:28px;font-weight:600;color:#0d0c0a;letter-spacing:-0.03em;margin-bottom:8px">
            OPS<span style="color:#c9963a">.</span>
        </div>
        <div style="width:40px;height:1px;background:linear-gradient(90deg,transparent,#c9963a,transparent);margin:0 auto 12px"></div>
        <div style="font-size:13px;color:#8a8070;letter-spacing:0.05em">
            E-Ticaret Operasyonel Analiz Platformu
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        # Sekme seçimi
        tab_login, tab_register = st.tabs(["  Giriş Yap  ", "  Kayıt Ol  "])

        # ── GİRİŞ ───────────────────────────
        with tab_login:
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            email    = st.text_input("E-posta", placeholder="ornek@sirket.com", key="login_email")
            password = st.text_input("Şifre", type="password", placeholder="••••••••", key="login_pass")

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Giriş Yap", use_container_width=True, key="btn_login"):
                if not email or not password:
                    st.error("E-posta ve şifre gerekli.")
                else:
                    user = db.authenticate(email, password)
                    if user:
                        st.session_state.user = user
                        st.session_state.app_page = "home"
                        st.rerun()
                    else:
                        st.error("E-posta veya şifre hatalı.")

            st.divider()
            st.markdown("""
            <div style="text-align:center;font-size:11px;color:#6b7280">
                Demo hesap: <code>demo@opsint.com</code> / <code>demo123</code><br>
                <span style="color:#00e5b0">Pro plan</span> — tüm özellikler açık
            </div>
            """, unsafe_allow_html=True)

        # ── KAYIT ────────────────────────────
        with tab_register:
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

            r_name     = st.text_input("Ad Soyad", placeholder="Ali Yılmaz", key="reg_name")
            r_email    = st.text_input("E-posta", placeholder="ornek@sirket.com", key="reg_email")
            r_password = st.text_input("Şifre", type="password", placeholder="Min. 6 karakter", key="reg_pass")
            r_password2= st.text_input("Şifre (tekrar)", type="password", placeholder="••••••••", key="reg_pass2")

            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

            if st.button("Ücretsiz Başla", use_container_width=True, key="btn_register"):
                if not r_name or not r_email or not r_password:
                    st.error("Tüm alanları doldur.")
                elif r_password != r_password2:
                    st.error("Şifreler eşleşmiyor.")
                elif len(r_password) < 6:
                    st.error("Şifre en az 6 karakter olmalı.")
                else:
                    try:
                        user = db.create_user(r_email, r_name, r_password, plan="free")
                        st.session_state.user = user
                        st.session_state.app_page = "home"
                        st.success("Hesap oluşturuldu!")
                        import time; time.sleep(0.8)
                        st.rerun()
                    except ValueError as e:
                        st.error(str(e))

            st.divider()
            st.markdown("""
            <div style="text-align:center;font-size:11px;color:#6b7280">
                Ücretsiz plan ile başla.<br>
                Dilediğin zaman yükselt.
            </div>
            """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR (giriş sonrası)
# ─────────────────────────────────────────────

def render_sidebar():
    user  = st.session_state.user
    plan  = PLANS[user["plan"]]
    limits= db.check_plan_limit(user["email"])

    with st.sidebar:
        # Kullanıcı bilgisi
        st.markdown(f"""
        <div style="padding:20px 0 12px">
            <div style="font-size:20px;font-weight:600;color:#0d0c0a;letter-spacing:-0.03em">
                OPS<span style="color:#c9963a">.</span>
            </div>
            <div style="font-size:13px;color:#8a8070;margin-top:8px">{user['name']}</div>
            <div style="font-size:12px;color:#8a8070;margin-top:2px">{user['email']}</div>
            <div style="margin-top:10px">{plan_badge(user['plan'])}</div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Navigasyon
        pages = [
            ("🏠", "Ana Sayfa",     "home"),
            ("🔗", "Mağaza Bağla",  "connect"),
            ("📊", "Analiz",         "analysis"),
            ("💳", "Planlar",        "pricing"),
        ]
        for icon, label, page_key in pages:
            active = st.session_state.app_page == page_key
            style  = "color:#00e5b0;font-weight:600;" if active else "color:#9ca3b0;"
            if st.button(f"{icon}  {label}", key=f"nav_{page_key}",
                         use_container_width=True):
                st.session_state.app_page = page_key
                st.rerun()

        st.divider()

        # Plan kullanım göstergesi
        used  = limits["used"]
        limit = limits["limit"]
        pct   = min(int(used / max(limit, 1) * 100), 100)
        bar_color = "#ff3b5c" if pct > 80 else "#f5a623" if pct > 50 else "#00e5b0"

        st.markdown(f"""
        <div style="font-size:10px;color:#6b7280;letter-spacing:0.1em;text-transform:uppercase;margin-bottom:6px">
            Bu Ay Kullanım
        </div>
        <div style="font-size:13px;color:#2c2a25;margin-bottom:6px">{used} / {limit} analiz</div>
        <div style="background:#1e2128;border-radius:4px;height:4px">
            <div style="width:{pct}%;background:{bar_color};height:4px;border-radius:4px"></div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # Çıkış
        if st.button("↩  Çıkış Yap", use_container_width=True):
            for k in defaults:
                st.session_state[k] = defaults[k]
            st.rerun()


# ─────────────────────────────────────────────
# SAYFA: ANA SAYFA
# ─────────────────────────────────────────────

def page_home():
    user  = st.session_state.user
    plan  = PLANS[user["plan"]]
    result= st.session_state.result

    st.markdown(f"""
    <div style="margin-bottom:24px">
        <div style="font-family:'Instrument Serif',serif;font-size:32px;font-weight:400;letter-spacing:-0.02em;color:#0d0c0a">
            Hoş geldin, {user['name'].split()[0]}! 👋
        </div>
        <div style="font-size:14px;color:#8a8070;margin-top:4px">
            {plan.name} Plan &nbsp;·&nbsp; €{plan.price_eur}/ay
        </div>
    </div>
    """, unsafe_allow_html=True)

    if result is None:
        # Henüz analiz yok
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("""
            <div style="background:#f8f7f4;border:1px solid #e0d8cc;border-radius:16px;padding:28px 24px">
                <div style="font-size:28px;margin-bottom:12px">🔗</div>
                <div style="font-family:'Instrument Serif',serif;font-size:18px;font-weight:400;color:#0d0c0a;margin-bottom:8px">
                    Mağazanı Bağla
                </div>
                <div style="font-size:13px;color:#8a8070;line-height:1.6">
                    Shopify mağazanı bağla ve AI destekli operasyonel analize başla.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Mağaza Bağla →", key="home_connect"):
                st.session_state.app_page = "connect"
                st.rerun()

        with c2:
            st.markdown("""
            <div style="background:#f8f7f4;border:1px solid #e0d8cc;border-radius:16px;padding:28px 24px">
                <div style="font-size:28px;margin-bottom:12px">📊</div>
                <div style="font-family:'Instrument Serif',serif;font-size:18px;font-weight:400;color:#0d0c0a;margin-bottom:8px">
                    Demo Analizi Dene
                </div>
                <div style="font-size:13px;color:#8a8070;line-height:1.6">
                    Gerçek bağlantı olmadan, örnek verilerle sistemi keşfet.
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Demo Başlat →", key="home_demo"):
                st.session_state.use_mock_shopify = True
                st.session_state.use_mock_meta    = True
                st.session_state.shopify_cfg = ShopifyConfig(use_mock=True, mock_order_count=200)
                st.session_state.meta_cfg    = MetaConfig(use_mock=True)
                st.session_state.shop_name   = "Demo Mağaza"
                st.session_state.app_page    = "analysis"
                st.rerun()

        # Plan özellikleri
        st.divider()
        st.markdown("**Planın Kapsamı**")
        feats = [
            ("Mağaza Bağlantısı",  f"Max {plan.max_stores} mağaza", True),
            ("Aylık Sipariş",      f"{plan.max_orders:,} sipariş",  True),
            ("AI Analiz Raporu",   "GPT-4o destekli",               plan.ai_reports),
            ("PDF Rapor",          "Müşteriye gönderilebilir",       plan.pdf_export),
            ("Meta Ads Analizi",   "ROAS + Çapraz Alarm",           plan.meta_ads),
            ("Destek",             plan.support,                     True),
        ]
        for feat, detail, active in feats:
            icon  = "✅" if active else "🔒"
            color = "#e8eaf0" if active else "#3a3f4a"
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;padding:10px 0;
                        border-bottom:1px solid #e0d8cc;color:{color}">
                <span>{icon} {feat}</span>
                <span style="color:#8a8070;font-size:12px">{detail}</span>
            </div>
            """, unsafe_allow_html=True)

        if user["plan"] != "pro":
            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            if st.button("⬆  Planı Yükselt", use_container_width=True):
                st.session_state.app_page = "pricing"
                st.rerun()

    else:
        # Son analiz özeti
        analysis = result["analysis"]
        metrics  = result.get("metrics", {})
        ft  = metrics.get("fulfillment_time", {})
        rev = metrics.get("revenue", {})
        score = analysis["overall_health_score"]
        sc    = score_color(score)

        st.markdown(f"""
        <div style="font-size:11px;color:#6b7280;margin-bottom:16px">
            Son Analiz: {result.get('generated_at','')[:19].replace('T',' ')} &nbsp;·&nbsp;
            {st.session_state.shop_name}
        </div>
        """, unsafe_allow_html=True)

        c1,c2,c3,c4 = st.columns(4)
        c1.metric("Sağlık Skoru", f"{score}/100", analysis["overall_health_label"])
        c2.metric("Toplam Gelir", f"€{rev.get('total_revenue',0):,.0f}")
        c3.metric("Ort. Sepet", f"€{rev.get('aov',0):.0f}")
        c4.metric("Fulfillment", f"{ft.get('median',0)}s")

        st.divider()
        if st.button("📊 Tam Analizi Gör →", use_container_width=True):
            st.session_state.app_page = "analysis"
            st.rerun()


# ─────────────────────────────────────────────
# SAYFA: MAĞAZA BAĞLA
# ─────────────────────────────────────────────

def page_connect():
    user   = st.session_state.user
    limits = db.check_plan_limit(user["email"])
    plan   = limits["plan"]

    st.markdown("""
    <div style="font-family:'Syne',sans-serif;font-size:24px;font-weight:800;margin-bottom:4px">
        Mağaza Bağlantısı
    </div>
    <div style="font-size:13px;color:#6b7280;margin-bottom:28px">
        Shopify ve Meta Ads hesaplarını bağla.
    </div>
    """, unsafe_allow_html=True)

    # Shopify
    st.markdown("#### 🛍️ Shopify")
    mode = st.radio("Mod:", ["🎮 Demo", "🔗 Gerçek Mağaza"], horizontal=True, key="conn_mode")

    if "Demo" in mode:
        st.info("Demo modunda 200 adet gerçekçi sipariş verisi kullanılır.")
        if st.button("Demo Mağazayla Devam Et", key="demo_conn"):
            st.session_state.use_mock_shopify = True
            st.session_state.shopify_cfg = ShopifyConfig(use_mock=True, mock_order_count=200)
            st.session_state.shop_name   = "Demo Mağaza"
            st.success("✅ Demo mağaza bağlandı!")
    else:
        with st.expander("📖 Access Token Nasıl Alınır?"):
            st.markdown(SHOPIFY_GUIDE)
        col1, col2 = st.columns(2)
        with col1:
            shop_domain = st.text_input("Shopify Domain", placeholder="magazan.myshopify.com")
        with col2:
            access_token = st.text_input("Access Token", type="password", placeholder="shpat_xxx")

        if st.button("Bağlantıyı Test Et", key="test_shopify"):
            if not shop_domain or not access_token:
                st.error("Domain ve token gerekli.")
            else:
                with st.spinner("Bağlanılıyor..."):
                    res = test_shopify_connection(shop_domain, access_token)
                if res.success:
                    st.success(f"✅ {res.shop_name} — {res.order_count:,} sipariş")
                    st.session_state.use_mock_shopify = False
                    st.session_state.shopify_cfg = ShopifyConfig(
                        shop_domain=shop_domain, access_token=access_token, use_mock=False)
                    st.session_state.shop_name = res.shop_name
                    db.add_store(user["email"], {"domain": shop_domain, "name": res.shop_name})
                else:
                    st.error(f"{res.message} — {res.detail}")

    st.divider()

    # Meta Ads
    st.markdown("#### 📣 Meta Ads")
    meta_mode = st.radio("Mod:", ["🎮 Demo", "🔗 Gerçek Hesap", "⏭️ Atla"],
                         horizontal=True, key="meta_conn_mode")

    if "Demo" in meta_mode:
        if st.button("Demo Meta Bağla", key="demo_meta"):
            st.session_state.use_mock_meta = True
            st.session_state.meta_cfg = MetaConfig(use_mock=True)
            st.success("✅ Demo Meta Ads bağlandı!")

    elif "Atla" in meta_mode:
        st.session_state.meta_cfg = None
        st.info("Meta Ads analizi devre dışı.")

    elif not limits["can_meta"]:
        st.markdown("""
        <div class="locked-feature">
            🔒 Meta Ads entegrasyonu <strong>Pro Plan</strong> gerektirir.<br>
            <span style="font-size:11px">€79/ay — Hemen yükselt</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button("Pro'ya Yükselt"):
            st.session_state.app_page = "pricing"
            st.rerun()
    else:
        with st.expander("📖 Meta Token Nasıl Alınır?"):
            st.markdown(META_GUIDE)
        col1, col2 = st.columns(2)
        with col1:
            meta_token = st.text_input("Access Token", type="password", placeholder="EAAxx...")
        with col2:
            meta_account = st.text_input("Ad Account ID", placeholder="act_123456789")

        if st.button("Meta Bağlantısını Test Et"):
            if not meta_token:
                st.error("Token gerekli.")
            else:
                with st.spinner("Bağlanılıyor..."):
                    res = test_meta_connection(meta_token, meta_account)
                if res.success:
                    st.success(f"✅ {res.ad_account or 'Doğrulandı'}")
                    st.session_state.use_mock_meta = False
                    st.session_state.meta_cfg = MetaConfig(
                        access_token=meta_token, ad_account_id=meta_account, use_mock=False)
                else:
                    st.error(f"{res.message}")

    st.divider()
    if st.session_state.shopify_cfg:
        if st.button("▶  Analize Geç →", use_container_width=True):
            st.session_state.app_page = "analysis"
            st.rerun()


# ─────────────────────────────────────────────
# SAYFA: ANALİZ
# ─────────────────────────────────────────────

def page_analysis():
    user   = st.session_state.user
    limits = db.check_plan_limit(user["email"])
    plan   = limits["plan"]
    result = st.session_state.result

    # Başlat butonu
    if result is None or st.button("🔄 Yeniden Analiz Et"):
        if not st.session_state.shopify_cfg:
            st.warning("Önce mağazanı bağla.")
            if st.button("Mağaza Bağla →"):
                st.session_state.app_page = "connect"
                st.rerun()
            return

        if not limits["allowed"]:
            st.error(f"Bu ay {limits['used']} analiz hakkı kullandın (limit: {limits['limit']}). Plan yükselt.")
            return

        prog = st.progress(0, "Shopify verisi çekiliyor...")
        # AIConfig otomatik olarak Streamlit Secrets'tan OpenAI key okur
        ai_cfg = AIConfig(language="tr")

        prog.progress(30, "Metrikler hesaplanıyor...")
        st.session_state.result = run_full_analysis(st.session_state.shopify_cfg, ai_cfg)
        prog.progress(65, "AI analizi yapılıyor...")

        if st.session_state.meta_cfg and limits["can_meta"]:
            st.session_state.meta_result = run_meta_analysis(
                st.session_state.meta_cfg,
                st.session_state.result.get("products_df")
            )

        db.record_analysis(user["email"])
        prog.progress(100, "Tamamlandı!")
        import time; time.sleep(0.5)
        st.rerun()

    if result is None:
        return

    # Güvenlik kontrolü — analiz başarısız olduysa
    if not result.get("success") or "analysis" not in result:
        error_msg = result.get("error", "Bilinmeyen hata")
        st.error(f"Analiz tamamlanamadı: {error_msg}")
        st.info("Mock AI ile tekrar deneniyor...")
        # Mock AI ile zorla çalıştır
        from ai_engine import AIConfig, run_full_analysis
        mock_result = run_full_analysis(
            st.session_state.shopify_cfg,
            AIConfig(use_mock_ai=True, language="tr")
        )
        if mock_result.get("success") and "analysis" in mock_result:
            st.session_state.result = mock_result
            st.rerun()
        else:
            if st.button("Tekrar Dene"):
                st.session_state.result = None
                st.rerun()
        return

    # ── SONUÇ EKRANI
    analysis    = result["analysis"]
    metrics     = result.get("metrics", {})
    orders_df   = result.get("orders_df", pd.DataFrame())
    products_df = result.get("products_df", pd.DataFrame())
    meta_result = st.session_state.meta_result
    ft  = metrics.get("fulfillment_time", {})
    rev = metrics.get("revenue", {})
    score = analysis["overall_health_score"]
    sc    = score_color(score)

    # Başlık
    st.markdown(f"""
    <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;margin-bottom:4px">
        Analiz Sonuçları
    </div>
    <div style="font-size:11px;color:#6b7280;margin-bottom:20px">
        {st.session_state.shop_name} &nbsp;·&nbsp; {result.get('generated_at','')[:19].replace('T',' ')}
        &nbsp;·&nbsp; {ft.get('total_fulfilled',0)} sipariş
    </div>
    """, unsafe_allow_html=True)

    # KPI satırı
    c1,c2,c3,c4,c5 = st.columns([1.4,1,1,1,1])
    with c1:
        st.markdown(f"""
        <div class="health-box">
            <div style="font-size:10px;color:#6b7280;letter-spacing:0.12em;text-transform:uppercase">Operasyonel Sağlık</div>
            <div class="score-num" style="color:{sc};margin:6px 0 4px">{score}</div>
            <div style="font-size:12px;color:{sc}">{analysis['overall_health_label']}</div>
            <div style="width:100%;background:#1e2128;height:3px;border-radius:2px;margin-top:12px">
                <div style="width:{score}%;background:{sc};height:3px;border-radius:2px"></div>
            </div>
        </div>""", unsafe_allow_html=True)
    with c2: st.metric("Fulfillment", f"{ft.get('mean',0)}s", f"Medyan {ft.get('median',0)}s", delta_color="off")
    with c3: st.metric("Toplam Gelir", f"€{rev.get('total_revenue',0):,.0f}", f"{rev.get('total_orders',0)} sipariş")
    with c4: st.metric("Ort. Sepet", f"€{rev.get('aov',0):.0f}", "↑ Hedef €250")
    with c5: st.metric("İptal Oranı", f"%{rev.get('cancellation_rate',0)}", "Hedef <%2.5", delta_color="inverse")

    st.divider()

    # Sekmeler
    tab_names = ["Bulgular", "Gelir", "Stok", "Aksiyonlar"]
    if meta_result and limits["can_meta"]: tab_names.append("Meta Ads")
    tabs = st.tabs(tab_names)

    # ── TAB 1: BULGULAR
    with tabs[0]:
        st.markdown(f"""
        <div style="background:#111318;border:1px solid #1e2128;border-radius:8px;
                    padding:16px 20px;margin-bottom:20px;font-size:13px;line-height:1.7;color:#9ca3b0">
            <span style="font-family:'Syne',sans-serif;color:#2c2a25;font-weight:600">
            Yönetici Özeti —</span> {analysis['executive_summary']}
        </div>""", unsafe_allow_html=True)

        for f in sorted(analysis["findings"], key=lambda x: x["priority"]):
            sev  = f["severity"]
            icon = {"critical":"🔴","warning":"⚠️","ok":"✅"}[sev]
            pri  = {1:"ACİL",2:"Yüksek",3:"Orta",4:"Düşük",5:"İzle"}[f["priority"]]
            st.markdown(f"""
            <div class="finding-card finding-{sev}">
                <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px">
                    <span class="tag tag-{sev}">{icon} {pri}</span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">{f['area']}</span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">Efor: {f.get('estimated_effort','—')}</span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">Etki: {f.get('estimated_impact','—')}</span>
                </div>
                <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:600;margin-bottom:6px">{f['title']}</div>
                <div style="font-size:11px;color:#6b7280;margin-bottom:4px">Kök Neden</div>
                <div style="font-size:12px;color:#9ca3b0;line-height:1.6">{f['root_cause']}</div>
                <div style="font-size:11px;color:#6b7280;margin-top:8px;margin-bottom:4px">İş Etkisi</div>
                <div style="font-size:12px;color:#9ca3b0">{f.get('impact','—')}</div>
                <div class="finding-rec">
                    <span style="color:#00e5b0;font-size:10px;letter-spacing:0.1em;text-transform:uppercase">Aksiyon →</span><br>
                    {f['recommendation']}
                </div>
            </div>""", unsafe_allow_html=True)

    # ── TAB 2: GELİR
    with tabs[1]:
        if not orders_df.empty:
            valid = orders_df[~orders_df["fulfillment_status"].isin(["cancelled","refunded"])].copy()
            valid["date"] = pd.to_datetime(valid["created_at"]).dt.date
            daily = valid.groupby("date")["total_price"].sum().reset_index()
            daily["ma7"] = daily["total_price"].rolling(7, min_periods=1).mean()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily["date"], y=daily["total_price"], name="Günlük €",
                                 marker_color="rgba(0,229,176,0.25)", marker_line_color="rgba(0,229,176,0.6)", marker_line_width=1))
            fig.add_trace(go.Scatter(x=daily["date"], y=daily["ma7"], name="7g Ort.",
                                     line=dict(color="#ff6b35", width=2)))
            fig.update_layout(title="Günlük Gelir", legend=dict(orientation="h", y=1.1), **plotly_theme())
            st.plotly_chart(fig, use_container_width=True)

    # ── TAB 3: STOK
    with tabs[2]:
        if not products_df.empty:
            inv_df = products_df[["title","category","inventory","price","margin_pct"]].copy()
            inv_df["durum"] = inv_df["inventory"].apply(
                lambda v: "🔴 TÜKENDİ" if v==0 else "🔴 KRİTİK" if v<10 else "⚠️ DÜŞÜK" if v<30 else "✅ NORMAL")
            inv_df.columns = ["Ürün","Kategori","Stok","Fiyat €","Margin %","Durum"]
            st.dataframe(
                pd.concat([inv_df[inv_df["Stok"]<30], inv_df[inv_df["Stok"]>=30]]).reset_index(drop=True),
                use_container_width=True, hide_index=True,
                column_config={"Stok": st.column_config.ProgressColumn("Stok", max_value=200, format="%d"),
                               "Margin %": st.column_config.NumberColumn(format="%.1f%%")})

    # ── TAB 4: AKSİYONLAR
    with tabs[3]:
        st.markdown("""<div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;margin-bottom:16px">Bu Hafta Yapılacaklar</div>""", unsafe_allow_html=True)
        for i, qw in enumerate(analysis.get("quick_wins",[]), 1):
            st.markdown(f"""<div class="qw-item"><div class="qw-num">{i:02d}</div><div>{qw}</div></div>""", unsafe_allow_html=True)

        st.divider()

        # İndirme butonları
        dl1, dl2 = st.columns(2)
        with dl1:
            if limits["can_pdf"]:
                pdf = generate_pdf_report(result, meta_result, st.session_state.shop_name)
                st.download_button("⬇  PDF Rapor", data=pdf,
                    file_name=f"ops_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf", use_container_width=True)
            else:
                st.markdown("""<div class="locked-feature">🔒 PDF export Starter+ plan gerektirir</div>""", unsafe_allow_html=True)

        with dl2:
            export = {k:v for k,v in result.items() if k not in ("orders_df","products_df")}
            st.download_button("⬇  JSON Veri", data=json.dumps(export, ensure_ascii=False, indent=2, default=str),
                file_name=f"ops_{datetime.now().strftime('%Y%m%d')}.json",
                mime="application/json", use_container_width=True)

    # ── TAB 5: META ADS
    if meta_result and limits["can_meta"] and len(tabs) > 4:
        with tabs[4]:
            ra = meta_result["roas_analysis"]
            mc1,mc2,mc3,mc4 = st.columns(4)
            mc1.metric("Toplam Harcama", f"€{ra['total_spend']:,.0f}")
            mc2.metric("Toplam Gelir",   f"€{ra['total_revenue']:,.0f}")
            mc3.metric("Blended ROAS",   f"{ra['blended_roas']}x")
            mc4.metric("Kritik Kampanya",f"{ra['bad_campaigns']}", delta_color="inverse")
            st.divider()
            camp = meta_result["campaign_summary"][["campaign_name","spend","revenue","roas","durum"]].copy()
            camp.columns = ["Kampanya","Harcama €","Gelir €","ROAS","Durum"]
            st.dataframe(camp, use_container_width=True, hide_index=True,
                column_config={"ROAS": st.column_config.ProgressColumn(max_value=5, format="%.2fx")})


# ─────────────────────────────────────────────
# SAYFA: FİYATLANDIRMA
# ─────────────────────────────────────────────

def page_pricing():
    user = st.session_state.user

    st.markdown("""
    <div style="text-align:center;margin-bottom:32px">
        <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;margin-bottom:8px">
            Plan Seç
        </div>
        <div style="font-size:13px;color:#6b7280">
            Test kartı: <code>4242 4242 4242 4242</code> — Herhangi bir tarih ve CVC
        </div>
    </div>
    """, unsafe_allow_html=True)

    # URL'den ödeme sonucu kontrol et
    params = st.query_params
    if params.get("payment") == "success":
        plan = params.get("plan", "starter")
        db.update_plan(user["email"], plan)
        st.session_state.user["plan"] = plan
        st.success(f"✅ Ödeme başarılı! {PLANS[plan].name} planına geçildi.")
        st.query_params.clear()
    elif params.get("payment") == "cancelled":
        st.warning("Ödeme iptal edildi.")
        st.query_params.clear()

    cols = st.columns(3)
    plan_list = [
        ("free",    "Ücretsiz", 0),
        ("starter", "Starter",  29),
        ("pro",     "Pro",      79),
    ]

    for col, (key, name, price) in zip(cols, plan_list):
        plan    = PLANS[key]
        current = user["plan"] == key
        border  = "#00e5b0" if current else "#1e2128"

        with col:
            st.markdown(f"""
            <div style="background:#111318;border:2px solid {border};border-radius:12px;
                        padding:28px 24px;text-align:center;margin-bottom:12px">
                <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:800;margin-bottom:4px">
                    {name} {'· Mevcut' if current else ''}
                </div>
                <div style="font-size:36px;font-weight:800;
                            color:{'#00e5b0' if key=='pro' else '#e8eaf0'};margin:12px 0 4px">
                    €{price}
                </div>
                <div style="font-size:11px;color:#6b7280;margin-bottom:20px">/ ay</div>
                <div style="text-align:left;font-size:13px;line-height:2.2">
                    ✅ Max {plan.max_stores} mağaza<br>
                    ✅ {plan.max_orders:,} sipariş/ay<br>
                    {'✅' if plan.ai_reports else '🔒'} AI Analiz<br>
                    {'✅' if plan.pdf_export else '🔒'} PDF Rapor<br>
                    {'✅' if plan.meta_ads   else '🔒'} Meta Ads<br>
                    ✅ {plan.support} Destek
                </div>
            </div>
            """, unsafe_allow_html=True)

            if current:
                st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
                if key != "free":
                    st.markdown(f"""
                    <div style="text-align:center;font-size:11px;color:#6b7280">
                        Aktif plan
                    </div>
                    """, unsafe_allow_html=True)

            elif key == "free":
                if st.button("Ücretsiz'e Geç", key="switch_free", use_container_width=True):
                    db.update_plan(user["email"], "free")
                    st.session_state.user["plan"] = "free"
                    st.success("Ücretsiz plana geçildi.")
                    import time; time.sleep(0.8)
                    st.rerun()

            else:
                # Stripe ödeme butonu
                if st.button(
                    f"{'⬆' if key=='pro' else ''} {name}'e Geç — €{price}/ay",
                    key=f"pay_{key}",
                    use_container_width=True,
                ):
                    with st.spinner("Stripe ödeme sayfası hazırlanıyor..."):
                        result = create_checkout_session(
                            plan=key,
                            customer_email=user["email"],
                            success_url=f"http://localhost:8501/?payment=success&plan={key}",
                            cancel_url="http://localhost:8501/?payment=cancelled",
                        )

                    if result["success"]:
                        st.markdown(f"""
                        <div style="background:rgba(0,229,176,0.05);border:1px solid rgba(0,229,176,0.3);
                                    border-radius:8px;padding:16px 20px;margin-top:12px;text-align:center">
                            <div style="font-size:13px;color:#2c2a25;margin-bottom:10px">
                                Ödeme sayfası hazır!<br>
                                <span style="font-size:11px;color:#6b7280">
                                    Test kartı: 4242 4242 4242 4242
                                </span>
                            </div>
                            <a href="{result['checkout_url']}" target="_blank"
                               style="background:#00e5b0;color:#000;padding:10px 24px;
                                      border-radius:6px;text-decoration:none;font-weight:600;
                                      font-size:12px;letter-spacing:0.05em;text-transform:uppercase">
                                💳 Ödemeye Git →
                            </a>
                        </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.error(f"Stripe hatası: {result['error']}")

    st.divider()
    st.markdown("""
    <div style="text-align:center;font-size:12px;color:#6b7280">
        🔒 Ödemeler Stripe tarafından güvenli şekilde işlenir.<br>
        Kart bilgilerin hiçbir zaman sunucularımızda saklanmaz.
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ANA ROUTER
# ─────────────────────────────────────────────

if st.session_state.user is None:
    page_auth()
else:
    render_sidebar()
    page = st.session_state.app_page
    if   page == "home":     page_home()
    elif page == "connect":  page_connect()
    elif page == "analysis": page_analysis()
    elif page == "pricing":  page_pricing()
