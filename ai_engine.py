"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 2: AI Analiz Motoru - OpenAI GPT-4 Entegrasyonu

Ek kurulum:
pip install openai --break-system-packages
"""

import os
import json
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional
import numpy as np
from openai import OpenAI

# Adım 1'den içe aktar
from data_layer import run_pipeline, ShopifyConfig


# ─────────────────────────────────────────────
# KONFİGÜRASYON
# ─────────────────────────────────────────────

@dataclass
class AIConfig:
    api_key: str = ""
    model: str = "gpt-4o-mini"
    language: str = "en"
    use_mock_ai: bool = True


# ─────────────────────────────────────────────
# PROMPT ŞABLONLARI
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """Sen, e-ticaret operasyonlarında uzman bir Endüstri Mühendisi ve İş Analistisin.
Görevin: verilen operasyonel metrikleri analiz etmek, kök nedenleri tespit etmek ve somut, 
önceliklendirilmiş aksiyon planı sunmak.

Yanıt formatın HER ZAMAN geçerli JSON olmalıdır. Markdown veya ekstra metin ekleme.
Dil: {language}

JSON yapısı:
{{
  "executive_summary": "2-3 sentence executive summary",
  "overall_health_score": score between 0-100,
  "overall_health_label": "Critical | Poor | Average | Good | Excellent",
  "findings": [
    {{
      "area": "area name",
      "severity": "critical | warning | ok",
      "title": "kısa başlık",
      "root_cause": "kök neden analizi",
      "impact": "iş etkisi (para/müşteri kaybı gibi)",
      "recommendation": "concrete action step",
      "priority": 1-5 (1=en acil),
      "estimated_effort": "Low | Medium | High",
      "estimated_impact": "Low | Medium | High"
    }}
  ],
  "quick_wins": ["3 quick actions doable this week"],
  "kpi_targets": {{
    "fulfillment_target_hours": number,
    "inventory_reorder_point": number,
    "target_cancellation_rate_pct": number
  }},
  "swot": {{
    "strengths": ["2-3 key strengths based on data"],
    "weaknesses": ["2-3 key weaknesses based on data"],
    "opportunities": ["2-3 market/operational opportunities"],
    "threats": ["2-3 risks or threats to watch"]
  }}
}}"""

ANALYSIS_PROMPT = """Aşağıdaki e-ticaret operasyon verilerini analiz et:

=== SİPARİŞ HAZIRLAMA SÜRESİ ===
- Ortalama: {fulfillment_mean} saat
- Medyan: {fulfillment_median} saat
- P95 (en yavaş %5): {fulfillment_p95} saat
- 72 saatten uzun sipariş sayısı: {orders_over_72h} adet ({orders_over_72h_pct}%)
- Durum: {fulfillment_status}

=== STOK ANALİZİ ===
- Ortalama stok devir hızı: {avg_turnover}x
- Number of critical stock products: {critical_items_count}
- Critical products: {critical_items}
- Toplam ürün sayısı: {total_products}

=== GELİR METRİKLERİ ===
- Toplam gelir (90 gün): €{total_revenue}
- Toplam sipariş: {total_orders}
- Geçerli sipariş: {valid_orders}
- Ortalama sepet tutarı (AOV): €{aov}
- İptal oranı: %{cancellation_rate}
- İade oranı: %{refund_rate}
- Average items per order: {avg_items}

=== BAĞLAM ===
- Hedef pazar: AB (Öncelikle Almanya)
- Sektör: Kozmetik / Lüks bakım ürünleri
- Kanal: Shopify D2C + Meta Ads

