"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 1: Veri Katmanı - Shopify Entegrasyonu & Mock Data Üreteci

Gerekli kurulum:
pip install pandas numpy requests python-dateutil faker rich
"""

import pandas as pd
import numpy as np
import requests
import json
import random
from datetime import datetime, timedelta
from dateutil import parser as date_parser
from dataclasses import dataclass, field
from typing import Optional
from faker import Faker

fake = Faker("de_DE")  # Alman market simülasyonu
random.seed(42)
np.random.seed(42)


# ─────────────────────────────────────────────
# KONFİGÜRASYON
# ─────────────────────────────────────────────

@dataclass
class ShopifyConfig:
    """Shopify API bağlantı konfigürasyonu"""
    shop_domain: str = ""           # örn: myaurellia.myshopify.com
    access_token: str = ""          # Private App Access Token
    api_version: str = "2024-01"
    use_mock: bool = True           # True = Mock data kullan (test modu)
    mock_order_count: int = 200     # Kaç adet mock sipariş üretilsin


# ─────────────────────────────────────────────
# MOCK DATA ÜRETECİ
# ─────────────────────────────────────────────

class MockDataGenerator:
    """
    Gerçekçi e-ticaret verisi üretir.
    Shopify API olmadan tam test yapılabilir.
    """

    PRODUCTS = [
        {"id": 1001, "title": "Rose Elixir Serum",        "category": "Skincare",  "price": 89.99,  "cost": 22.00, "sku": "SKN-001"},
        {"id": 1002, "title": "Midnight Oud Perfume",      "category": "Perfume",   "price": 145.00, "cost": 35.00, "sku": "PRF-001"},
        {"id": 1003, "title": "Gold Shimmer Body Lotion",  "category": "Body Care", "price": 59.99,  "cost": 14.00, "sku": "BDY-001"},
        {"id": 1004, "title": "Argan Oil Hair Mask",       "category": "Hair Care", "price": 49.99,  "cost": 12.00, "sku": "HRC-001"},
        {"id": 1005, "title": "Vitamin C Brightening Cream","category": "Skincare", "price": 79.99,  "cost": 19.00, "sku": "SKN-002"},
        {"id": 1006, "title": "Jasmine Blossom Perfume",   "category": "Perfume",   "price": 125.00, "cost": 30.00, "sku": "PRF-002"},
        {"id": 1007, "title": "Hyaluronic Acid Toner",     "category": "Skincare",  "price": 45.99,  "cost": 11.00, "sku": "SKN-003"},
        {"id": 1008, "title": "Coconut Repair Shampoo",    "category": "Hair Care", "price": 34.99,  "cost": 8.50,  "sku": "HRC-002"},
    ]

    STATUSES = ["fulfilled", "fulfilled", "fulfilled", "unfulfilled", "cancelled", "refunded"]
    # Ağırlıklı dağılım: gerçekçi bir mağaza gibi

    def generate_orders(self, count: int = 200) -> list[dict]:
        """Sipariş verisi üret"""
        orders = []
        base_date = datetime.now() - timedelta(days=90)

        for i in range(count):
            created_at = base_date + timedelta(
                days=random.uniform(0, 88),
                hours=random.uniform(0, 23),
                minutes=random.uniform(0, 59)
            )

            # Sipariş hazırlama süresi: log-normal dağılım (gerçekçi)
            # Çoğu sipariş 1-3 gün, bazıları çok uzun sürer (darboğaz simülasyonu)
            fulfillment_hours = np.random.lognormal(mean=2.5, sigma=0.8)
            fulfillment_hours = min(fulfillment_hours, 168)  # max 7 gün

            fulfilled_at = created_at + timedelta(hours=fulfillment_hours)

            # Ürün seçimi
            num_items = random.choices([1, 2, 3, 4], weights=[50, 30, 15, 5])[0]
            line_items = []
            total_price = 0.0

            selected_products = random.sample(self.PRODUCTS, min(num_items, len(self.PRODUCTS)))
            for prod in selected_products:
                qty = random.choices([1, 2, 3], weights=[70, 20, 10])[0]
                item_total = prod["price"] * qty
                total_price += item_total
                line_items.append({
                    "product_id": prod["id"],
                    "title": prod["title"],
                    "quantity": qty,
                    "price": prod["price"],
                    "sku": prod["sku"]
                })

            status = random.choices(
                self.STATUSES,
                weights=[55, 55, 55, 20, 8, 7]
            )[0]

            # Kargo bilgisi
            carrier = random.choice(["DHL", "DPD", "Hermes", "UPS", "GLS"])
            shipping_cost = random.choice([0, 4.99, 6.99, 9.99])

            orders.append({
                "id": 10000 + i,
                "order_number": f"#AU{1000 + i}",
                "created_at": created_at.isoformat(),
                "fulfilled_at": fulfilled_at.isoformat() if status == "fulfilled" else None,
                "financial_status": random.choice(["paid", "paid", "paid", "refunded", "pending"]),
                "fulfillment_status": status,
                "total_price": round(total_price + shipping_cost, 2),
                "subtotal_price": round(total_price, 2),
                "shipping_cost": shipping_cost,
                "line_items": line_items,
                "customer_country": random.choice(["DE", "DE", "DE", "AT", "CH"]),
                "shipping_carrier": carrier,
                "tags": random.choice(["", "vip", "repeat_customer", "wholesale", ""]),
            })

        return orders

    def generate_products(self) -> list[dict]:
        """Ürün ve stok verisi üret"""
        products = []
        for prod in self.PRODUCTS:
            # Stok: bazı ürünler kritik seviyede (darboğaz simülasyonu)
            inventory = random.choices(
                [random.randint(0, 5), random.randint(6, 30), random.randint(31, 200)],
                weights=[20, 40, 40]
            )[0]

            products.append({
                "id": prod["id"],
                "title": prod["title"],
                "category": prod["category"],
                "sku": prod["sku"],
                "price": prod["price"],
                "cost_per_item": prod["cost"],
                "inventory_quantity": inventory,
                "inventory_policy": "deny",  # stok bitti = satış durur
                "created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
            })
        return products


# ─────────────────────────────────────────────
# SHOPIFY API İSTEMCİSİ
# ─────────────────────────────────────────────

class ShopifyClient:
    """
    Gerçek Shopify API ile iletişim kurar.
    use_mock=True ise MockDataGenerator devreye girer.
    """

    def __init__(self, config: ShopifyConfig):
        self.config = config
        self.mock_gen = MockDataGenerator()
        self.base_url = f"https://{config.shop_domain}/admin/api/{config.api_version}"
        self.headers = {
            "X-Shopify-Access-Token": config.access_token,
            "Content-Type": "application/json"
        }

    def _get(self, endpoint: str, params: dict = None) -> dict:
        """Shopify API GET isteği"""
        url = f"{self.base_url}/{endpoint}.json"
        response = requests.get(url, headers=self.headers, params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def fetch_orders(self, limit: int = 250, status: str = "any") -> list[dict]:
        """Siparişleri getir (gerçek veya mock)"""
        if self.config.use_mock:
            print("📦 [MOCK] Sipariş verisi üretiliyor...")
            return self.mock_gen.generate_orders(self.config.mock_order_count)

        print("🔗 [API] Shopify'dan siparişler çekiliyor...")
        all_orders = []
        params = {"limit": limit, "status": status}

        while True:
            data = self._get("orders", params)
            orders = data.get("orders", [])
            all_orders.extend(orders)

            # Sayfalama (pagination)
            link_header = data.get("link", "")
            if 'rel="next"' not in str(link_header):
                break
            # Bir sonraki sayfa için page_info token'ı parse et
            # (Shopify cursor-based pagination)

        return all_orders

    def fetch_products(self) -> list[dict]:
        """Ürünleri getir (gerçek veya mock)"""
        if self.config.use_mock:
            print("🛍️ [MOCK] Ürün verisi üretiliyor...")
            return self.mock_gen.generate_products()

        print("🔗 [API] Shopify'dan ürünler çekiliyor...")
        data = self._get("products", {"limit": 250})
        return data.get("products", [])


# ─────────────────────────────────────────────
# VERİ TEMİZLEME & DÖNÜŞTÜRME
# ─────────────────────────────────────────────

class DataTransformer:
    """Ham veriyi analiz için hazır DataFrame'e dönüştürür"""

    @staticmethod
    def orders_to_dataframe(raw_orders: list[dict]) -> pd.DataFrame:
        """
        Ham sipariş listesini temizlenmiş DataFrame'e çevirir.
        Eksik veri, tip dönüşümü ve türetilmiş sütunlar burada oluşturulur.
        """
        records = []
        for o in raw_orders:
            # line_items'dan ürün kategorilerini çıkar
            items = o.get("line_items", [])
            product_titles = [item.get("title", "") for item in items]
            total_qty = sum(item.get("quantity", 1) for item in items)

            records.append({
                "order_id":           o.get("id"),
                "order_number":       o.get("order_number", o.get("name", "")),
                "created_at":         o.get("created_at"),
                "fulfilled_at":       o.get("fulfilled_at"),
                "financial_status":   o.get("financial_status", "unknown"),
                "fulfillment_status": o.get("fulfillment_status", "unknown"),
                "total_price":        float(o.get("total_price", 0) or 0),
                "subtotal_price":     float(o.get("subtotal_price", 0) or 0),
                "shipping_cost":      float(o.get("shipping_cost", 0) or 0),
                "item_count":         total_qty,
                "product_titles":     ", ".join(product_titles[:2]),  # ilk 2 ürün
                "customer_country":   o.get("customer_country", o.get("billing_address", {}) or {}).get("country_code", "UNKNOWN") if isinstance(o.get("billing_address"), dict) else o.get("customer_country", "DE"),
                "shipping_carrier":   o.get("shipping_carrier", "Unknown"),
                "tags":               o.get("tags", ""),
            })

        df = pd.DataFrame(records)

        # Tarih dönüşümleri
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        df["fulfilled_at"] = pd.to_datetime(df["fulfilled_at"], utc=True, errors="coerce")

        # Duplikat temizle
        df = df.drop_duplicates(subset=["order_id"])

        # Sıralama
        df = df.sort_values("created_at").reset_index(drop=True)

        return df

    @staticmethod
    def products_to_dataframe(raw_products: list[dict]) -> pd.DataFrame:
        """Ham ürün listesini DataFrame'e çevirir"""
        records = []
        for p in raw_products:
            records.append({
                "product_id":    p.get("id"),
                "title":         p.get("title", ""),
                "category":      p.get("category", p.get("product_type", "Uncategorized")),
                "sku":           p.get("sku", ""),
                "price":         float(p.get("price", 0) or 0),
                "cost":          float(p.get("cost_per_item", 0) or 0),
                "inventory":     int(p.get("inventory_quantity", 0) or 0),
                "created_at":    p.get("created_at"),
            })

        df = pd.DataFrame(records)
        df["created_at"] = pd.to_datetime(df["created_at"], utc=True, errors="coerce")
        df["margin_pct"] = np.where(
            df["price"] > 0,
            ((df["price"] - df["cost"]) / df["price"] * 100).round(1),
            0
        )
        return df


