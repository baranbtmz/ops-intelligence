"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 3: Streamlit Dashboard

Kurulum:
pip install streamlit plotly --break-system-packages

Çalıştır:
streamlit run dashboard.py
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import json
import sys
import os
from datetime import datetime, timedelta

# ── Sayfa ayarları (EN ÜSTTE olmalı)
st.set_page_config(
    page_title="Aurellia OPS Intelligence",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Adım 1, 2 & 4 modüllerini içe aktar
sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig
from ai_engine import AIConfig, run_full_analysis
from meta_ads import MetaConfig, run_meta_analysis

# ─────────────────────────────────────────────
# GLOBAL STİL
# ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap');

:root {
    --bg:       #0a0c0f;
    --surface:  #111318;
    --border:   #1e2128;
    --accent:   #00e5b0;
    --accent2:  #ff6b35;
    --warn:     #f5a623;
    --danger:   #ff3b5c;
    --text:     #e8eaf0;
    --muted:    #6b7280;
}

html, body, [class*="css"] {
    font-family: 'DM Mono', monospace;
    background-color: var(--bg);
    color: var(--text);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--border);
}

/* Metrik kartları */
[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetric"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0;
    width: 3px; height: 100%;
    background: var(--accent);
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 11px !important; letter-spacing: 0.1em; text-transform: uppercase; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'Syne', sans-serif !important; font-size: 28px !important; }
[data-testid="stMetricDelta"] > div { font-size: 12px !important; }

/* Başlıklar */
h1, h2, h3 { font-family: 'Syne', sans-serif !important; letter-spacing: -0.02em; }

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

/* Divider */
hr { border-color: var(--border) !important; }

/* Expander */
details { background: var(--surface) !important; border: 1px solid var(--border) !important; border-radius: 8px !important; }

/* Genel container */
.block-container { padding-top: 2rem !important; }

/* Sağlık skoru kutusu */
.health-box {
    background: linear-gradient(135deg, #111318 0%, #0d1117 100%);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 28px 32px;
    text-align: center;
    position: relative;
    overflow: hidden;
}
.health-box::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, var(--accent), var(--accent2));
}
.score-num {
    font-family: 'Syne', sans-serif;
    font-size: 72px;
    font-weight: 800;
    line-height: 1;
    letter-spacing: -4px;
}
.score-label {
    font-family: 'DM Mono', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: var(--muted);
    margin-top: 6px;
}

/* Bulgu kartları */
.finding-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 10px;
    border-left: 3px solid;
    transition: transform 0.15s;
}
.finding-card:hover { transform: translateX(4px); }
.finding-critical { border-left-color: var(--danger); }
.finding-warning  { border-left-color: var(--warn); }
.finding-ok       { border-left-color: var(--accent); }

.tag {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    font-weight: 500;
}
.tag-critical { background: rgba(255,59,92,0.15); color: var(--danger); border: 1px solid rgba(255,59,92,0.3); }
.tag-warning  { background: rgba(245,166,35,0.15); color: var(--warn);   border: 1px solid rgba(245,166,35,0.3); }
.tag-ok       { background: rgba(0,229,176,0.1);  color: var(--accent); border: 1px solid rgba(0,229,176,0.25); }