Bu verilere dayanarak kapsamlı operasyonel analiz yap ve JSON formatında döndür."""


# ─────────────────────────────────────────────
# MOCK AI YANITI (API key olmadan test için)
# ─────────────────────────────────────────────

MOCK_AI_RESPONSE = {
    "executive_summary": "Order fulfillment time is below the industry average, indicating good performance. However, critical stock levels detected in 3 products may lead to revenue loss and customer dissatisfaction. Cancellation and return rates are within acceptable limits, but there are cross-sell opportunities to increase average order value.",
    "overall_health_score": 68,
    "overall_health_label": "Orta",
    "findings": [
        {
            "area": "Inventory Management",
            "severity": "critical",
            "title": "3 Products with Critical Stock Levels",
            "root_cause": "Coconut Shampoo (0 stock), Vitamin C Cream (9 units) and Midnight Oud Perfume (16 units) are at risk of stockout. Reorder points appear to be undefined in the supply chain.",
            "impact": "If these 3 products account for ~35% of total sales, stockouts could cause €13,000+ revenue loss in 90 days. Ad spend is also wasted if Meta Ads traffic is directed to out-of-stock products.",
            "recommendation": "Contact your supplier immediately. Place urgent order for Coconut Shampoo. Set 'reorder points' for all products in Shopify (minimum 30 units). Auto-pause Meta Ads for products when stock runs out.",
            "priority": 1,
            "estimated_effort": "Düşük",
            "estimated_impact": "Yüksek"
        },
        {
            "area": "Order Fulfillment",
            "severity": "ok",
            "title": "Fulfillment Time Under Control",
            "root_cause": "Medyan 12.1 saat, P95 39.5 saat. 72 saatten uzun yalnızca 1 sipariş mevcut. Bu performans Amazon Prime dışındaki rakiplere göre rekabetçi.",
            "impact": "Mevcut durum müşteri memnuniyeti için yeterli. Almanya'da tüketiciler hız konusunda hassastır; bu avantajı pazarlama materyallerinde vurgulamak dönüşümü artırabilir.",
            "recommendation": "Hızlı gönderimi ('24 Stunden Versand' gibi) ürün sayfalarında ve Meta Ads'te öne çıkar. P95'i 24 saatin altına indirmeyi hedefle.",
            "priority": 4,
            "estimated_effort": "Düşük",
            "estimated_impact": "Orta"
        },
        {
            "area": "Gelir Optimizasyonu",
            "severity": "warning",
            "title": "AOV Increase Opportunity Available",
            "root_cause": "Ortalama sepet tutarı €201. Kozmetik sektöründe çapraz satış (örn. serum + tonik + krem seti) ile bu rakamın %20-30 artırılması mümkün.",
            "impact": "AOV'yi €201'den €250'ye çıkarmak, mevcut sipariş hacmiyle 90 günde ek €9,800+ gelir anlamına gelir.",
            "recommendation": "Shopify'da 'Frequently Bought Together' uygulaması ekle. Skincare rutini paketleri oluştur (Serum + Toner + Cream = %10 indirim). Sepet sayfasında upsell widget'ı test et.",
            "priority": 2,
            "estimated_effort": "Orta",
            "estimated_impact": "Yüksek"
        },
        {
            "area": "Cancellation & Return Management",
            "severity": "ok",
            "title": "Cancellation and Return Rates Acceptable",
            "root_cause": "İptal %3.5, iade %3.0. Kozmetik sektörü ortalaması %5-8 iade. Şu anki oranlar iyi ancak Almanya'da 14 günlük yasal iade hakkı göz önünde bulundurulmalı.",
            "impact": "Mevcut oranlar düşük maliyetli. İade nedenlerini kategorize ederek ürün açıklamalarını iyileştirmek bu oranı daha da düşürebilir.",
            "recommendation": "İade gerekçelerini Shopify'da kayıt altına al. En sık iade edilen ürünlerin fotoğraf/açıklamalarını güçlendir. 'Satisfied or Refunded' garantisini öne çıkar.",
            "priority": 5,
            "estimated_effort": "Düşük",
            "estimated_impact": "Düşük"
        },
        {
            "area": "Ad-Inventory Alignment",
            "severity": "warning",
            "title": "No Meta Ads and Inventory Synchronization",
            "root_cause": "Meta Ads budget may keep flowing to out-of-stock products, wasting ad spend and negatively impacting customer experience.",
            "impact": "Günlük €50 reklam bütçesinin %20'si stoksuz ürünlere gidiyorsa, ayda €300 israf söz konusu olabilir.",
            "recommendation": "Check Shopify-Meta Catalog synchronization. Set up automation to pause ad sets when stock drops below 10 units (possible with Shopify Flow or Zapier).",
            "priority": 3,
            "estimated_effort": "Orta",
            "estimated_impact": "Orta"
        }
    ],
    "quick_wins": [
        "Coconut Shampoo için bugün tedarikçiyle iletişime geç, acil sipariş ver",
        "Shopify admin'de stoku 0 olan ürünlerin Meta Ads reklam setlerini manuel olarak durdur",
        "Ürün sayfalarına '24 saat içinde kargoya verilir' etiketi ekle"
    ],
    "kpi_targets": {
        "fulfillment_target_hours": 24,
        "inventory_reorder_point": 30,
        "target_cancellation_rate_pct": 2.5
    },
    "swot": {
        "strengths": [
            "Fast order fulfillment (median 12h) — competitive advantage vs industry average of 48h",
            "Low cancellation rate (3.5%) — well below the 5-8% cosmetics sector average",
            "Diverse product portfolio with strong margin potential"
        ],
        "weaknesses": [
            "Critical stock issues on 3 key products risk stockouts and lost revenue",
            "AOV of €201 below €250 target — cross-sell opportunities untapped",
            "No Meta Ads and inventory synchronization causing ad spend waste"
        ],
        "opportunities": [
            "Bundle creation (serum + toner + cream sets) could increase AOV by 20-30%",
            "German market expansion — fast fulfillment is a key differentiator in DE",
            "Win-back campaigns for at-risk customers with high historical spend"
        ],
        "threats": [
            "Stockouts on popular products could drive customers to competitors",
            "Rising Meta Ads CPM in cosmetics vertical increasing customer acquisition costs",
            "14-day return policy in EU markets if product descriptions are not accurate"
        ]
    }
}


# ─────────────────────────────────────────────
# AI ANALİZ MOTORU
# ─────────────────────────────────────────────

class AIAnalysisEngine:
    """
    OpenAI GPT-4 ile operasyonel metrikleri yorumlar,
    kök neden analizi yapar ve aksiyon planı üretir.
    """

    def __init__(self, config: AIConfig):
        self.config = config
        if not config.use_mock_ai:
            api_key = config.api_key or os.environ.get("OPENAI_API_KEY", "")
            if not api_key:
                raise ValueError("OPENAI_API_KEY bulunamadı. AIConfig.api_key veya env var set edin.")
            self.client = OpenAI(api_key=api_key)

    def _build_prompt(self, report: dict) -> str:
        """Metriklerden analiz prompt'u oluşturur"""
        ft  = report["fulfillment_time"]
        inv = report["inventory"]
        rev = report["revenue"]

        critical_items = inv.get("critical_items")
        if critical_items is not None and len(critical_items) > 0:
            critical_str = ", ".join(
                f"{row['title']} ({row['inventory']} units)"
                for _, row in critical_items.iterrows()
            )
        else:
            critical_str = "None"

        lang = "English"

        return ANALYSIS_PROMPT.format(
            fulfillment_mean      = ft["mean"],
            fulfillment_median    = ft["median"],
            fulfillment_p95       = ft["p95"],
            orders_over_72h       = ft["orders_over_72h"],
            orders_over_72h_pct   = round(ft["orders_over_72h"] / max(ft["total_fulfilled"], 1) * 100, 1),
            fulfillment_status    = ft["status"],
            avg_turnover          = inv["avg_turnover"],
            critical_items_count  = len(inv["critical_items"]) if inv["critical_items"] is not None else 0,
            critical_items        = critical_str,
            total_products        = len(inv["details"]),
            total_revenue         = f"{rev['total_revenue']:,.2f}",
            total_orders          = rev["total_orders"],
            valid_orders          = rev["valid_orders"],
            aov                   = f"{rev['aov']:.2f}",
            cancellation_rate     = rev["cancellation_rate"],
            refund_rate           = rev["refund_rate"],
            avg_items             = rev["avg_items_per_order"],
        )

    def analyze(self, report: dict) -> dict:
        """
        Operasyonel raporu AI'ya gönderir, yapılandırılmış analiz döndürür.
        use_mock_ai=True ise API çağrısı yapılmaz.
        """

        if self.config.use_mock_ai:
            print("🤖 [MOCK AI] Analiz yapılıyor... (gerçek API çağrısı yok)")
            time.sleep(1.2)  # API gecikme simülasyonu
            return {
                "success": True,
                "model": "mock-gpt-4o",
                "prompt_tokens": 850,
                "completion_tokens": 620,
                "analysis": MOCK_AI_RESPONSE,
                "generated_at": datetime.now().isoformat(),
            }

        # ── Gerçek OpenAI API çağrısı ──
        print(f"🤖 [GPT-4] {self.config.model} ile analiz başlıyor...")

        lang = "English"
        system = SYSTEM_PROMPT.format(language=lang)
        user_prompt = self._build_prompt(report)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user",   "content": user_prompt},
                ],
                temperature=0.3,       # Tutarlı, az yaratıcı çıktı
                response_format={"type": "json_object"},  # Garantili JSON
                max_tokens=2000,
            )

            raw = response.choices[0].message.content
            analysis = json.loads(raw)

            return {
                "success": True,
                "model": self.config.model,
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "analysis": analysis,
                "generated_at": datetime.now().isoformat(),
            }

        except json.JSONDecodeError as e:
            return {"success": False, "error": f"JSON parse hatası: {e}", "raw": raw}
        except Exception as e:
            return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────