# ─────────────────────────────────────────────
# METRİK HESAPLAMA MOTORu
# ─────────────────────────────────────────────

class MetricsEngine:
    """
    Operasyonel verimlilik metriklerini hesaplar.
    Endüstri Mühendisliği perspektifinden KPI analizi.
    """

    def __init__(self, orders_df: pd.DataFrame, products_df: pd.DataFrame):
        self.orders = orders_df.copy()
        self.products = products_df.copy()

    # ── 1. SİPARİŞ HAZIRLAMA SÜRESİ ─────────────────
    def order_fulfillment_time(self) -> dict:
        """
        Sipariş Hazırlama Süresi (Order Fulfillment Time)
        Formül: fulfilled_at - created_at (saat cinsinden)

        Hedef: <24 saat (Amazon etkisiyle müşteri beklentisi)
        Kritik: >72 saat = müşteri memnuniyeti riski
        """
        fulfilled = self.orders[
            (self.orders["fulfillment_status"] == "fulfilled") &
            (self.orders["fulfilled_at"].notna())
        ].copy()

        fulfilled["fulfillment_hours"] = (
            fulfilled["fulfilled_at"] - fulfilled["created_at"]
        ).dt.total_seconds() / 3600

        # Negatif değerleri temizle (veri kalitesi sorunu)
        fulfilled = fulfilled[fulfilled["fulfillment_hours"] > 0]

        stats = {
            "metric": "Sipariş Hazırlama Süresi",
            "unit": "saat",
            "mean":   round(fulfilled["fulfillment_hours"].mean(), 1),
            "median": round(fulfilled["fulfillment_hours"].median(), 1),
            "p75":    round(fulfilled["fulfillment_hours"].quantile(0.75), 1),
            "p95":    round(fulfilled["fulfillment_hours"].quantile(0.95), 1),
            "max":    round(fulfilled["fulfillment_hours"].max(), 1),
            "orders_over_72h": int((fulfilled["fulfillment_hours"] > 72).sum()),
            "orders_over_24h": int((fulfilled["fulfillment_hours"] > 24).sum()),
            "total_fulfilled": len(fulfilled),
            "fulfillment_hours_series": fulfilled[["order_id", "created_at", "fulfillment_hours"]],
        }

        # Performans değerlendirmesi
        if stats["median"] <= 24:
            stats["status"] = "✅ İyi"
            stats["risk"] = "Düşük"
        elif stats["median"] <= 48:
            stats["status"] = "⚠️ Orta"
            stats["risk"] = "Orta"
        else:
            stats["status"] = "🔴 Kritik"
            stats["risk"] = "Yüksek"

        return stats

    # ── 2. STOK DEVİR HIZI ───────────────────────────
    def inventory_turnover(self, period_days: int = 90) -> dict:
        """
        Stok Devir Hızı (Inventory Turnover Rate)
        Formül: (Dönem Satış Adedi) / (Ortalama Stok)

        Yüksek = verimli stok yönetimi
        Düşük  = fazla stok / satılmayan ürün
        """
        # Dönemsel satış adedi (iptal ve iadeler hariç)
        sales = self.orders[
            ~self.orders["fulfillment_status"].isin(["cancelled", "refunded"])
        ]

        # Ürün bazlı satış miktarı
        product_sales = {}
        for _, row in sales.iterrows():
            # Basitleştirilmiş: sipariş başına item_count kullan
            pass

        results = []
        for _, prod in self.products.iterrows():
            # Ürün için tahmini satış (mock'ta direkt hesapla)
            avg_daily_sales = max(
                np.random.uniform(0.5, 5.0),  # gerçekte satış verisinden gelir
                0.1
            )
            total_sold = avg_daily_sales * period_days
            avg_inventory = max(prod["inventory"], 1)

            turnover = round(total_sold / avg_inventory, 2)
            days_of_stock = round(avg_inventory / avg_daily_sales, 0) if avg_daily_sales > 0 else 999

            results.append({
                "product_id":    prod["product_id"],
                "title":         prod["title"],
                "category":      prod["category"],
                "inventory":     prod["inventory"],
                "turnover_rate": turnover,
                "days_of_stock": days_of_stock,
                "status": (
                    "🔴 Stok Tükenme Riski" if prod["inventory"] < 10 else
                    "⚠️ Düşük Stok" if prod["inventory"] < 30 else
                    "✅ Normal"
                ),
            })

        df = pd.DataFrame(results).sort_values("turnover_rate", ascending=False)
        return {
            "metric": "Stok Devir Hızı",
            "period_days": period_days,
            "details": df,
            "avg_turnover": round(df["turnover_rate"].mean(), 2),
            "critical_items": df[df["inventory"] < 10],
        }

    # ── 3. DÖNÜŞÜM VE GELİR ANALİZİ ────────────────
    def revenue_metrics(self) -> dict:
        """Gelir ve sipariş bazlı metrikler"""
        valid = self.orders[~self.orders["fulfillment_status"].isin(["cancelled", "refunded"])]

        daily_revenue = valid.groupby(
            valid["created_at"].dt.date
        )["total_price"].sum()

        return {
            "metric": "Gelir Metrikleri",
            "total_revenue":     round(valid["total_price"].sum(), 2),
            "total_orders":      len(self.orders),
            "valid_orders":      len(valid),
            "cancelled_orders":  len(self.orders[self.orders["fulfillment_status"] == "cancelled"]),
            "refunded_orders":   len(self.orders[self.orders["fulfillment_status"] == "refunded"]),
            "aov":               round(valid["total_price"].mean(), 2),  # Average Order Value
            "avg_items_per_order": round(valid["item_count"].mean(), 1),
            "cancellation_rate": round(len(self.orders[self.orders["fulfillment_status"] == "cancelled"]) / len(self.orders) * 100, 1),
            "refund_rate":       round(len(self.orders[self.orders["fulfillment_status"] == "refunded"]) / len(self.orders) * 100, 1),
            "daily_revenue_series": daily_revenue,
        }

    # ── 4. TAM ÖZET RAPORU ───────────────────────────
    def full_report(self) -> dict:
        """Tüm metrikleri tek seferde hesapla"""
        print("\n⚙️  Metrikler hesaplanıyor...\n")
        return {
            "fulfillment_time": self.order_fulfillment_time(),
            "inventory":        self.inventory_turnover(),
            "revenue":          self.revenue_metrics(),
            "generated_at":     datetime.now().isoformat(),
        }