.finding-title { font-family: 'Syne', sans-serif; font-size: 15px; font-weight: 600; margin: 8px 0 4px; }
.finding-meta  { font-size: 11px; color: var(--muted); margin-bottom: 8px; }
.finding-body  { font-size: 12px; line-height: 1.6; color: #9ca3b0; }
.finding-rec   { font-size: 12px; margin-top: 8px; padding: 8px 12px;
                 background: rgba(0,229,176,0.05); border-radius: 4px;
                 border-left: 2px solid var(--accent); }

/* Quick wins */
.qw-item {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 16px;
    margin-bottom: 8px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    font-size: 13px;
    line-height: 1.5;
}
.qw-num {
    font-family: 'Syne', sans-serif;
    font-size: 20px;
    font-weight: 800;
    color: var(--accent);
    min-width: 28px;
    line-height: 1;
}

/* Stok uyarı badge */
.inv-badge {
    padding: 4px 10px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 500;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# YARDIMCI FONKSİYONLAR
# ─────────────────────────────────────────────

def score_color(score: int) -> str:
    if score >= 75: return "#00e5b0"
    if score >= 50: return "#f5a623"
    return "#ff3b5c"

def plotly_theme() -> dict:
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Mono, monospace", color="#6b7280", size=11),
        xaxis=dict(gridcolor="#1e2128", linecolor="#1e2128", tickcolor="#1e2128"),
        yaxis=dict(gridcolor="#1e2128", linecolor="#1e2128", tickcolor="#1e2128"),
        margin=dict(l=0, r=0, t=30, b=0),
    )


# ─────────────────────────────────────────────
# SIDEBAR — KONTROL PANELİ
# ─────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⬡ OPS Intelligence")
    st.markdown("<span style='font-size:11px;color:#6b7280;letter-spacing:0.1em;text-transform:uppercase'>E-Ticaret Analiz Sistemi</span>", unsafe_allow_html=True)
    st.divider()

    st.markdown("**Veri Kaynağı**")
    use_mock = st.toggle("Mock Data (Test Modu)", value=True)
    mock_count = st.slider("Sipariş Sayısı", 50, 500, 200, 50, disabled=not use_mock)

    st.divider()
    st.markdown("**AI Motoru**")
    use_mock_ai = st.toggle("Mock AI (API key gereksiz)", value=True)

    if not use_mock_ai:
        api_key = st.text_input("OpenAI API Key", type="password", placeholder="sk-...")
        model = st.selectbox("Model", ["gpt-4o-mini", "gpt-4o"])
    else:
        api_key, model = "", "gpt-4o-mini"

    lang = st.selectbox("Analiz Dili", ["Türkçe (tr)", "İngilizce (en)"])
    lang_code = "tr" if "tr" in lang else "en"

    st.divider()
    st.markdown("**📣 Meta Ads**")
    use_mock_meta = st.toggle("Mock Meta Data", value=True)
    if not use_mock_meta:
        meta_token    = st.text_input("Access Token", type="password", placeholder="EAAxx...")
        meta_account  = st.text_input("Ad Account ID", placeholder="act_123456789")
    else:
        meta_token, meta_account = "", ""

    st.divider()
    run_btn = st.button("▶  ANALİZİ ÇALIŞTIR", use_container_width=True)

    st.divider()
    st.markdown("<span style='font-size:10px;color:#3a3f4a'>Adım 4 / Meta Ads Entegrasyonu<br>© 2025 Aurellia OPS</span>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE — ANALİZ ÇALIŞTIRMA
# ─────────────────────────────────────────────

if "result" not in st.session_state:
    st.session_state.result = None
if "meta_result" not in st.session_state:
    st.session_state.meta_result = None

if run_btn:
    with st.spinner("⚙️ Shopify + Meta Ads + AI analiz çalışıyor..."):
        shopify_cfg = ShopifyConfig(use_mock=use_mock, mock_order_count=mock_count)
        ai_cfg = AIConfig(
            api_key=api_key,
            model=model,
            language=lang_code,
            use_mock_ai=use_mock_ai,
        )
        st.session_state.result = run_full_analysis(shopify_cfg, ai_cfg)

        # Meta Ads analizi (ürün stok verisiyle birleşik)
        meta_cfg = MetaConfig(
            access_token=meta_token,
            ad_account_id=meta_account,
            use_mock=use_mock_meta,
        )
        products_df = st.session_state.result.get("products_df")
        st.session_state.meta_result = run_meta_analysis(meta_cfg, products_df)


# ─────────────────────────────────────────────
# ANA İÇERİK
# ─────────────────────────────────────────────

if st.session_state.result is None:
    # ── Karşılama Ekranı
    st.markdown("""
    <div style="text-align:center;padding:80px 0 60px">
        <div style="font-family:'Syne',sans-serif;font-size:56px;font-weight:800;
                    letter-spacing:-3px;line-height:1;margin-bottom:16px">
            OPS<span style="color:#00e5b0">·</span>INTELLIGENCE
        </div>
        <div style="font-size:13px;color:#6b7280;letter-spacing:0.15em;text-transform:uppercase;margin-bottom:48px">
            E-Ticaret Operasyonel Analiz & AI Karar Destek Sistemi
        </div>
        <div style="display:flex;justify-content:center;gap:40px;flex-wrap:wrap">
    """, unsafe_allow_html=True)

    for icon, label, desc in [
        ("⬡", "Veri Katmanı", "Shopify API + Mock"),
        ("◈", "AI Motor", "GPT-4o Analizi"),
        ("◎", "Dashboard", "Gerçek Zamanlı KPI"),
        ("◉", "Aksiyon", "Öncelikli Plan"),
    ]:
        st.markdown(f"""
        <div style="background:#111318;border:1px solid #1e2128;border-radius:10px;
                    padding:24px 32px;min-width:160px;text-align:center">
            <div style="font-size:28px;margin-bottom:8px">{icon}</div>
            <div style="font-family:'Syne',sans-serif;font-size:14px;font-weight:600">{label}</div>
            <div style="font-size:11px;color:#6b7280;margin-top:4px">{desc}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("</div></div>", unsafe_allow_html=True)
    st.info("← Sol panelden **ANALİZİ ÇALIŞTIR** butonuna bas")

else:
    result = st.session_state.result
    analysis = result["analysis"]
    metrics  = result.get("metrics", {})
    orders_df   = result.get("orders_df", pd.DataFrame())
    products_df = result.get("products_df", pd.DataFrame())

    if not result["success"]:
        st.error(f"❌ AI Analiz hatası: {result.get('error', 'Bilinmeyen hata')}")
        st.stop()

    ft  = metrics.get("fulfillment_time", {})
    inv = metrics.get("inventory", {})
    rev = metrics.get("revenue", {})

    # ── BAŞLIK SATIRI
    col_title, col_time = st.columns([4, 1])
    with col_title:
        st.markdown(f"""
        <div style="font-family:'Syne',sans-serif;font-size:28px;font-weight:800;
                    letter-spacing:-1px;margin-bottom:4px">
            OPS<span style="color:#00e5b0">·</span>INTELLIGENCE
        </div>
        <div style="font-size:11px;color:#6b7280;letter-spacing:0.1em;text-transform:uppercase">
            Son Analiz: {result.get('generated_at','')[:19].replace('T',' ')} &nbsp;|&nbsp;
            Model: {result.get('model','')} &nbsp;|&nbsp;
            {ft.get('total_fulfilled',0)} sipariş işlendi
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # ══════════════════════════════════════════
    # BÖLÜM 1 — SAĞLIK SKORU + KPI ÖZET
    # ══════════════════════════════════════════

    score = analysis["overall_health_score"]
    c1, c2, c3, c4, c5 = st.columns([1.4, 1, 1, 1, 1])

    with c1:
        sc = score_color(score)
        st.markdown(f"""
        <div class="health-box">
            <div class="score-label">Operasyonel Sağlık</div>
            <div class="score-num" style="color:{sc}">{score}</div>
            <div style="font-family:'DM Mono';font-size:12px;color:{sc};
                        margin-top:8px;letter-spacing:0.08em">
                {analysis['overall_health_label']}
            </div>
            <div style="width:100%;background:#1e2128;height:3px;
                        border-radius:2px;margin-top:16px">
                <div style="width:{score}%;background:{sc};height:3px;border-radius:2px"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

    with c2:
        st.metric("Ort. Fulfillment",
                  f"{ft.get('mean',0)}s",
                  f"Medyan {ft.get('median',0)}s",
                  delta_color="off")
    with c3:
        st.metric("Toplam Gelir",
                  f"€{rev.get('total_revenue',0):,.0f}",
                  f"{rev.get('total_orders',0)} sipariş")
    with c4:
        st.metric("Ortalama Sepet",
                  f"€{rev.get('aov',0):.0f}",
                  f"↑ Hedef €250",
                  delta_color="normal")
    with c5:
        cancel = rev.get('cancellation_rate', 0)
        st.metric("İptal Oranı",
                  f"%{cancel}",
                  f"Hedef <%2.5",
                  delta_color="inverse")

    st.divider()

    # ══════════════════════════════════════════
    # BÖLÜM 2 — TABS
    # ══════════════════════════════════════════

    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋  Bulgular & Aksiyon",
        "📈  Gelir Analizi",
        "📦  Stok & Ürünler",
        "⚡  Hızlı Kazanımlar",
        "📣  Meta Ads",
    ])

    # ─── TAB 1: BULGULAR
    with tab1:
        st.markdown(f"""
        <div style="background:#111318;border:1px solid #1e2128;border-radius:8px;
                    padding:16px 20px;margin-bottom:20px;font-size:13px;line-height:1.7;color:#9ca3b0">
            <span style="font-family:'Syne',sans-serif;color:#e8eaf0;font-weight:600">
            Yönetici Özeti —</span> {analysis['executive_summary']}
        </div>
        """, unsafe_allow_html=True)

        findings = sorted(analysis["findings"], key=lambda x: x["priority"])
        for f in findings:
            sev   = f["severity"]
            icon  = {"critical": "🔴", "warning": "⚠️", "ok": "✅"}[sev]
            pri   = {1:"ACİL",2:"Yüksek",3:"Orta",4:"Düşük",5:"İzle"}[f["priority"]]
            cls   = f"finding-{sev}"
            tcls  = f"tag-{sev}"
            efor  = f.get("estimated_effort","—")
            etki  = f.get("estimated_impact","—")

            st.markdown(f"""
            <div class="finding-card {cls}">
                <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
                    <span class="tag {tcls}">{icon} {pri}</span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">
                        {f['area']}
                    </span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">
                        Efor: {efor}
                    </span>
                    <span class="tag" style="background:#1a1d24;color:#6b7280;border:1px solid #1e2128">
                        Etki: {etki}
                    </span>
                </div>
                <div class="finding-title">{f['title']}</div>
                <div class="finding-meta">Kök Neden Analizi</div>
                <div class="finding-body">{f['root_cause']}</div>
                <div class="finding-meta" style="margin-top:10px">İş Etkisi</div>
                <div class="finding-body">{f.get('impact','—')}</div>
                <div class="finding-rec">
                    <span style="color:#00e5b0;font-size:10px;letter-spacing:0.1em;
                                 text-transform:uppercase">Aksiyon →</span><br>
                    {f['recommendation']}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # KPI Hedefleri
        kpi = analysis.get("kpi_targets", {})
        st.divider()
        st.markdown("**🎯 Hedef KPI Tablosu**")
        kc1, kc2, kc3 = st.columns(3)
        kc1.metric("Fulfillment Hedefi", f"{kpi.get('fulfillment_target_hours',24)} saat",
                   f"Şu an: {ft.get('median',0)}s medyan")
        kc2.metric("Yeniden Sipariş Noktası", f"{kpi.get('inventory_reorder_point',30)} adet",
                   "Kritik eşik")
        kc3.metric("Maks İptal Oranı", f"%{kpi.get('target_cancellation_rate_pct',2.5)}",
                   f"Şu an: %{rev.get('cancellation_rate',0)}")

    # ─── TAB 2: GELİR ANALİZİ
    with tab2:
        if not orders_df.empty and "created_at" in orders_df.columns:
            valid_orders = orders_df[~orders_df["fulfillment_status"].isin(["cancelled","refunded"])].copy()

            # Günlük gelir grafiği
            valid_orders["date"] = pd.to_datetime(valid_orders["created_at"]).dt.date
            daily = valid_orders.groupby("date")["total_price"].sum().reset_index()
            daily["rolling_7d"] = daily["total_price"].rolling(7, min_periods=1).mean()

            fig_rev = go.Figure()
            fig_rev.add_trace(go.Bar(
                x=daily["date"], y=daily["total_price"],
                name="Günlük Gelir",
                marker_color="rgba(0,229,176,0.25)",
                marker_line_color="rgba(0,229,176,0.6)",
                marker_line_width=1,
            ))
            fig_rev.add_trace(go.Scatter(
                x=daily["date"], y=daily["rolling_7d"],
                name="7 Günlük Ortalama",
                line=dict(color="#ff6b35", width=2),
                mode="lines",
            ))
            fig_rev.update_layout(
                title="Günlük Gelir (€)",
                legend=dict(orientation="h", y=1.1, x=0),
                **plotly_theme()
            )
            st.plotly_chart(fig_rev, use_container_width=True)

            gc1, gc2 = st.columns(2)

            # Durum dağılımı
            with gc1:
                status_counts = orders_df["fulfillment_status"].value_counts().reset_index()
                status_colors = {
                    "fulfilled": "#00e5b0", "unfulfilled": "#f5a623",
                    "cancelled": "#ff3b5c", "refunded": "#ff6b35",
                }
                colors = [status_colors.get(s, "#6b7280") for s in status_counts["fulfillment_status"]]
                fig_pie = go.Figure(go.Pie(
                    labels=status_counts["fulfillment_status"],
                    values=status_counts["count"],
                    hole=0.55,
                    marker=dict(colors=colors, line=dict(color="#0a0c0f", width=2)),
                    textfont=dict(family="DM Mono"),
                ))
                fig_pie.update_layout(title="Sipariş Durum Dağılımı", **plotly_theme())
                st.plotly_chart(fig_pie, use_container_width=True)

            # Fulfillment süresi dağılımı
            with gc2:
                if "fulfillment_hours_series" in metrics.get("fulfillment_time", {}):
                    fh_series = metrics["fulfillment_time"]["fulfillment_hours_series"]
                    if hasattr(fh_series, "to_dict"):
                        hours = pd.Series([r["fulfillment_hours"] for r in fh_series.to_dict("records")])
                    else:
                        hours = pd.Series([])
                else:
                    fulfilled = orders_df[
                        (orders_df["fulfillment_status"] == "fulfilled") &
                        (orders_df["fulfilled_at"].notna())
                    ].copy()
                    fulfilled["fh"] = (
                        pd.to_datetime(fulfilled["fulfilled_at"]) -
                        pd.to_datetime(fulfilled["created_at"])
                    ).dt.total_seconds() / 3600
                    hours = fulfilled["fh"].clip(0, 120)

                fig_hist = go.Figure(go.Histogram(
                    x=hours,
                    nbinsx=30,
                    marker_color="rgba(0,229,176,0.4)",
                    marker_line_color="rgba(0,229,176,0.8)",
                    marker_line_width=1,
                ))
                fig_hist.add_vline(x=24, line_dash="dash", line_color="#f5a623",
                                   annotation_text="24s", annotation_font_color="#f5a623")
                fig_hist.add_vline(x=48, line_dash="dash", line_color="#ff3b5c",
                                   annotation_text="48s", annotation_font_color="#ff3b5c")
                fig_hist.update_layout(title="Fulfillment Süresi Dağılımı (saat)", **plotly_theme())
                st.plotly_chart(fig_hist, use_container_width=True)

            # Haftalık özet tablosu
            st.divider()
            st.markdown("**Haftalık Özet**")
            valid_orders["week"] = pd.to_datetime(valid_orders["created_at"]).dt.to_period("W").astype(str)
            weekly = valid_orders.groupby("week").agg(
                Sipariş=("order_id","count"),
                Gelir=("total_price","sum"),
                AOV=("total_price","mean"),
            ).round(2).reset_index()
            weekly.columns = ["Hafta","Sipariş","Gelir (€)","AOV (€)"]
            st.dataframe(weekly.tail(8), use_container_width=True, hide_index=True)

    # ─── TAB 3: STOK
    with tab3:
        if not products_df.empty:
            # Stok durumu tablosu
            inv_df = products_df[["title","category","inventory","price","cost","margin_pct"]].copy()
            inv_df.columns = ["Ürün","Kategori","Stok","Fiyat €","Maliyet €","Margin %"]
            inv_df = inv_df.sort_values("Stok")

            def stok_badge(v):
                if v == 0:   return "🔴 TÜKENDİ"
                if v < 10:   return "🔴 KRİTİK"
                if v < 30:   return "⚠️ DÜŞÜK"
                return "✅ NORMAL"

            inv_df["Durum"] = inv_df["Stok"].apply(stok_badge)

            # Kritik ürünleri üstte göster
            inv_df = pd.concat([
                inv_df[inv_df["Stok"] < 30],
                inv_df[inv_df["Stok"] >= 30],
            ]).reset_index(drop=True)

            st.dataframe(
                inv_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Stok": st.column_config.ProgressColumn("Stok", max_value=200, format="%d"),
                    "Margin %": st.column_config.NumberColumn("Margin %", format="%.1f%%"),
                }
            )

            # Kategori stok grafiği
            cat_stock = products_df.groupby("category")["inventory"].sum().reset_index()
            fig_cat = go.Figure(go.Bar(
                x=cat_stock["category"],
                y=cat_stock["inventory"],
                marker_color=["#ff3b5c" if v < 50 else "#00e5b0" for v in cat_stock["inventory"]],
                text=cat_stock["inventory"],
                textposition="outside",
                textfont=dict(color="#e8eaf0"),
            ))
            fig_cat.update_layout(title="Kategoriye Göre Toplam Stok", **plotly_theme())
            st.plotly_chart(fig_cat, use_container_width=True)

            # Margin analizi
            fig_margin = go.Figure()
            fig_margin.add_trace(go.Bar(
                x=products_df["title"].str[:20],
                y=products_df["margin_pct"],
                marker_color=[
                    "#00e5b0" if m >= 70 else "#f5a623" if m >= 50 else "#ff3b5c"
                    for m in products_df["margin_pct"]
                ],
                text=[f"%{m:.0f}" for m in products_df["margin_pct"]],
                textposition="outside",
                textfont=dict(color="#e8eaf0"),
            ))
            fig_margin.update_layout(title="Ürün Kar Marjları", **plotly_theme())
            st.plotly_chart(fig_margin, use_container_width=True)

    # ─── TAB 4: HIZLI KAZANIMLAR
    with tab4:
        qws = analysis.get("quick_wins", [])
        st.markdown("""
        <div style="font-family:'Syne',sans-serif;font-size:20px;font-weight:700;
                    margin-bottom:20px">
            Bu Hafta Yapılacaklar
        </div>
        """, unsafe_allow_html=True)

        for i, qw in enumerate(qws, 1):
            st.markdown(f"""
            <div class="qw-item">
                <div class="qw-num">{i:02d}</div>
                <div>{qw}</div>
            </div>
            """, unsafe_allow_html=True)

        st.divider()
        st.markdown("**📊 Bulgular Öncelik Matrisi**")

        findings = analysis.get("findings", [])
        if findings:
            effort_map = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Low": 1, "Medium": 2, "High": 3}
            impact_map = {"Düşük": 1, "Orta": 2, "Yüksek": 3, "Low": 1, "Medium": 2, "High": 3}
            color_map  = {"critical": "#ff3b5c", "warning": "#f5a623", "ok": "#00e5b0"}

            fig_matrix = go.Figure()
            for f in findings:
                x = effort_map.get(f.get("estimated_effort","Orta"), 2) + np.random.uniform(-0.05, 0.05)
                y = impact_map.get(f.get("estimated_impact","Orta"), 2) + np.random.uniform(-0.05, 0.05)
                fig_matrix.add_trace(go.Scatter(
                    x=[x], y=[y],
                    mode="markers+text",
                    text=[f["title"][:20]],
                    textposition="top center",
                    textfont=dict(size=10, color="#9ca3b0"),
                    marker=dict(
                        size=20,
                        color=color_map.get(f["severity"], "#6b7280"),
                        opacity=0.85,
                        line=dict(color="#0a0c0f", width=2),
                    ),
                    showlegend=False,
                    hovertext=f["title"],
                ))

            theme = plotly_theme()
            theme["xaxis"] = dict(title="Uygulama Efor", tickvals=[1,2,3], ticktext=["Düşük","Orta","Yüksek"], gridcolor="#1e2128")
            theme["yaxis"] = dict(title="İş Etkisi", tickvals=[1,2,3], ticktext=["Düşük","Orta","Yüksek"], gridcolor="#1e2128")
            theme["height"] = 420
            fig_matrix.update_layout(**theme)
            # Öncelik bölgeleri
            fig_matrix.add_shape(type="rect", x0=0.5, x1=1.5, y0=1.5, y1=3.5,
                                  fillcolor="rgba(0,229,176,0.05)", line_width=0)
            fig_matrix.add_annotation(x=1, y=3.4, text="HIZLI KAZAN →", showarrow=False,
                                       font=dict(color="#00e5b0", size=9))
            st.plotly_chart(fig_matrix, use_container_width=True)

        # JSON export
        st.divider()
        export_data = {k: v for k, v in result.items() if k not in ("orders_df","products_df")}
        st.download_button(
            "⬇  Raporu JSON İndir",
            data=json.dumps(export_data, ensure_ascii=False, indent=2, default=str),
            file_name=f"ops_report_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
            mime="application/json",
            use_container_width=True,
        )

    # ─── TAB 5: META ADS
    with tab5:
        mr = st.session_state.meta_result
        if mr is None:
            st.info("← Sol panelden **ANALİZİ ÇALIŞTIR** butonuna bas")
        else:
            ra = mr["roas_analysis"]

            # ── KPI Üst Satırı
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("Toplam Harcama",  f"€{ra['total_spend']:,.0f}")
            mc2.metric("Toplam Gelir",    f"€{ra['total_revenue']:,.0f}")
            roas_color = "normal" if ra["blended_roas"] >= 2.0 else "inverse"
            mc3.metric("Blended ROAS",    f"{ra['blended_roas']}x",
                       "↑ Hedef 3.0x", delta_color=roas_color)
            mc4.metric("İyi Kampanya",    f"{ra['good_campaigns']} / {ra['total_campaigns']}")
            mc5.metric("Kritik Kampanya", f"{ra['bad_campaigns']}",
                       delta_color="inverse" if ra["bad_campaigns"] > 0 else "off")

            st.divider()

            # ── Kampanya tablosu
            st.markdown("**📊 Kampanya Performans Tablosu**")
            camp_df = mr["campaign_summary"][
                ["campaign_name","spend","revenue","roas","cpc","ctr","purchases","avg_freq","durum"]
            ].copy()
            camp_df.columns = ["Kampanya","Harcama €","Gelir €","ROAS","CPC €","CTR %","Satış","Frekans","Durum"]
            st.dataframe(
                camp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "ROAS": st.column_config.ProgressColumn("ROAS", max_value=5, format="%.2fx"),
                    "Harcama €": st.column_config.NumberColumn(format="€%.0f"),
                    "Gelir €":   st.column_config.NumberColumn(format="€%.0f"),
                }
            )

            # ── Günlük trend grafiği
            daily = mr["daily_trends"]
            fig_meta = go.Figure()
            fig_meta.add_trace(go.Bar(
                x=daily["date"], y=daily["spend"],
                name="Harcama €",
                marker_color="rgba(255,107,53,0.3)",
                marker_line_color="rgba(255,107,53,0.7)",
                marker_line_width=1,
            ))
            fig_meta.add_trace(go.Scatter(
                x=daily["date"], y=daily["revenue"],
                name="Gelir €",
                line=dict(color="#00e5b0", width=2),
                mode="lines",
            ))
            fig_meta.add_trace(go.Scatter(
                x=daily["date"], y=daily["spend_7d_avg"],
                name="Harcama 7g Ort.",
                line=dict(color="#ff6b35", width=1.5, dash="dot"),
                mode="lines",
            ))
            fig_meta.update_layout(
                title="Günlük Reklam Harcaması vs Gelir (€)",
                legend=dict(orientation="h", y=1.1, x=0),
                **plotly_theme()
            )
            st.plotly_chart(fig_meta, use_container_width=True)

            # ROAS trend
            fig_roas = go.Figure()
            fig_roas.add_trace(go.Scatter(
                x=daily["date"], y=daily["roas"],
                mode="lines",
                line=dict(color="#f5a623", width=2),
                fill="tozeroy",
                fillcolor="rgba(245,166,35,0.08)",
                name="Günlük ROAS",
            ))
            fig_roas.add_hline(y=3.0, line_dash="dash", line_color="#00e5b0",
                               annotation_text="Hedef ROAS 3x", annotation_font_color="#00e5b0")
            fig_roas.add_hline(y=1.5, line_dash="dash", line_color="#ff3b5c",
                               annotation_text="Başabaş 1.5x", annotation_font_color="#ff3b5c")
            fig_roas.update_layout(title="Günlük ROAS Trendi", **plotly_theme())
            st.plotly_chart(fig_roas, use_container_width=True)

            # ── ÇAPRAZ ALARMLAR
            st.divider()
            alarms = mr["cross_alarms"]
            crit = [a for a in alarms if a["severity"] == "critical"]
            warn = [a for a in alarms if a["severity"] == "warning"]

            st.markdown(f"""
            <div style="font-family:'Syne',sans-serif;font-size:18px;font-weight:700;margin-bottom:16px">
                🚨 Çapraz Alarmlar
                <span style="font-size:12px;font-weight:400;color:#6b7280;margin-left:12px">
                    {len(crit)} kritik · {len(warn)} uyarı
                </span>
            </div>
            """, unsafe_allow_html=True)

            if not alarms:
                st.success("✅ Aktif çapraz alarm yok — stok ve reklam senkronize görünüyor.")
            else:
                for a in alarms:
                    sev = a["severity"]
                    icon = "🔴" if sev == "critical" else "⚠️"
                    border = "#ff3b5c" if sev == "critical" else "#f5a623"
                    bg     = "rgba(255,59,92,0.05)" if sev == "critical" else "rgba(245,166,35,0.05)"
                    waste_html = ""
                    if a.get("estimated_waste_eur"):
                        waste_html = f"""<div style="margin-top:8px;font-size:11px;color:#ff3b5c">
                            💸 Tahmini 2 haftalık israf: €{a['estimated_waste_eur']:.0f}
                        </div>"""

                    st.markdown(f"""
                    <div style="background:{bg};border:1px solid {border};border-radius:8px;
                                padding:16px 20px;margin-bottom:12px;border-left:3px solid {border}">
                        <div style="display:flex;gap:10px;align-items:center;margin-bottom:8px">
                            <span style="background:rgba(255,255,255,0.05);border:1px solid {border};
                                         border-radius:4px;padding:2px 8px;font-size:10px;
                                         letter-spacing:0.1em;color:{border}">{a['alarm_type']}</span>
                            <span style="font-size:11px;color:#6b7280">{a.get('campaign','')[:40]}</span>
                        </div>
                        <div style="font-family:'Syne',sans-serif;font-size:15px;font-weight:600;
                                    margin-bottom:8px">{icon} {a['title']}</div>
                        <div style="font-size:12px;color:#9ca3b0;line-height:1.6">{a['description']}</div>
                        <div style="font-size:12px;margin-top:10px;padding:8px 12px;
                                    background:rgba(0,229,176,0.05);border-radius:4px;
                                    border-left:2px solid #00e5b0">
                            <span style="color:#00e5b0;font-size:10px;letter-spacing:0.1em;
                                         text-transform:uppercase">Aksiyon →</span><br>
                            {a['action']}
                        </div>
                        {waste_html}
                    </div>
                    """, unsafe_allow_html=True)

            # ── En iyi / En kötü kampanya özeti
            st.divider()
            bc1, bc2 = st.columns(2)
            with bc1:
                st.markdown(f"""
                <div style="background:#111318;border:1px solid #1e2128;border-radius:8px;padding:16px 20px">
                    <div style="font-size:10px;color:#00e5b0;letter-spacing:0.1em;text-transform:uppercase">En İyi Kampanya</div>
                    <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;margin:8px 0 4px">{ra['top_campaign'][:45]}</div>
                    <div style="font-size:24px;font-weight:800;color:#00e5b0">{ra['top_roas']}x ROAS</div>
                </div>
                """, unsafe_allow_html=True)
            with bc2:
                st.markdown(f"""
                <div style="background:#111318;border:1px solid #1e2128;border-radius:8px;padding:16px 20px">
                    <div style="font-size:10px;color:#ff3b5c;letter-spacing:0.1em;text-transform:uppercase">En Düşük Performans</div>
                    <div style="font-family:'Syne',sans-serif;font-size:16px;font-weight:700;margin:8px 0 4px">{ra['worst_campaign'][:45]}</div>
                    <div style="font-size:24px;font-weight:800;color:#ff3b5c">{ra['worst_roas']}x ROAS</div>
                </div>
                """, unsafe_allow_html=True)