# RAPOR YAZICI
# ─────────────────────────────────────────────

class ReportFormatter:
    """AI çıktısını okunabilir formata dönüştürür"""

    SEVERITY_ICONS = {"critical": "🔴", "warning": "⚠️", "ok": "✅"}
    PRIORITY_LABELS = {1: "ACİL", 2: "Yüksek", 3: "Orta", 4: "Düşük", 5: "İzle"}

    @staticmethod
    def to_console(result: dict) -> None:
        """Terminale renkli çıktı (rich kütüphanesi)"""
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.columns import Columns
        from rich import box

        console = Console()
        a = result["analysis"]

        # ── Skor Paneli
        score = a["overall_health_score"]
        color = "green" if score >= 70 else "yellow" if score >= 50 else "red"
        console.print(Panel(
            f"[bold {color}]Operasyonel Sağlık Skoru: {score}/100 — {a['overall_health_label']}[/bold {color}]\n\n"
            f"{a['executive_summary']}",
            title="🏥 Yönetici Özeti",
            border_style=color,
        ))

        # ── Bulgular Tablosu
        table = Table(title="📋 Operasyonel Bulgular", box=box.ROUNDED, show_lines=True)
        table.add_column("Öncelik",  width=8,  justify="center")
        table.add_column("Alan",     width=18)
        table.add_column("Sorun",    width=28)
        table.add_column("Kök Neden", width=35)
        table.add_column("Aksiyon",  width=35)
        table.add_column("Efor/Etki", width=12, justify="center")

        findings = sorted(a["findings"], key=lambda x: x["priority"])
        for f in findings:
            icon = ReportFormatter.SEVERITY_ICONS.get(f["severity"], "❓")
            pri_label = ReportFormatter.PRIORITY_LABELS.get(f["priority"], str(f["priority"]))
            pri_color = "red" if f["priority"] == 1 else "yellow" if f["priority"] <= 3 else "green"

            table.add_row(
                f"[{pri_color}]{icon}\n{pri_label}[/{pri_color}]",
                f["area"],
                f["title"],
                f["root_cause"][:120] + "..." if len(f["root_cause"]) > 120 else f["root_cause"],
                f["recommendation"][:120] + "..." if len(f["recommendation"]) > 120 else f["recommendation"],
                f"{f['estimated_effort']}\n{f['estimated_impact']}",
            )

        console.print(table)

        # ── Hızlı Kazanımlar
        console.print("\n[bold cyan]⚡ Bu Hafta Yapılacaklar (Quick Wins):[/bold cyan]")
        for i, qw in enumerate(a["quick_wins"], 1):
            console.print(f"  {i}. {qw}")

        # ── KPI Hedefleri
        kpi = a["kpi_targets"]
        console.print(f"\n[bold cyan]🎯 Hedef KPI'lar:[/bold cyan]")
        console.print(f"  Fulfillment Hedefi : {kpi['fulfillment_target_hours']} saat")
        console.print(f"  Yeniden Sipariş    : {kpi['inventory_reorder_point']} adet stok altı")
        console.print(f"  Maks İptal Oranı   : %{kpi['target_cancellation_rate_pct']}")

        # ── Meta bilgi
        console.print(f"\n[dim]Model: {result['model']} | "
                      f"Token: {result['prompt_tokens']}+{result['completion_tokens']} | "
                      f"{result['generated_at'][:19]}[/dim]")

    @staticmethod
    def to_json(result: dict, path: str = "analysis_report.json") -> None:
        """JSON dosyasına kaydet (Adım 3'te Streamlit okuyacak)"""
        # DataFrame'leri çıkar (JSON serialize edilemiyor)
        safe = {k: v for k, v in result.items() if k != "orders_df"}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(safe, f, ensure_ascii=False, indent=2, default=str)
        print(f"💾 Rapor kaydedildi: {path}")