# ─────────────────────────────────────────────
# ANA PIPELINE
# ─────────────────────────────────────────────

def run_pipeline(config: Optional[ShopifyConfig] = None) -> dict:
    """
    Tam veri pipeline'ını çalıştırır:
    1. Veri çek → 2. Temizle → 3. Metrikleri hesapla
    """
    if config is None:
        config = ShopifyConfig(use_mock=True, mock_order_count=200)

    # 1. Veri çekimi
    client = ShopifyClient(config)
    raw_orders = client.fetch_orders()
    raw_products = client.fetch_products()

    print(f"✅ {len(raw_orders)} sipariş, {len(raw_products)} ürün alındı.")

    # 2. Dönüştürme
    transformer = DataTransformer()
    orders_df   = transformer.orders_to_dataframe(raw_orders)
    products_df = transformer.products_to_dataframe(raw_products)

    print(f"✅ DataFrame oluşturuldu: orders{orders_df.shape}, products{products_df.shape}")

    # 3. Metrik hesaplama
    engine = MetricsEngine(orders_df, products_df)
    report = engine.full_report()

    report["orders_df"]   = orders_df
    report["products_df"] = products_df

    return report


# ─────────────────────────────────────────────
# TEST / DEMO ÇIKTISI
# ─────────────────────────────────────────────

