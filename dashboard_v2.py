"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 5: Müşteri Onboarding Akışlı Dashboard

Çalıştır:
streamlit run dashboard_v2.py
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
    page_title="OPS Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig
from ai_engine import AIConfig, run_full_analysis
from meta_ads import MetaConfig, run_meta_analysis
from onboarding import (
    test_shopify_connection, test_meta_connection,
    SHOPIFY_GUIDE, META_GUIDE
)
from pdf_report import generate_pdf_report

# ─────────────────────────────────────────────
# STİL
# ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

:root {
    --bg: #0a0c0f; --surface: #111318; --border: #1e2128;
    --accent: #00e5b0; --accent2: #ff6b35; --warn: #f5a623;
    --danger: #ff3b5c; --text: #e8eaf0; --muted: #6b7280;
}
html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
    background-color: var(--bg);
    color: var(--text);
}
h1,h2,h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.02em; }

/* Input alanları */
.stTextInput > div > div > input {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 6px !important;
    color: var(--text) !important;
    font-family: 'DM Mono', monospace !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
}
.stTextInput > div > div > input:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 2px rgba(0,229,176,0.15) !important;
}

/* Butonlar */
.stButton > button {
    background: var(--accent) !important;
    color: #000 !important;
    border: none !important;
    border-radius: 6px !important;
    font-family: 'DM Mono', monospace !important;
    font-weight: 500 !important;
    letter-spacing: 0.05em !important;
    text-transform: uppercase !important;
    font-size: 12px !important;
    padding: 10px 24px !important;
    transition: all 0.2s !important;
}
.stButton > button:hover {
    background: #00ffcc !important;
    transform: translateY(-1px);
    box-shadow: 0 4px 20px rgba(0,229,176,0.3) !important;
}

/* Metrik kartları */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    position: relative; overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: ''; position: absolute; top: 0; left: 0;
    width: 3px; height: 100%; background: var(--accent);
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 11px !important; letter-spacing: 0.1em; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'Syne', sans-serif !important; font-size: 26px !important; }

/* Toggle */
.stToggle { accent-color: var(--accent); }

/* Divider */
hr { border-color: var(--border) !important; }
.block-container { padding-top: 2rem !important; max-width: 1200px; }

/* Adım indikatörü */
.step-bar {
    display: flex; gap: 0; margin-bottom: 40px;
}
.step-item {
    flex: 1; padding: 12px 0; text-align: center;
    font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
    border-bottom: 2px solid var(--border); color: var(--muted);
    transition: all 0.3s;
}
.step-item.active {
    border-bottom-color: var(--accent); color: var(--accent);
    font-weight: 600;
}
.step-item.done {
    border-bottom-color: var(--accent); color: var(--muted);
}

/* Bağlantı kartı */
.conn-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 28px 32px;
    margin-bottom: 16px;
}
.conn-card.success { border-color: rgba(0,229,176,0.4); background: rgba(0,229,176,0.03); }
.conn-card.error   { border-color: rgba(255,59,92,0.4);  background: rgba(255,59,92,0.03); }