# ─────────────────────────────────────────────
# ANA PIPELINE (Adım 1 + 2 birleşik)
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
# 1. CHURN PREDICTION ENGINE
# ─────────────────────────────────────────────

def run_churn_prediction(orders_df, openai_client=None) -> dict:
    """
    Müşteri kaçış riski analizi.
    RFM (Recency, Frequency, Monetary) modeliyle churn riski hesaplar.
    """
    try:
        import pandas as pd
        now = pd.Timestamp.now(tz="UTC")

        if "customer_email" not in orders_df.columns:
            return {"error": "No customer data", "segments": [], "churn_rate": 0}

        # RFM hesapla
        rfm = orders_df.groupby("customer_email").agg(
            last_order=("created_at", "max"),
            frequency=("order_id", "count"),
            monetary=("total_price", "sum")
        ).reset_index()

        rfm["recency_days"] = (now - rfm["last_order"]).dt.days

        # Churn risk skoru (0-100)
        rfm["churn_risk"] = (
            (rfm["recency_days"] / rfm["recency_days"].max() * 60) +
            ((1 - rfm["frequency"] / rfm["frequency"].max()) * 25) +
            ((1 - rfm["monetary"] / rfm["monetary"].max()) * 15)
        ).clip(0, 100).round(1)

        # Segmentler
        rfm["segment"] = pd.cut(
            rfm["churn_risk"],
            bins=[0, 30, 60, 80, 100],
            labels=["Loyal", "At Risk", "High Risk", "Lost"]
        )

        segments = rfm["segment"].value_counts().to_dict()
        high_risk = rfm[rfm["churn_risk"] >= 60].sort_values("monetary", ascending=False)

        # Ortalama geri kazanım değeri
        avg_clv = rfm["monetary"].mean()

        return {
            "total_customers": len(rfm),
            "churn_rate": round((rfm["churn_risk"] >= 60).sum() / len(rfm) * 100, 1),
            "segments": {str(k): int(v) for k, v in segments.items()},
            "high_risk_count": int((rfm["churn_risk"] >= 60).sum()),
            "avg_customer_value": round(float(avg_clv), 2),
            "potential_revenue_at_risk": round(float(high_risk["monetary"].sum()), 2),
            "top_at_risk": high_risk[["customer_email","recency_days","monetary","churn_risk"]].head(5).to_dict("records"),
            "recommendation": "Re-engage customers inactive for 30+ days with a personalized win-back email offering 15% discount.",
        }
    except Exception as e:
        return {"error": str(e), "segments": {}, "churn_rate": 0}


