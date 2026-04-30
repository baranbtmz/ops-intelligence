"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 2: AI Analiz Motoru - OpenAI GPT-4 Entegrasyonu

Ek kurulum:
pip install openai --break-system-packages
"""

import os
import json
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional
from openai import OpenAI

# Adım 1'den içe aktar
from data_layer import run_pipeline, ShopifyConfig


# ─────────────────────────────────────────────
# KONFİGÜRASYON
# ─────────────────────────────────────────────

@dataclass
class AIConfig:
    api_key: str = ""                  # OpenAI API key (veya env var)
    model: str = "gpt-4o-mini"        # gpt-4o veya gpt-4o-mini
    language: str = "tr"              # "tr" = Türkçe, "en" = İngilizce
    use_mock_ai: bool = True          # True = gerçek API çağrısı yapma, demo yanıtı döndür

    def __post_init__(self):
        """Streamlit Secrets veya env variable'dan key'i otomatik oku"""
        if not self.api_key:
            # Streamlit Secrets'tan dene
            try:
                import streamlit as st
                key = st.secrets.get("OPENAI_API_KEY", "")
                if key:
                    self.api_key = key
                    self.use_mock_ai = False
            except Exception:
                pass
        # Environment variable'dan dene
        if not self.api_key:
            key = os.environ.get("OPENAI_API_KEY", "")
            if key:
                self.api_key = key
                self.use_mock_ai = False


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
  "executive_summary": "2-3 cümle yönetici özeti",
  "overall_health_score": 0-100 arası puan,
  "overall_health_label": "Kritik | Zayıf | Orta | İyi | Mükemmel",
  "findings": [
    {{
      "area": "alan adı",
      "severity": "critical | warning | ok",
      "title": "kısa başlık",
      "root_cause": "kök neden analizi",
      "impact": "iş etkisi (para/müşteri kaybı gibi)",
      "recommendation": "somut aksiyon adımı",
      "priority": 1-5 (1=en acil),
      "estimated_effort": "Düşük | Orta | Yüksek",
      "estimated_impact": "Düşük | Orta | Yüksek"
    }}
  ],
  "quick_wins": ["Bu hafta yapılabilecek 3 hızlı aksiyon"],
  "kpi_targets": {{
    "fulfillment_target_hours": sayı,
    "inventory_reorder_point": sayı,
    "target_cancellation_rate_pct": sayı
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
- Kritik stok altındaki ürün sayısı: {critical_items_count}
- Kritik ürünler: {critical_items}
- Toplam ürün sayısı: {total_products}

=== GELİR METRİKLERİ ===
- Toplam gelir (90 gün): €{total_revenue}
- Toplam sipariş: {total_orders}
- Geçerli sipariş: {valid_orders}
- Ortalama sepet tutarı (AOV): €{aov}
- İptal oranı: %{cancellation_rate}
- İade oranı: %{refund_rate}
- Sipariş başına ortalama ürün: {avg_items}

=== BAĞLAM ===
- Hedef pazar: AB (Öncelikle Almanya)
- Sektör: Kozmetik / Lüks bakım ürünleri
- Kanal: Shopify D2C + Meta Ads

Bu verilere dayanarak kapsamlı operasyonel analiz yap ve JSON formatında döndür."""


# ─────────────────────────────────────────────
# MOCK AI YANITI (API key olmadan test için)
# ─────────────────────────────────────────────

