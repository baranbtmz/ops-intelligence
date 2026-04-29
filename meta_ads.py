"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 4: Meta Ads Entegrasyonu

Ek kurulum (opsiyonel - gerçek API için):
pip install facebook-business --break-system-packages
"""

import json
import random
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional

random.seed(99)
np.random.seed(99)


# ─────────────────────────────────────────────
# KONFİGÜRASYON
# ─────────────────────────────────────────────

@dataclass
class MetaConfig:
    access_token: str = ""       # Meta Graph API token
    ad_account_id: str = ""      # act_XXXXXXXXX formatında
    use_mock: bool = True        # True = gerçek API çağrısı yapma


# ─────────────────────────────────────────────
# MOCK META ADS VERİSİ
# ─────────────────────────────────────────────

class MetaMockGenerator:
    """
    Gerçekçi Meta Ads kampanya verisi üretir.
    Aurellia'nın Alman kozmetik pazarı senaryosuna göre ayarlanmış.
    """

    CAMPAIGNS = [
        {"id": "C001", "name": "Rose Serum — DE Kadın 25-44",     "objective": "CONVERSIONS", "product_sku": "SKN-001"},
        {"id": "C002", "name": "Oud Perfume — DE Lüks Segment",   "objective": "CONVERSIONS", "product_sku": "PRF-001"},
        {"id": "C003", "name": "Body Lotion — Retargeting DE",     "objective": "CONVERSIONS", "product_sku": "BDY-001"},
        {"id": "C004", "name": "Vitamin C Cream — Awareness",      "objective": "REACH",       "product_sku": "SKN-002"},
        {"id": "C005", "name": "Hair Mask — DE+AT+CH Broad",       "objective": "CONVERSIONS", "product_sku": "HRC-001"},
    ]

    def generate_daily_stats(self, days: int = 90) -> list[dict]:
        """Her kampanya için günlük reklam performans verisi üret"""
        records = []
        base_date = datetime.now() - timedelta(days=days)

        for camp in self.CAMPAIGNS:
            # Her kampanyanın kendine özgü performans profili var
            base_spend   = random.uniform(15, 55)     # günlük bütçe (€)
            base_ctr     = random.uniform(0.018, 0.055)  # tıklama oranı
            base_cpc     = random.uniform(0.35, 1.20)    # tıklama başı maliyet
            base_roas    = random.uniform(1.2, 4.5)      # reklam harcama getirisi

            # C004 Awareness kampanyası zayıf ROAS (normal)
            if camp["id"] == "C004":
                base_roas = random.uniform(0.6, 1.4)

            for d in range(days):
                date = base_date + timedelta(days=d)

                # Hafta sonu etkisi (Alman tüketici hafta sonu daha az alışveriş)
                weekend_factor = 0.75 if date.weekday() >= 5 else 1.0

                # Trend: ilk haftalarda düşük, sonra optimize
                trend = min(1.0 + d * 0.004, 1.35)

                # Günlük gürültü
                noise = np.random.normal(1.0, 0.18)

                spend      = round(base_spend * weekend_factor * noise, 2)
                impressions = int(spend / base_cpc / base_ctr * random.uniform(0.85, 1.15))
                clicks      = int(impressions * base_ctr * noise)
                cpc         = round(spend / max(clicks, 1), 2)
                ctr         = round(clicks / max(impressions, 1) * 100, 3)

                # Dönüşümler (purchases)
                conv_rate  = random.uniform(0.008, 0.045) * trend
                purchases  = max(int(clicks * conv_rate), 0)
                revenue    = round(purchases * random.uniform(85, 220), 2)
                roas       = round(revenue / max(spend, 0.01), 2)
                cpa        = round(spend / max(purchases, 1), 2)

                records.append({
                    "date":         date.strftime("%Y-%m-%d"),
                    "campaign_id":  camp["id"],
                    "campaign_name": camp["name"],
                    "objective":    camp["objective"],
                    "product_sku":  camp["product_sku"],
                    "spend":        spend,
                    "impressions":  impressions,
                    "clicks":       clicks,
                    "ctr":          ctr,
                    "cpc":          cpc,
                    "purchases":    purchases,
                    "revenue":      revenue,
                    "roas":         roas,
                    "cpa":          cpa,
                    "reach":        int(impressions * random.uniform(0.7, 0.95)),
                    "frequency":    round(random.uniform(1.1, 3.8), 2),
                })

        return records

    def generate_ad_sets(self) -> list[dict]:
        """Reklam seti bazında hedefleme verisi"""
        ad_sets = []
        audiences = [
            ("DE Kadın 25-34 — Skincare Interest", "DE", "25-34", "F"),
            ("DE Kadın 35-44 — Premium Beauty",    "DE", "35-44", "F"),
            ("DE Erkek 25-44 — Hediye Alıcılar",   "DE", "25-44", "M"),
            ("AT+CH Kadın 25-44 — Lookalike",      "AT,CH", "25-44", "F"),
            ("Retargeting — Site Ziyaretçileri",   "DE,AT,CH", "18-65", "ALL"),
        ]
        for i, (name, countries, age, gender) in enumerate(audiences):
            ad_sets.append({
                "id":          f"AS{i+1:03d}",
                "name":        name,
                "countries":   countries,
                "age_range":   age,
                "gender":      gender,
                "daily_budget": round(random.uniform(10, 40), 2),
                "status":      random.choice(["ACTIVE","ACTIVE","ACTIVE","PAUSED"]),
            })
        return ad_sets


# ─────────────────────────────────────────────
# META ADS İSTEMCİSİ
# ─────────────────────────────────────────────

class MetaAdsClient:
    """
    Meta Graph API ile iletişim kurar.
    use_mock=True ise MetaMockGenerator devreye girer.
    """

    def __init__(self, config: MetaConfig):
        self.config = config
        self.mock_gen = MetaMockGenerator()

    def fetch_campaign_insights(self, days: int = 90) -> list[dict]:
        if self.config.use_mock:
            print("📣 [MOCK] Meta Ads verisi üretiliyor...")
            return self.mock_gen.generate_daily_stats(days)

        # Gerçek API (facebook-business SDK)
        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount

            FacebookAdsApi.init(access_token=self.config.access_token)
            account = AdAccount(self.config.ad_account_id)

            since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            until = datetime.now().strftime("%Y-%m-%d")

            insights = account.get_insights(fields=[
                "campaign_name", "spend", "impressions", "clicks",
                "ctr", "cpc", "actions", "action_values", "reach", "frequency",
            ], params={
                "time_range": {"since": since, "until": until},
                "time_increment": 1,
                "level": "campaign",
            })
            return [dict(i) for i in insights]

        except ImportError:
            print("⚠️  facebook-business kurulu değil, mock data kullanılıyor.")
            return self.mock_gen.generate_daily_stats(days)

    def fetch_ad_sets(self) -> list[dict]:
        if self.config.use_mock:
            return self.mock_gen.generate_ad_sets()
        return []


# ─────────────────────────────────────────────
# META ADS ANALİZ MOTORU
# ─────────────────────────────────────────────

class MetaAnalyzer:
    """
    Meta Ads verisini Shopify verileriyle birleştirir,
    ROAS analizi, çapraz alarmlar ve optimizasyon önerileri üretir.
    """

    # Endüstri benchmark'ları (Alman kozmetik D2C)
    BENCHMARKS = {
        "roas_good":        3.0,   # iyi ROAS eşiği
        "roas_critical":    1.5,   # zarar/başabaş eşiği
        "ctr_good":         0.03,  # %3 CTR iyi
        "cpc_max":          1.00,  # €1 üzeri CPC pahalı
        "freq_max":         3.5,   # 3.5+ frekans = reklam yorgunluğu
        "cpa_max":          45.0,  # €45 üzeri CPA sürdürülemez
    }

    def __init__(self, raw_stats: list[dict], ad_sets: list[dict],
                 products_df: Optional[pd.DataFrame] = None):
        self.df = pd.DataFrame(raw_stats)
        self.df["date"] = pd.to_datetime(self.df["date"])
        self.ad_sets = pd.DataFrame(ad_sets)
        self.products_df = products_df

    # ── 1. KAMPANYA ÖZET METRİKLERİ ────────────────
    def campaign_summary(self) -> pd.DataFrame:
        """Kampanya bazında toplanmış KPI'lar"""
        agg = self.df.groupby(["campaign_id","campaign_name","product_sku"]).agg(
            spend       =("spend","sum"),
            impressions =("impressions","sum"),
            clicks      =("clicks","sum"),
            purchases   =("purchases","sum"),
            revenue     =("revenue","sum"),
            reach       =("reach","sum"),
            avg_freq    =("frequency","mean"),
        ).reset_index()

        agg["ctr"]  = (agg["clicks"]  / agg["impressions"].clip(1) * 100).round(3)
        agg["cpc"]  = (agg["spend"]   / agg["clicks"].clip(1)).round(2)
        agg["roas"] = (agg["revenue"] / agg["spend"].clip(0.01)).round(2)
        agg["cpa"]  = (agg["spend"]   / agg["purchases"].clip(1)).round(2)
        agg["spend"] = agg["spend"].round(2)
        agg["revenue"] = agg["revenue"].round(2)

        # Performans renk kodu
        def perf_label(roas):
            if roas >= self.BENCHMARKS["roas_good"]:    return "✅ İyi"
            if roas >= self.BENCHMARKS["roas_critical"]: return "⚠️ Orta"
            return "🔴 Kritik"

        agg["durum"] = agg["roas"].apply(perf_label)
        return agg.sort_values("roas", ascending=False).reset_index(drop=True)

    # ── 2. GÜNLÜK TREND ────────────────────────────
    def daily_trends(self) -> pd.DataFrame:
        """Tüm kampanyalar için günlük toplam harcama ve gelir"""
        daily = self.df.groupby("date").agg(
            spend    =("spend","sum"),
            revenue  =("revenue","sum"),
            clicks   =("clicks","sum"),
            purchases=("purchases","sum"),
        ).reset_index()
        daily["roas"] = (daily["revenue"] / daily["spend"].clip(0.01)).round(2)
        daily["spend_7d_avg"]   = daily["spend"].rolling(7, min_periods=1).mean().round(2)
        daily["revenue_7d_avg"] = daily["revenue"].rolling(7, min_periods=1).mean().round(2)
        return daily

    # ── 3. ÇAPRAZ ALARMLAR — ANA ÖZELLİK ──────────
    def cross_alarms(self) -> list[dict]:
        """
        Shopify stok + Meta Ads'i birleştiren çapraz alarmlar.
        Bu sistemin kalbi: stok/reklam senkronizasyon hatalarını tespit eder.
        """
        alarms = []
        summary = self.campaign_summary()

        for _, camp in summary.iterrows():
            sku = camp["product_sku"]

            # Stok bilgisini bul
            inventory = None
            if self.products_df is not None and not self.products_df.empty:
                prod_row = self.products_df[self.products_df["sku"] == sku]
                if not prod_row.empty:
                    inventory = int(prod_row.iloc[0]["inventory"])

            # ── ALARM 1: Stok tükenmek üzere ama reklam açık
            if inventory is not None and inventory < 15 and camp["spend"] > 5:
                severity = "critical" if inventory == 0 else "warning"
                alarms.append({
                    "alarm_type": "STOK_REKLAM_UYUMSUZLUĞU",
                    "severity":   severity,
                    "campaign":   camp["campaign_name"],
                    "sku":        sku,
                    "inventory":  inventory,
                    "daily_spend": round(camp["spend"] / 90, 2),
                    "title": f"{'Stok Tükendi' if inventory == 0 else 'Kritik Stok'} — Reklam Aktif",
                    "description": (
                        f"'{camp['campaign_name']}' kampanyası günde "
                        f"€{round(camp['spend']/90,1)} harcıyor ancak "
                        f"ürün stoğu {'tamamen tükenmiş' if inventory==0 else str(inventory)+' adet kalmış'}. "
                        f"Bu reklam bütçesi boşa gidiyor ve kullanıcı deneyimini bozuyor."
                    ),
                    "action": (
                        "Kampanyayı hemen duraklat veya bütçeyi stoklu ürünlere yönlendir. "
                        f"Acil tedarik siparişi ver. 30 adet stok altına inince otomatik duraklama kur."
                    ),
                    "estimated_waste_eur": round(camp["spend"] / 90 * 14, 0),  # 2 haftalık israf
                })

            # ── ALARM 2: Düşük ROAS (zarar eden kampanya)
            if camp["roas"] < self.BENCHMARKS["roas_critical"] and camp["spend"] > 50:
                alarms.append({
                    "alarm_type": "DÜŞÜK_ROAS",
                    "severity":   "critical",
                    "campaign":   camp["campaign_name"],
                    "sku":        sku,
                    "roas":       camp["roas"],
                    "spend":      camp["spend"],
                    "revenue":    camp["revenue"],
                    "title": f"Zarar Eden Kampanya — ROAS {camp['roas']}x",
                    "description": (
                        f"€{camp['spend']:.0f} harcandı, yalnızca €{camp['revenue']:.0f} gelir üretildi. "
                        f"ROAS {camp['roas']}x, başabaş noktası ({self.BENCHMARKS['roas_critical']}x) altında."
                    ),
                    "action": (
                        "Kampanya hedefleme kitlesini daralt (Broad → Lookalike). "
                        "Reklam kreatiflerini değiştir. 7 gün ROAS iyileşmezse durdur."
                    ),
                    "estimated_waste_eur": round(camp["spend"] - camp["revenue"] / 2, 0),
                })

            # ── ALARM 3: Reklam yorgunluğu (yüksek frekans)
            if camp["avg_freq"] > self.BENCHMARKS["freq_max"]:
                alarms.append({
                    "alarm_type": "REKLAM_YORGUNLUĞU",
                    "severity":   "warning",
                    "campaign":   camp["campaign_name"],
                    "sku":        sku,
                    "frequency":  round(camp["avg_freq"], 1),
                    "title": f"Reklam Yorgunluğu — Frekans {round(camp['avg_freq'],1)}x",
                    "description": (
                        f"Hedef kitle bu reklamı ortalama {round(camp['avg_freq'],1)} kez gördü. "
                        f"{self.BENCHMARKS['freq_max']}+ üzeri frekans CTR düşüşüne ve marka erozyonuna yol açar."
                    ),
                    "action": (
                        "Yeni reklam kreatifleri ekle (en az 3 farklı görsel/metin kombinasyonu). "
                        "Kitleyi genişlet veya Lookalike oranını artır (%1 → %3)."
                    ),
                    "estimated_waste_eur": None,
                })

            # ── ALARM 4: Yüksek CPC
            if camp["cpc"] > self.BENCHMARKS["cpc_max"] and camp["spend"] > 30:
                alarms.append({
                    "alarm_type": "YÜKSEK_CPC",
                    "severity":   "warning",
                    "campaign":   camp["campaign_name"],
                    "sku":        sku,
                    "cpc":        camp["cpc"],
                    "title": f"Yüksek Tıklama Maliyeti — €{camp['cpc']} CPC",
                    "description": (
                        f"Tıklama başı maliyet €{camp['cpc']}, benchmark €{self.BENCHMARKS['cpc_max']} üzerinde. "
                        f"Alman kozmetik sektöründe €0.40-0.80 arası CPC hedeflenmeli."
                    ),
                    "action": (
                        "Reklam alaka puanını artır (görseli ürünle eşleştir). "
                        "Manuel teklif stratejisini dene. Düşük CPC'li kitleyle A/B testi yap."
                    ),
                    "estimated_waste_eur": None,
                })

        # Öncelik sıralaması: critical önce
        alarms.sort(key=lambda x: (0 if x["severity"]=="critical" else 1, x["alarm_type"]))
        return alarms

    # ── 4. ROAS KARŞILAŞTIRMA ──────────────────────
    def roas_benchmark_analysis(self) -> dict:
        """ROAS dağılımı ve benchmark karşılaştırması"""
        summary = self.campaign_summary()
        total_spend   = summary["spend"].sum()
        total_revenue = summary["revenue"].sum()
        blended_roas  = round(total_revenue / max(total_spend, 0.01), 2)

        good     = len(summary[summary["roas"] >= self.BENCHMARKS["roas_good"]])
        moderate = len(summary[(summary["roas"] >= self.BENCHMARKS["roas_critical"]) &
                               (summary["roas"] < self.BENCHMARKS["roas_good"])])
        bad      = len(summary[summary["roas"] < self.BENCHMARKS["roas_critical"]])

        return {
            "total_spend":   round(total_spend, 2),
            "total_revenue": round(total_revenue, 2),
            "blended_roas":  blended_roas,
            "good_campaigns":    good,
            "moderate_campaigns": moderate,
            "bad_campaigns":     bad,
            "total_campaigns":   len(summary),
            "top_campaign":      summary.iloc[0]["campaign_name"] if len(summary) > 0 else "—",
            "top_roas":          summary.iloc[0]["roas"] if len(summary) > 0 else 0,
            "worst_campaign":    summary.iloc[-1]["campaign_name"] if len(summary) > 0 else "—",
            "worst_roas":        summary.iloc[-1]["roas"] if len(summary) > 0 else 0,
        }

    # ── 5. TAM RAPOR ───────────────────────────────
    def full_report(self) -> dict:
        print("📣 Meta Ads metrikleri hesaplanıyor...")
        return {
            "campaign_summary": self.campaign_summary(),
            "daily_trends":     self.daily_trends(),
            "cross_alarms":     self.cross_alarms(),
            "roas_analysis":    self.roas_benchmark_analysis(),
            "ad_sets":          self.ad_sets,
            "generated_at":     datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────
# ANA FONKSİYON (diğer modüllerle entegrasyon)
# ─────────────────────────────────────────────

def run_meta_analysis(
    meta_config: Optional[MetaConfig] = None,
    products_df: Optional[pd.DataFrame] = None,
    days: int = 90,
) -> dict:
    """
    Meta Ads pipeline:
    Veri Çek → Dönüştür → Analiz Et → Alarmları Üret
    """
    if meta_config is None:
        meta_config = MetaConfig(use_mock=True)

    client   = MetaAdsClient(meta_config)
    raw      = client.fetch_campaign_insights(days)
    ad_sets  = client.fetch_ad_sets()

    analyzer = MetaAnalyzer(raw, ad_sets, products_df)
    return analyzer.full_report()


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    console.print(Panel.fit(
        "📣 [bold magenta]Meta Ads Analiz Motoru[/bold magenta]\n"
        "   Adım 4: Reklam + Stok Çapraz Alarm Sistemi",
        border_style="magenta"
    ))

    report = run_meta_analysis()

    # Kampanya özeti
    console.print("\n[bold yellow]📊 Kampanya Performansı[/bold yellow]")
    t = Table(box=box.SIMPLE)
    for col in ["Kampanya","Harcama €","Gelir €","ROAS","CPC €","CTR %","Durum"]:
        t.add_column(col)
    for _, r in report["campaign_summary"].iterrows():
        t.add_row(
            r["campaign_name"][:35],
            f"{r['spend']:,.0f}",
            f"{r['revenue']:,.0f}",
            f"{r['roas']}x",
            f"{r['cpc']}",
            f"%{r['ctr']}",
            r["durum"],
        )
    console.print(t)

    # ROAS analizi
    ra = report["roas_analysis"]
    console.print(f"\n[bold yellow]🎯 ROAS Özeti[/bold yellow]")
    console.print(f"  Toplam Harcama  : €{ra['total_spend']:,.0f}")
    console.print(f"  Toplam Gelir    : €{ra['total_revenue']:,.0f}")
    console.print(f"  Blended ROAS    : {ra['blended_roas']}x")
    console.print(f"  En İyi          : {ra['top_campaign'][:40]} ({ra['top_roas']}x)")
    console.print(f"  En Kötü         : {ra['worst_campaign'][:40]} ({ra['worst_roas']}x)")

    # Çapraz alarmlar
    alarms = report["cross_alarms"]
    console.print(f"\n[bold red]🚨 Çapraz Alarmlar ({len(alarms)} adet)[/bold red]")
    for a in alarms:
        icon = "🔴" if a["severity"] == "critical" else "⚠️"
        console.print(f"\n  {icon} [{a['alarm_type']}] {a['title']}")
        console.print(f"     {a['description'][:120]}...")
        console.print(f"     → {a['action'][:100]}...")
        if a.get("estimated_waste_eur"):
            console.print(f"     💸 Tahmini israf: €{a['estimated_waste_eur']}")

    console.print(Panel.fit(
        "✅ [green]Adım 4 başarıyla tamamlandı![/green]\n"
        "   Sonraki: Adım 5 → Dashboard'a Meta Ads sekmesi entegrasyonu",
        border_style="green"
    ))