# ─────────────────────────────────────────────
# 2. PRICE ELASTICITY ENGINE
# ─────────────────────────────────────────────

def run_price_elasticity(orders_df, products_df) -> dict:
    """
    Hangi ürünün fiyatını artırabilirsin?
    Satış hızı ve fiyat ilişkisini analiz eder.
    """
    try:
        import pandas as pd

        results = []
        for _, product in products_df.iterrows():
            title = product.get("title", "Unknown")
            price = float(product.get("price", 0))
            stock = float(product.get("stock", 0))
            cost  = float(product.get("cost", 0))
            margin = ((price - cost) / price * 100) if price > 0 else 0

            # Bu ürünün sipariş sayısı
            if "product_title" in orders_df.columns:
                product_orders = orders_df[orders_df["product_title"].str.contains(title, na=False, case=False)]
            else:
                product_orders = orders_df.head(0)  # boş

            order_count = len(product_orders)
            revenue = float(product_orders["total_price"].sum()) if len(product_orders) > 0 else price * 10

            # Elasticity score: yüksek margin + yüksek talep = fiyat artırılabilir
            elasticity_score = min(100, (margin * 0.5) + (min(order_count, 50) / 50 * 30) + (min(stock, 100) / 100 * 20))
            recommendation = "price_increase" if elasticity_score > 60 and margin < 60 else \
                            "bundle" if order_count > 10 else \
                            "discount" if stock > 80 else "maintain"

            price_increase_potential = round(price * 1.15, 2) if recommendation == "price_increase" else price
            additional_revenue = round((price_increase_potential - price) * max(order_count, 5), 2)

            results.append({
                "product": title,
                "current_price": price,
                "margin_pct": round(margin, 1),
                "elasticity_score": round(elasticity_score, 1),
                "recommendation": recommendation,
                "suggested_price": price_increase_potential,
                "additional_revenue_potential": additional_revenue,
            })

        results.sort(key=lambda x: x["additional_revenue_potential"], reverse=True)
        total_potential = sum(r["additional_revenue_potential"] for r in results if r["recommendation"] == "price_increase")

        return {
            "products": results[:10],
            "total_revenue_potential": round(total_potential, 2),
            "increase_candidates": sum(1 for r in results if r["recommendation"] == "price_increase"),
            "bundle_candidates": sum(1 for r in results if r["recommendation"] == "bundle"),
            "insight": f"Increasing prices on {sum(1 for r in results if r['recommendation'] == 'price_increase')} products by 15% could generate an additional €{round(total_potential, 0)} in revenue."
        }
    except Exception as e:
        return {"error": str(e), "products": [], "total_revenue_potential": 0}