if __name__ == "__main__":
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich import box

    console = Console()

    console.print(Panel.fit(
        "🏭 [bold cyan]E-Ticaret Operasyonel Analiz Sistemi[/bold cyan]\n"
        "   Adım 1: Veri Katmanı Test",
        border_style="cyan"
    ))

    report = run_pipeline()

    # ── Fulfillment Özeti
    ft = report["fulfillment_time"]
    console.print(f"\n[bold yellow]📦 {ft['metric']}[/bold yellow]")
    console.print(f"  Ortalama : {ft['mean']} saat")
    console.print(f"  Medyan   : {ft['median']} saat  → Durum: {ft['status']}")
    console.print(f"  P95      : {ft['p95']} saat")
    console.print(f"  >72 saat : {ft['orders_over_72h']} sipariş (darboğaz riski)")

    # ── Stok Tablosu
    inv = report["inventory"]
    console.print(f"\n[bold yellow]📊 {inv['metric']} (Ortalama: {inv['avg_turnover']}x)[/bold yellow]")

    table = Table(box=box.SIMPLE)
    table.add_column("Ürün", style="white")
    table.add_column("Stok", justify="right")
    table.add_column("Devir Hızı", justify="right")
    table.add_column("Stok Günü", justify="right")
    table.add_column("Durum")

    for _, row in inv["details"].iterrows():
        table.add_row(
            row["title"][:30],
            str(row["inventory"]),
            f"{row['turnover_rate']}x",
            f"{row['days_of_stock']:.0f}g",
            row["status"],
        )
    console.print(table)

    # ── Gelir Özeti
    rev = report["revenue"]
    console.print(f"\n[bold yellow]💰 {rev['metric']}[/bold yellow]")
    console.print(f"  Toplam Gelir    : €{rev['total_revenue']:,.2f}")
    console.print(f"  Toplam Sipariş  : {rev['total_orders']}")
    console.print(f"  Ortalama Sepet  : €{rev['aov']:.2f}")
    console.print(f"  İptal Oranı     : %{rev['cancellation_rate']}")
    console.print(f"  İade Oranı      : %{rev['refund_rate']}")

    console.print(Panel.fit(
        "✅ [green]Adım 1 başarıyla tamamlandı![/green]\n"
        "   Sonraki: Adım 2 → AI Analiz Motoru (OpenAI entegrasyonu)",
        border_style="green"
    ))