/* Sağlık skoru */
.health-box {
    background: linear-gradient(135deg, #111318 0%, #0d1117 100%);
    border: 1px solid var(--border); border-radius: 12px;
    padding: 28px 32px; text-align: center; position: relative; overflow: hidden;
}
.health-box::after {
    content: ''; position: absolute; bottom: 0; left: 0; right: 0;
    height: 3px; background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.score-num {
    font-family: 'Syne', sans-serif; font-size: 72px; font-weight: 800;
    line-height: 1; letter-spacing: -4px;
}

/* Bulgu kartları */
.finding-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 16px 20px; margin-bottom: 10px;
    border-left: 3px solid; transition: transform 0.15s;
}
.finding-card:hover { transform: translateX(4px); }
.finding-critical { border-left-color: #ff3b5c; }
.finding-warning  { border-left-color: #f5a623; }
.finding-ok       { border-left-color: #00e5b0; }
.tag {
    display: inline-block; padding: 2px 8px; border-radius: 4px;
    font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 500;
}
.tag-critical { background: rgba(255,59,92,0.15); color: #ff3b5c; border: 1px solid rgba(255,59,92,0.3); }
.tag-warning  { background: rgba(245,166,35,0.15); color: #f5a623; border: 1px solid rgba(245,166,35,0.3); }
.tag-ok       { background: rgba(0,229,176,0.1);  color: #00e5b0; border: 1px solid rgba(0,229,176,0.25); }
.finding-rec {
    font-size: 12px; margin-top: 8px; padding: 8px 12px;
    background: rgba(0,229,176,0.05); border-radius: 4px;
    border-left: 2px solid #00e5b0;
}
.qw-item {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 12px 16px; margin-bottom: 8px;
    display: flex; align-items: flex-start; gap: 12px;
    font-size: 13px; line-height: 1.5;
}
.qw-num {
    font-family: 'Syne', sans-serif; font-size: 20px; font-weight: 800;
    color: #00e5b0; min-width: 28px; line-height: 1;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# YARDIMCILAR
# ─────────────────────────────────────────────

def score_color(s):
    return "#00e5b0" if s >= 75 else "#f5a623" if s >= 50 else "#ff3b5c"

def plotly_theme():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono, monospace", color="#6b7280", size=11),
        xaxis=dict(gridcolor="#1e2128", linecolor="#1e2128"),
        yaxis=dict(gridcolor="#1e2128", linecolor="#1e2128"),
        margin=dict(l=0, r=0, t=30, b=0),
    )

def step_bar(current: int):
    steps = ["1  Shopify", "2  Meta Ads", "3  Analiz", "4  Sonuçlar"]
    html = '<div class="step-bar">'
    for i, s in enumerate(steps, 1):
        cls = "active" if i == current else "done" if i < current else "step-item"
        if i == current: cls = "step-item active"
        elif i < current: cls = "step-item done"
        else: cls = "step-item"
        html += f'<div class="{cls}">{s}</div>'
    html += '</div>'
    st.markdown(html, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE BAŞLAT
# ─────────────────────────────────────────────

defaults = {
    "page": "onboarding",        # onboarding | dashboard
    "step": 1,                   # onboarding adımı (1-4)
    "shopify_ok": False,
    "meta_ok": False,
    "shopify_cfg": None,
    "meta_cfg": None,
    "use_mock_shopify": True,
    "use_mock_meta": True,
    "shop_name": "",
    "ad_account": "",
    "result": None,
    "meta_result": None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ─────────────────────────────────────────────
# SAYFA: ONBOARDING
# ─────────────────────────────────────────────

def page_onboarding():

    # Logo
    st.markdown("""
    <div style="text-align:center;padding:20px 0 32px">
        <div style="font-family:'Syne',sans-serif;font-size:40px;font-weight:800;
                    letter-spacing:-2px;margin-bottom:6px">
            OPS<span style="color:#00e5b0">·</span>INTELLIGENCE
        </div>
        <div style="font-size:11px;color:#6b7280;letter-spacing:0.15em;text-transform:uppercase">
            E-Ticaret Operasyonel Analiz Platformu
        </div>
    </div>
    """, unsafe_allow_html=True)

    step_bar(st.session_state.step)

    # ══ ADIM 1: SHOPIFY ══════════════════════════
    if st.session_state.step == 1:
        st.markdown("""
        <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:700;margin-bottom:6px">
            Shopify Mağazanı Bağla
        </div>
        <div style="font-size:13px;color:#6b7280;margin-bottom:28px">
            Sipariş, ürün ve stok verilerini çekmek için Shopify bağlantısı gerekli.
        </div>
        """, unsafe_allow_html=True)

        # Demo / Gerçek seçimi
        mode = st.radio(
            "Bağlantı modu:",
            ["🎮  Demo (gerçek veri gerekmez)", "🔗  Gerçek Shopify Mağazası"],
            horizontal=True,
        )

        if "Demo" in mode:
            st.markdown("""
            <div style="background:rgba(0,229,176,0.05);border:1px solid rgba(0,229,176,0.2);
                        border-radius:8px;padding:16px 20px;margin:16px 0;font-size:13px;color:#9ca3b0">
                Demo modunda sistem 200 adet gerçekçi sipariş verisi üretir.<br>
                API bağlantısı gerekmez — hemen analiz başlatabilirsin.
            </div>
            """, unsafe_allow_html=True)

            if st.button("Demo ile Devam Et →", use_container_width=True):
                st.session_state.use_mock_shopify = True
                st.session_state.shopify_cfg = ShopifyConfig(use_mock=True, mock_order_count=200)
                st.session_state.shopify_ok = True
                st.session_state.shop_name = "Demo Mağaza"
                st.session_state.step = 2
                st.rerun()

        else:
            with st.expander("📖 Access Token Nasıl Alınır?"):
                st.markdown(SHOPIFY_GUIDE)

            col1, col2 = st.columns(2)
            with col1:
                shop_domain = st.text_input(
                    "Shopify Domain",
                    placeholder="magazaadın.myshopify.com",
                    help="myshopify.com ile biten adresin"
                )
            with col2:
                access_token = st.text_input(
                    "Admin API Access Token",
                    type="password",
                    placeholder="shpat_xxxxxxxxxxxxxxxxxxxxxxxx",
                )

            order_limit = st.slider("Çekilecek sipariş sayısı", 50, 500, 250, 50)

            if st.button("Bağlantıyı Test Et →", use_container_width=True):
                if not shop_domain or not access_token:
                    st.error("Domain ve Access Token alanlarını doldur.")
                else:
                    with st.spinner("Shopify'a bağlanılıyor..."):
                        result = test_shopify_connection(shop_domain, access_token)

                    if result.success:
                        st.markdown(f"""
                        <div class="conn-card success">
                            <div style="font-size:16px;font-weight:600;color:#00e5b0;margin-bottom:8px">
                                ✅ Bağlantı Başarılı!
                            </div>
                            <div style="font-size:13px;color:#9ca3b0">
                                Mağaza: <strong style="color:#e8eaf0">{result.shop_name}</strong><br>
                                Toplam Sipariş: <strong style="color:#e8eaf0">{result.order_count:,}</strong>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.session_state.use_mock_shopify = False
                        st.session_state.shopify_cfg = ShopifyConfig(
                            shop_domain=shop_domain,
                            access_token=access_token,
                            use_mock=False,
                            mock_order_count=order_limit,
                        )
                        st.session_state.shopify_ok = True
                        st.session_state.shop_name = result.shop_name

                        import time; time.sleep(1.5)
                        st.session_state.step = 2
                        st.rerun()
                    else:
                        st.markdown(f"""
                        <div class="conn-card error">
                            <div style="font-size:15px;font-weight:600;color:#ff3b5c;margin-bottom:8px">
                                {result.message}
                            </div>
                            <div style="font-size:12px;color:#6b7280">{result.detail}</div>
                        </div>
                        """, unsafe_allow_html=True)

    # ══ ADIM 2: META ADS ═════════════════════════
    elif st.session_state.step == 2:
        st.markdown(f"""
        <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:700;margin-bottom:6px">
            Meta Ads Hesabını Bağla
        </div>
        <div style="font-size:13px;color:#6b7280;margin-bottom:28px">
            Reklam harcaması, ROAS ve çapraz alarm analizi için gerekli. Atlanabilir.
        </div>
        """, unsafe_allow_html=True)

        mode = st.radio(
            "Bağlantı modu:",
            ["🎮  Demo (simüle reklam verisi)", "🔗  Gerçek Meta Ads Hesabı", "⏭️  Atla"],
            horizontal=True,
        )

        if "Demo" in mode:
            if st.button("Demo ile Devam Et →", use_container_width=True):
                st.session_state.use_mock_meta = True
                st.session_state.meta_cfg = MetaConfig(use_mock=True)
                st.session_state.meta_ok = True
                st.session_state.step = 3
                st.rerun()

        elif "Atla" in mode:
            if st.button("Meta Ads'i Atla →", use_container_width=True):
                st.session_state.meta_cfg = None
                st.session_state.meta_ok = False
                st.session_state.step = 3
                st.rerun()

        else:
            with st.expander("📖 Meta Access Token Nasıl Alınır?"):
                st.markdown(META_GUIDE)

            col1, col2 = st.columns(2)
            with col1:
                meta_token = st.text_input(
                    "Meta Access Token",
                    type="password",
                    placeholder="EAAxxxxxxxxxx...",
                )
            with col2:
                meta_account = st.text_input(
                    "Ad Account ID",
                    placeholder="act_123456789",
                )

            if st.button("Bağlantıyı Test Et →", use_container_width=True):
                if not meta_token:
                    st.error("Access Token alanını doldur.")
                else:
                    with st.spinner("Meta Ads'e bağlanılıyor..."):
                        result = test_meta_connection(meta_token, meta_account)

                    if result.success:
                        st.markdown(f"""
                        <div class="conn-card success">
                            <div style="font-size:16px;font-weight:600;color:#00e5b0;margin-bottom:8px">
                                ✅ Bağlantı Başarılı!
                            </div>
                            <div style="font-size:13px;color:#9ca3b0">
                                Hesap: <strong style="color:#e8eaf0">{result.ad_account or 'Doğrulandı'}</strong><br>
                                <span style="font-size:11px">{result.detail}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.session_state.use_mock_meta = False
                        st.session_state.meta_cfg = MetaConfig(
                            access_token=meta_token,
                            ad_account_id=meta_account,
                            use_mock=False,
                        )
                        st.session_state.meta_ok = True

                        import time; time.sleep(1.5)
                        st.session_state.step = 3
                        st.rerun()
                    else:
                        st.markdown(f"""
                        <div class="conn-card error">
                            <div style="font-size:15px;font-weight:600;color:#ff3b5c;margin-bottom:8px">
                                {result.message}
                            </div>
                            <div style="font-size:12px;color:#6b7280">{result.detail}</div>
                        </div>
                        """, unsafe_allow_html=True)

        # Geri butonu
        if st.button("← Geri"):
            st.session_state.step = 1
            st.rerun()

    # ══ ADIM 3: ONAY + BAŞLAT ════════════════════
    elif st.session_state.step == 3:
        st.markdown("""
        <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:700;margin-bottom:24px">
            Analizi Başlat
        </div>
        """, unsafe_allow_html=True)

        # Bağlantı özeti
        s_color = "#00e5b0" if st.session_state.shopify_ok else "#ff3b5c"
        m_color = "#00e5b0" if st.session_state.meta_ok else "#6b7280"
        m_label = "Bağlı" if st.session_state.meta_ok else "Atlandı"
        mock_s  = " (Demo)" if st.session_state.use_mock_shopify else ""
        mock_m  = " (Demo)" if st.session_state.use_mock_meta else ""

        st.markdown(f"""
        <div style="background:var(--surface);border:1px solid var(--border);
                    border-radius:10px;padding:24px 28px;margin-bottom:24px">
            <div style="font-size:12px;color:#6b7280;letter-spacing:0.1em;
                        text-transform:uppercase;margin-bottom:16px">Bağlantı Özeti</div>
            <div style="display:flex;gap:32px;flex-wrap:wrap">
                <div>
                    <div style="font-size:10px;color:#6b7280;margin-bottom:4px">SHOPIFY</div>
                    <div style="color:{s_color};font-weight:600">
                        ✅ {st.session_state.shop_name}{mock_s}
                    </div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;margin-bottom:4px">META ADS</div>
                    <div style="color:{m_color};font-weight:600">
                        {'✅' if st.session_state.meta_ok else '—'} {m_label}{mock_m}
                    </div>
                </div>
                <div>
                    <div style="font-size:10px;color:#6b7280;margin-bottom:4px">AI MOTORu</div>
                    <div style="color:#00e5b0;font-weight:600">✅ Mock GPT-4o (Demo)</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # AI seçenekleri
        with st.expander("⚙️ AI Ayarları (opsiyonel)"):
            use_real_ai = st.toggle("Gerçek OpenAI API kullan", value=False)
            if use_real_ai:
                ai_key   = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
                ai_model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o"])
            else:
                ai_key, ai_model = "", "gpt-4o-mini"
            lang = st.selectbox("Analiz Dili", ["Türkçe (tr)", "İngilizce (en)"])
            lang_code = "tr" if "tr" in lang else "en"

        col_back, col_run = st.columns([1, 3])
        with col_back:
            if st.button("← Geri"):
                st.session_state.step = 2
                st.rerun()
        with col_run:
            if st.button("▶  ANALİZİ BAŞLAT", use_container_width=True):
                progress = st.progress(0, text="Shopify verisi çekiliyor...")

                ai_cfg = AIConfig(
                    api_key=ai_key if use_real_ai else "",
                    model=ai_model,
                    language=lang_code,
                    use_mock_ai=not use_real_ai,
                )

                progress.progress(25, text="Veri işleniyor...")
                st.session_state.result = run_full_analysis(
                    st.session_state.shopify_cfg, ai_cfg
                )

                progress.progress(60, text="AI analizi yapılıyor...")

                if st.session_state.meta_cfg is not None:
                    products_df = st.session_state.result.get("products_df")
                    st.session_state.meta_result = run_meta_analysis(
                        st.session_state.meta_cfg, products_df
                    )

                progress.progress(100, text="Tamamlandı!")
                import time; time.sleep(0.8)

                st.session_state.page = "dashboard"
                st.rerun()


# ─────────────────────────────────────────────
# SAYFA: DASHBOARD
# ─────────────────────────────────────────────

def page_dashboard():
    result      = st.session_state.result
    meta_result = st.session_state.meta_result
    analysis    = result["analysis"]
    metrics     = result.get("metrics", {})
    orders_df   = result.get("orders_df", pd.DataFrame())
    products_df = result.get("products_df", pd.DataFrame())
    ft  = metrics.get("fulfillment_time", {})
    rev = metrics.get("revenue", {})
    inv = metrics.get("inventory", {})

    # ── Üst bar
    c_logo, c_shop, c_reset = st.columns([3, 4, 1])
    with c_logo:
        st.markdown("""
        <div style="font-family:'Syne',sans-serif;font-size:22px;font-weight:800;
                    letter-spacing:-1px">
            OPS<span style="color:#00e5b0">·</span>INTELLIGENCE
        </div>
        """, unsafe_allow_html=True)
    with c_shop:
        mock_label = " · Demo Veri" if st.session_state.use_mock_shopify else ""
        st.markdown(f"""
        <div style="font-size:11px;color:#6b7280;padding-top:8px;letter-spacing:0.08em">
            {st.session_state.shop_name}{mock_label} &nbsp;|&nbsp;
            {result.get('generated_at','')[:19].replace('T',' ')} &nbsp;|&nbsp;
            {ft.get('total_fulfilled',0)} sipariş
        </div>
        """, unsafe_allow_html=True)
    with c_reset:
        if st.button("↩ Yeni Analiz"):
            for k in ["page","step","shopify_ok","meta_ok","result","meta_result"]:
                st.session_state[k] = defaults[k]
            st.rerun()

    st.divider()

    # ── KPI Satırı
    score = analysis["overall_health_score"]
    sc    = score_color(score)
    c1, c2, c3, c4, c5 = st.columns([1.4, 1, 1, 1, 1])

    with c1:
        st.markdown(f"""
        <div class="health-box">
            <div style="font-size:10px;color:#6b7280;letter-spacing:0.12em;text-transform:uppercase">
                Operasyonel Sağlık
            </div>
            <div class="score-num" style="color:{sc};margin:8px 0 4px">{score}</div>
            <div style="font-size:12px;color:{sc};letter-spacing:0.08em">
                {analysis['overall_health_label']}
            </div>
            <div style="width:100%;background:#1e2128;height:3px;border-radius:2px;margin-top:14px">
                <div style="width:{score}%;background:{sc};height:3px;border-radius:2px"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.metric("Ort. Fulfillment", f"{ft.get('mean',0)}s",
                  f"Medyan {ft.get('median',0)}s", delta_color="off")
    with c3:
        st.metric("Toplam Gelir", f"€{rev.get('total_revenue',0):,.0f}",
                  f"{rev.get('total_orders',0)} sipariş")
    with c4:
        st.metric("Ort. Sepet", f"€{rev.get('aov',0):.0f}",
                  "↑ Hedef €250")
    with c5:
        st.metric("İptal Oranı", f"%{rev.get('cancellation_rate',0)}",
                  "Hedef <%2.5", delta_color="inverse")

    st.divider()

    # ── Sekmeler
    tabs = ["📋  Bulgular", "📈  Gelir", "📦  Stok", "⚡  Aksiyonlar"]
    if meta_result:
        tabs.append("📣  Meta Ads")
    tab_objs = st.tabs(tabs)

    # ─ TAB 1: BULGULAR
    with tab_objs[0]:
        st.markdown(f"""
        <div style="background:#111318;border:1px solid #1e2128;border-radius:8px;
                    padding:16px 20px;margin-bottom:20px;font-size:13px;
                    line-height:1.7;color:#9ca3b0">
            <span style="font-family:'Syne',sans-serif;color:#e8eaf0;font-weight:600">
            Yönetici Özeti —</span> {analysis['executive_summary']}
        </div>
        """, unsafe_allow_html=True)

        for f in sorted(analysis["findings"], key=lambda x: x["priority"]):
            sev  = f["severity"]
            icon = {"critical":"🔴","warning":"⚠️","ok":"✅"}[sev]
            pri  = {1:"ACİL",2:"Yüksek",3:"Orta",4:"Düşük",5:"İzle"}[f["priority"]]
            pc   = "red" if f["priority"]==1 else "yellow" if f["priority"]<=3 else "green"

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
            </div>
            """, unsafe_allow_html=True)

    # ─ TAB 2: GELİR
    with tab_objs[1]:
        if not orders_df.empty:
            valid = orders_df[~orders_df["fulfillment_status"].isin(["cancelled","refunded"])].copy()
            valid["date"] = pd.to_datetime(valid["created_at"]).dt.date
            daily = valid.groupby("date")["total_price"].sum().reset_index()
            daily["ma7"] = daily["total_price"].rolling(7, min_periods=1).mean()

            fig = go.Figure()
            fig.add_trace(go.Bar(x=daily["date"], y=daily["total_price"],
                                 name="Günlük €",
                                 marker_color="rgba(0,229,176,0.25)",
                                 marker_line_color="rgba(0,229,176,0.6)",
                                 marker_line_width=1))
            fig.add_trace(go.Scatter(x=daily["date"], y=daily["ma7"],
                                     name="7g Ortalama",
                                     line=dict(color="#ff6b35", width=2)))
            fig.update_layout(title="Günlük Gelir (€)",
                              legend=dict(orientation="h", y=1.1),
                              **plotly_theme())
            st.plotly_chart(fig, use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                sc2 = orders_df["fulfillment_status"].value_counts().reset_index()
                colors = {"fulfilled":"#00e5b0","unfulfilled":"#f5a623",
                          "cancelled":"#ff3b5c","refunded":"#ff6b35"}
                fig2 = go.Figure(go.Pie(
                    labels=sc2["fulfillment_status"],
                    values=sc2["count"], hole=0.55,
                    marker=dict(colors=[colors.get(s,"#6b7280") for s in sc2["fulfillment_status"]],
                                line=dict(color="#0a0c0f", width=2)),
                ))
                fig2.update_layout(title="Sipariş Dağılımı", **plotly_theme())
                st.plotly_chart(fig2, use_container_width=True)

            with g2:
                fulfilled = orders_df[(orders_df["fulfillment_status"]=="fulfilled") &
                                      (orders_df["fulfilled_at"].notna())].copy()
                fulfilled["fh"] = (
                    pd.to_datetime(fulfilled["fulfilled_at"]) -
                    pd.to_datetime(fulfilled["created_at"])
                ).dt.total_seconds() / 3600
                fig3 = go.Figure(go.Histogram(x=fulfilled["fh"].clip(0,120), nbinsx=25,
                                              marker_color="rgba(0,229,176,0.4)",
                                              marker_line_color="rgba(0,229,176,0.8)",
                                              marker_line_width=1))
                fig3.add_vline(x=24, line_dash="dash", line_color="#f5a623",
                               annotation_text="24s")
                fig3.add_vline(x=48, line_dash="dash", line_color="#ff3b5c",
                               annotation_text="48s")
                fig3.update_layout(title="Fulfillment Süresi Dağılımı", **plotly_theme())
                st.plotly_chart(fig3, use_container_width=True)

    # ─ TAB 3: STOK
    with tab_objs[2]:
        if not products_df.empty:
            inv_df = products_df[["title","category","inventory","price","margin_pct"]].copy()
            inv_df["durum"] = inv_df["inventory"].apply(
                lambda v: "🔴 TÜKENDİ" if v==0 else "🔴 KRİTİK" if v<10 else "⚠️ DÜŞÜK" if v<30 else "✅ NORMAL"
            )
            inv_df.columns = ["Ürün","Kategori","Stok","Fiyat €","Margin %","Durum"]
            st.dataframe(
                pd.concat([inv_df[inv_df["Stok"]<30], inv_df[inv_df["Stok"]>=30]]).reset_index(drop=True),
                use_container_width=True, hide_index=True,
                column_config={
                    "Stok": st.column_config.ProgressColumn("Stok", max_value=200, format="%d"),
                    "Margin %": st.column_config.NumberColumn(format="%.1f%%"),
                }
            )

    # ─ TAB 4: AKSİYONLAR
    with tab_objs[3]:
        st.markdown("""<div style="font-family:'Syne',sans-serif;font-size:18px;
                    font-weight:700;margin-bottom:16px">Bu Hafta Yapılacaklar</div>""",
                    unsafe_allow_html=True)
        for i, qw in enumerate(analysis.get("quick_wins",[]), 1):
            st.markdown(f"""
            <div class="qw-item">
                <div class="qw-num">{i:02d}</div>
                <div>{qw}</div>
            </div>""", unsafe_allow_html=True)

        kpi = analysis.get("kpi_targets", {})
        st.divider()
        k1, k2, k3 = st.columns(3)
        k1.metric("Fulfillment Hedefi", f"{kpi.get('fulfillment_target_hours',24)}s",
                  f"Şu an: {ft.get('median',0)}s")
        k2.metric("Yeniden Sipariş", f"{kpi.get('inventory_reorder_point',30)} adet")
        k3.metric("Maks İptal", f"%{kpi.get('target_cancellation_rate_pct',2.5)}")

        # Rapor İndirme
        st.divider()
        dl1, dl2 = st.columns(2)
        with dl1:
            with st.spinner("PDF hazırlanıyor..."):
                pdf_bytes = generate_pdf_report(
                    result,
                    meta_result,
                    st.session_state.shop_name,
                )
            st.download_button(
                "⬇  PDF Rapor İndir",
                data=pdf_bytes,
                file_name=f"ops_raporu_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        with dl2:
            export = {k: v for k, v in result.items() if k not in ("orders_df","products_df")}
            st.download_button(
                "⬇  JSON Veri İndir",
                data=json.dumps(export, ensure_ascii=False, indent=2, default=str),
                file_name=f"ops_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )

    # ─ TAB 5: META ADS
    if meta_result and len(tab_objs) > 4:
        with tab_objs[4]:
            ra = meta_result["roas_analysis"]
            mc1,mc2,mc3,mc4 = st.columns(4)
            mc1.metric("Toplam Harcama", f"€{ra['total_spend']:,.0f}")
            mc2.metric("Toplam Gelir",   f"€{ra['total_revenue']:,.0f}")
            mc3.metric("Blended ROAS",   f"{ra['blended_roas']}x", "Hedef 3.0x")
            mc4.metric("Kritik Kampanya",f"{ra['bad_campaigns']}", delta_color="inverse")

            st.divider()
            camp_df = meta_result["campaign_summary"][
                ["campaign_name","spend","revenue","roas","cpc","purchases","durum"]
            ].copy()
            camp_df.columns = ["Kampanya","Harcama €","Gelir €","ROAS","CPC €","Satış","Durum"]
            st.dataframe(camp_df, use_container_width=True, hide_index=True,
                         column_config={
                             "ROAS": st.column_config.ProgressColumn("ROAS", max_value=5, format="%.2fx"),
                         })

            daily = meta_result["daily_trends"]
            fig_m = go.Figure()
            fig_m.add_trace(go.Bar(x=daily["date"], y=daily["spend"], name="Harcama €",
                                   marker_color="rgba(255,107,53,0.3)",
                                   marker_line_color="rgba(255,107,53,0.7)",
                                   marker_line_width=1))
            fig_m.add_trace(go.Scatter(x=daily["date"], y=daily["revenue"],
                                       name="Gelir €", line=dict(color="#00e5b0", width=2)))
            fig_m.update_layout(title="Reklam Harcaması vs Gelir",
                                legend=dict(orientation="h", y=1.1), **plotly_theme())
            st.plotly_chart(fig_m, use_container_width=True)

            alarms = meta_result["cross_alarms"]
            st.divider()
            st.markdown(f"""<div style="font-family:'Syne',sans-serif;font-size:18px;
                        font-weight:700;margin-bottom:16px">
                🚨 Çapraz Alarmlar
                <span style="font-size:12px;font-weight:400;color:#6b7280;margin-left:10px">
                    {sum(1 for a in alarms if a['severity']=='critical')} kritik ·
                    {sum(1 for a in alarms if a['severity']=='warning')} uyarı
                </span></div>""", unsafe_allow_html=True)

            if not alarms:
                st.success("✅ Aktif alarm yok.")
            else:
                for a in alarms:
                    border = "#ff3b5c" if a["severity"]=="critical" else "#f5a623"
                    bg     = "rgba(255,59,92,0.04)" if a["severity"]=="critical" else "rgba(245,166,35,0.04)"
                    icon   = "🔴" if a["severity"]=="critical" else "⚠️"
                    waste  = f"<div style='font-size:11px;color:#ff3b5c;margin-top:8px'>💸 Tahmini israf: €{a['estimated_waste_eur']:.0f}</div>" if a.get("estimated_waste_eur") else ""
                    st.markdown(f"""
                    <div style="background:{bg};border:1px solid {border};border-left:3px solid {border};
                                border-radius:8px;padding:16px 20px;margin-bottom:12px">
                        <div style="font-family:'Syne',sans-serif;font-size:15px;
                                    font-weight:600;margin-bottom:8px">{icon} {a['title']}</div>
                        <div style="font-size:12px;color:#9ca3b0;line-height:1.6">{a['description']}</div>
                        <div style="font-size:12px;margin-top:10px;padding:8px 12px;
                                    background:rgba(0,229,176,0.05);border-radius:4px;
                                    border-left:2px solid #00e5b0">
                            <span style="color:#00e5b0;font-size:10px;text-transform:uppercase">Aksiyon →</span><br>
                            {a['action']}
                        </div>{waste}
                    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# ROUTER
# ─────────────────────────────────────────────

if st.session_state.page == "onboarding":
    page_onboarding()
else:
    page_dashboard()