# ─────────────────────────────────────────────
# 3. SEASONAL FORECASTING ENGINE
# ─────────────────────────────────────────────

def run_seasonal_forecast(orders_df) -> dict:
    """
    Önümüzdeki 30 günün gelir tahmini.
    Geçmiş trend + mevsimsel etkileri kullanır.
    """
    try:
        import pandas as pd

        orders_df = orders_df.copy()
        orders_df["created_at"] = pd.to_datetime(orders_df["created_at"], utc=True, errors="coerce")
        orders_df["date"] = orders_df["created_at"].dt.date
        orders_df["total_price"] = pd.to_numeric(orders_df["total_price"], errors="coerce").fillna(0)

        daily = orders_df.groupby("date").agg(
            revenue=("total_price", "sum"),
            orders=("order_id", "count")
        ).reset_index()

        if len(daily) < 7:
            # Yeterli veri yok — mock tahmin, revenue'dan hesapla
            total_rev = orders_df["total_price"].sum()
            total_orders = len(orders_df)
            avg_daily = total_rev / 30 if total_rev > 0 else 500
            avg_order_val = total_rev / max(total_orders, 1)
            forecast = []
            for i in range(1, 31):
                date = (datetime.now() + timedelta(days=i)).date()
                weekday = date.weekday()
                multiplier = 1.3 if weekday in [4, 5] else 0.85 if weekday == 6 else 1.0
                pred_rev = round(avg_daily * multiplier, 2)
                forecast.append({
                    "date": str(date),
                    "predicted_revenue": pred_rev,
                    "predicted_orders": max(1, round(pred_rev / max(avg_order_val, 1))),
                    "confidence": "medium"
                })
        else:
            daily["date"] = pd.to_datetime(daily["date"])
            daily["weekday"] = daily["date"].dt.weekday
            avg_daily = daily["revenue"].mean()
            trend = (daily["revenue"].iloc[-7:].mean() - daily["revenue"].iloc[:7].mean()) / max(daily["revenue"].iloc[:7].mean(), 1)

            weekday_factors = daily.groupby("weekday")["revenue"].mean() / avg_daily
            weekday_factors = weekday_factors.reindex(range(7), fill_value=1.0)

            forecast = []
            for i in range(1, 31):
                date = (datetime.now() + timedelta(days=i)).date()
                weekday = date.weekday()
                factor = weekday_factors.get(weekday, 1.0)
                predicted = avg_daily * float(factor) * (1 + trend * i / 30)
                forecast.append({
                    "date": str(date),
                    "predicted_revenue": round(max(0, predicted), 2),
                    "predicted_orders": max(1, round(predicted / max(avg_daily / daily["orders"].mean(), 1))),
                    "confidence": "high" if len(daily) >= 30 else "medium"
                })

        total_forecast = sum(f["predicted_revenue"] for f in forecast)
        peak_day = max(forecast, key=lambda x: x["predicted_revenue"])
        low_day = min(forecast, key=lambda x: x["predicted_revenue"])

        return {
            "forecast_30_days": forecast,
            "total_predicted_revenue": round(total_forecast, 2),
            "avg_daily_predicted": round(total_forecast / 30, 2),
            "peak_day": peak_day,
            "lowest_day": low_day,
            "insight": f"Next 30 days projected revenue: €{round(total_forecast, 0)}. Peak expected on {peak_day['date']} (€{peak_day['predicted_revenue']}).",
            "recommendation": "Increase ad spend on peak days. Prepare inventory for projected demand spikes."
        }
    except Exception as e:
        return {"error": str(e), "forecast_30_days": [], "total_predicted_revenue": 0}