MOCK_AI_RESPONSE = {
    "executive_summary": "Mağazanın sipariş hazırlama süresi sektör ortalamasının altında olup iyi performans göstermektedir. Ancak 3 üründe kritik stok seviyesi tespit edilmiş olup bu durum gelir kaybına ve müşteri memnuniyetsizliğine yol açabilir. İptal ve iade oranları kabul edilebilir sınırlarda olmakla birlikte, ortalama sepet tutarının artırılması için çapraz satış fırsatları mevcuttur.",
    "overall_health_score": 68,
    "overall_health_label": "Orta",
    "findings": [
        {
            "area": "Stok Yönetimi",
            "severity": "critical",
            "title": "3 Üründe Kritik Stok Seviyesi",
            "root_cause": "Coconut Shampoo (0 stok), Vitamin C Cream (9 adet) ve Midnight Oud Perfume (16 adet) tükenme riski altında. Tedarik zincirinde yeniden sipariş noktaları tanımlanmamış görünüyor.",
            "impact": "Bu 3 ürün toplam satışların yaklaşık %35'ini oluşturuyorsa, stok kesintisi 90 günde €13,000+ gelir kaybına yol açabilir. Ayrıca Meta Ads'ten gelen trafiğin bu ürünlere yönlendirilmesi durumunda reklam bütçesi israf olur.",
            "recommendation": "Derhal tedarikçiyle iletişime geç. Coconut Shampoo için acil sipariş ver. Shopify'da tüm ürünlere 'reorder point' tanımla (en az 30 adet). Stok tükendiğinde Meta Ads'te ilgili ürünlerin reklamını otomatik duraklat.",
            "priority": 1,
            "estimated_effort": "Düşük",
            "estimated_impact": "Yüksek"
        },
        {
            "area": "Sipariş Hazırlama",
            "severity": "ok",
            "title": "Fulfillment Süresi Kontrol Altında",
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
            "title": "AOV Artırma Fırsatı Mevcut",
            "root_cause": "Ortalama sepet tutarı €201. Kozmetik sektöründe çapraz satış (örn. serum + tonik + krem seti) ile bu rakamın %20-30 artırılması mümkün.",
            "impact": "AOV'yi €201'den €250'ye çıkarmak, mevcut sipariş hacmiyle 90 günde ek €9,800+ gelir anlamına gelir.",
            "recommendation": "Shopify'da 'Frequently Bought Together' uygulaması ekle. Skincare rutini paketleri oluştur (Serum + Toner + Cream = %10 indirim). Sepet sayfasında upsell widget'ı test et.",
            "priority": 2,
            "estimated_effort": "Orta",
            "estimated_impact": "Yüksek"
        },
        {
            "area": "İptal & İade Yönetimi",
            "severity": "ok",
            "title": "İptal ve İade Oranları Kabul Edilebilir",
            "root_cause": "İptal %3.5, iade %3.0. Kozmetik sektörü ortalaması %5-8 iade. Şu anki oranlar iyi ancak Almanya'da 14 günlük yasal iade hakkı göz önünde bulundurulmalı.",
            "impact": "Mevcut oranlar düşük maliyetli. İade nedenlerini kategorize ederek ürün açıklamalarını iyileştirmek bu oranı daha da düşürebilir.",
            "recommendation": "İade gerekçelerini Shopify'da kayıt altına al. En sık iade edilen ürünlerin fotoğraf/açıklamalarını güçlendir. 'Satisfied or Refunded' garantisini öne çıkar.",
            "priority": 5,
            "estimated_effort": "Düşük",
            "estimated_impact": "Düşük"
        },
        {
            "area": "Reklam-Stok Uyumu",
            "severity": "warning",
            "title": "Meta Ads ve Stok Senkronizasyonu Yok",
            "root_cause": "Stoku tükenen ürünlere Meta Ads bütçesi aktarılmaya devam edebilir. Bu durum reklam harcamasını boşa çıkarır ve müşteri deneyimini olumsuz etkiler.",
            "impact": "Günlük €50 reklam bütçesinin %20'si stoksuz ürünlere gidiyorsa, ayda €300 israf söz konusu olabilir.",
            "recommendation": "Shopify-Meta Catalog senkronizasyonunu kontrol et. Stok <10 olduğunda o ürünün reklam setini otomatik kapatan bir otomasyon kur (Shopify Flow veya Zapier ile mümkün).",
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
                f"{row['title']} ({row['inventory']} adet)"
                for _, row in critical_items.iterrows()
            )
        else:
            critical_str = "Yok"

        lang = "Türkçe" if self.config.language == "tr" else "English"

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

        lang = "Türkçe" if self.config.language == "tr" else "English"
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