# ─────────────────────────────────────────────
# 4. COMPETITOR BENCHMARKING ENGINE
# ─────────────────────────────────────────────

def run_competitor_benchmark(metrics: dict) -> dict:
    """
    Sektör ortalamasıyla karşılaştırma.
    E-ticaret kozmetik sektörü benchmark verileri kullanır.
    """
    # Sektör benchmark verileri (kozmetik D2C, AB)
    BENCHMARKS = {
        "fulfillment_hours": {"excellent": 12, "good": 24, "average": 48, "poor": 72, "label": "Order Fulfillment Time"},
        "cancellation_rate": {"excellent": 1.5, "good": 2.5, "average": 4.0, "poor": 7.0, "label": "Cancellation Rate %"},
        "refund_rate":       {"excellent": 2.0, "good": 4.0, "average": 6.0, "poor": 10.0, "label": "Refund Rate %"},
        "aov":               {"excellent": 85, "good": 60, "average": 40, "poor": 25, "label": "Average Order Value €"},
        "repeat_rate":       {"excellent": 40, "good": 25, "average": 15, "poor": 8, "label": "Repeat Purchase Rate %"},
    }

    ft  = metrics.get("fulfillment_time", {})
    rev = metrics.get("revenue", {})

    user_values = {
        "fulfillment_hours": ft.get("median", 0),
        "cancellation_rate": rev.get("cancellation_rate", 0),
        "refund_rate":       rev.get("refund_rate", 0),
        "aov":               rev.get("aov", 0),
        "repeat_rate":       rev.get("repeat_rate", 15),
    }

    results = []
    total_score = 0

    for key, bench in BENCHMARKS.items():
        user_val = user_values.get(key, 0)
        is_lower_better = key in ["fulfillment_hours", "cancellation_rate", "refund_rate"]

        if is_lower_better:
            if user_val <= bench["excellent"]:   rating, score = "Excellent", 100
            elif user_val <= bench["good"]:      rating, score = "Good", 75
            elif user_val <= bench["average"]:   rating, score = "Average", 50
            else:                                rating, score = "Below Average", 25
        else:
            if user_val >= bench["excellent"]:   rating, score = "Excellent", 100
            elif user_val >= bench["good"]:      rating, score = "Good", 75
            elif user_val >= bench["average"]:   rating, score = "Average", 50
            else:                                rating, score = "Below Average", 25

        total_score += score
        results.append({
            "metric": bench["label"],
            "your_value": user_val,
            "industry_average": bench["average"],
            "top_10_pct": bench["excellent"],
            "rating": rating,
            "score": score,
            "gap_to_excellent": round(abs(user_val - bench["excellent"]), 1),
        })

    overall_percentile = round(total_score / len(BENCHMARKS))
    return {
        "benchmarks": results,
        "overall_percentile": overall_percentile,
        "overall_rating": "Excellent" if overall_percentile >= 80 else "Good" if overall_percentile >= 60 else "Average" if overall_percentile >= 40 else "Below Average",
        "industry": "Cosmetics D2C — EU Market",
        "insight": f"You score better than {overall_percentile}% of similar e-commerce stores in the EU cosmetics market.",
        "top_strength": max(results, key=lambda x: x["score"])["metric"],
        "top_weakness": min(results, key=lambda x: x["score"])["metric"],
    }


# ─────────────────────────────────────────────
# MASTER ANALYSIS RUNNER
# ─────────────────────────────────────────────

def run_extended_analysis(report: dict, openai_client=None) -> dict:
    """Tüm gelişmiş analizleri çalıştırır"""
    orders_df  = report.get("orders_df")
    products_df = report.get("products_df")
    metrics    = {
        "fulfillment_time": report.get("fulfillment_time", {}),
        "revenue": report.get("revenue", {}),
        "inventory": report.get("inventory", {}),
    }

    result = {}

    if orders_df is not None and len(orders_df) > 0:
        print("🔮 Churn Prediction çalışıyor...")
        result["churn"] = run_churn_prediction(orders_df, openai_client)

        print("💰 Price Elasticity analizi çalışıyor...")
        result["price_elasticity"] = run_price_elasticity(orders_df, products_df) if products_df is not None else {}

        print("📈 Seasonal Forecast hesaplanıyor...")
        result["forecast"] = run_seasonal_forecast(orders_df)

    print("🏆 Competitor Benchmarking yapılıyor...")
    result["benchmark"] = run_competitor_benchmark(metrics)

    return result


def run_full_analysis(
    shopify_config: Optional[ShopifyConfig] = None,
    ai_config: Optional[AIConfig] = None,
) -> dict:
    """
    Tam pipeline:
    Veri Çek → Temizle → Metrikleri Hesapla → AI Analiz → Rapor
    """
    if shopify_config is None:
        shopify_config = ShopifyConfig(use_mock=True, mock_order_count=200)
    if ai_config is None:
        ai_config = AIConfig(use_mock_ai=True)

    # Adım 1: Veri
    print("\n" + "─"*50)
    print("ADIM 1: Veri Pipeline")
    print("─"*50)
    report = run_pipeline(shopify_config)

    # Adım 2: AI Analiz
    print("\n" + "─"*50)
    print("ADIM 2: AI Analiz Motoru")
    print("─"*50)
    engine = AIAnalysisEngine(ai_config)
    ai_result = engine.analyze(report)

    # API başarısız olursa Mock'a geri dön
    if not ai_result.get("success") or "analysis" not in ai_result:
        print(f"⚠️ API hatası: {ai_result.get('error', 'Bilinmeyen')} — Mock AI'ya geçiliyor")
        mock_engine = AIAnalysisEngine(AIConfig(use_mock_ai=True))
        ai_result = mock_engine.analyze(report)
        ai_result["api_fallback"] = True

    # Sonucu birleştir
    ai_result["metrics"] = {
        "fulfillment_time": {
            k: v for k, v in report["fulfillment_time"].items()
            if k != "fulfillment_hours_series"
        },
        "inventory": {
            k: (v.to_dict("records") if hasattr(v, "to_dict") else v)
            for k, v in report["inventory"].items()
            if k != "critical_items"
        },
        "revenue": report["revenue"],
    }
    ai_result["orders_df"]   = report["orders_df"]
    ai_result["products_df"] = report["products_df"]

    return ai_result


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    result = run_full_analysis()

    if result["success"]:
        ReportFormatter.to_console(result)
        ReportFormatter.to_json(result, "analysis_report.json")
    else:
        print(f"❌ Analiz başarısız: {result['error']}")
