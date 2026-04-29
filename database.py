"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 9: Supabase PostgreSQL Veritabanı

Kurulum:
pip3 install supabase
"""

import bcrypt
from datetime import datetime
from typing import Optional
from supabase import create_client, Client

# ─────────────────────────────────────────────
# SUPABASE BAĞLANTI
# ─────────────────────────────────────────────

SUPABASE_URL = "https://zyygkcknlcnoabwqbfij.supabase.co"
SUPABASE_KEY = "sb_secret_4qIdVT61d1laGr_XZeyeMA_Y2nyBpQS"

_client: Optional[Client] = None

def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ─────────────────────────────────────────────
# PLAN TANIMI (auth.py ile aynı)
# ─────────────────────────────────────────────

from dataclasses import dataclass

@dataclass
class Plan:
    name: str
    price_eur: float
    max_stores: int
    max_orders: int
    ai_reports: bool
    pdf_export: bool
    meta_ads: bool
    support: str

PLANS = {
    "free": Plan("Ücretsiz", 0, 1, 100, False, False, False, "Topluluk"),
    "starter": Plan("Starter", 29, 2, 1000, True, True, False, "E-posta"),
    "pro": Plan("Pro", 79, 10, 10000, True, True, True, "Öncelikli"),
}


# ─────────────────────────────────────────────
# VERİTABANI KURULUMU
# ─────────────────────────────────────────────

SETUP_SQL = """
-- Kullanıcılar tablosu
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    email       TEXT UNIQUE NOT NULL,
    name        TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    plan        TEXT DEFAULT 'free',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    stores      JSONB DEFAULT '[]',
    analyses_this_month INTEGER DEFAULT 0,
    last_analysis TIMESTAMPTZ,
    is_active   BOOLEAN DEFAULT TRUE
);

-- Analiz geçmişi tablosu
CREATE TABLE IF NOT EXISTS analyses (
    id          BIGSERIAL PRIMARY KEY,
    user_email  TEXT NOT NULL,
    shop_name   TEXT,
    health_score INTEGER,
    total_revenue FLOAT,
    findings    JSONB,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""


# ─────────────────────────────────────────────
# KULLANICI VERİTABANI (Supabase)
# ─────────────────────────────────────────────

class SupabaseUserDatabase:
    """
    Supabase PostgreSQL tabanlı kullanıcı yönetimi.
    auth.py'deki UserDatabase ile aynı interface.
    """

    def __init__(self):
        self.db = get_client()
        self._ensure_demo_user()

    def _hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

    def _ensure_demo_user(self):
        """Demo kullanıcı yoksa oluştur"""
        try:
            existing = self.db.table("users").select("email").eq(
                "email", "demo@opsint.com"
            ).execute()

            if not existing.data:
                self.db.table("users").insert({
                    "email":        "demo@opsint.com",
                    "name":         "Demo Kullanıcı",
                    "password_hash": self._hash("demo123"),
                    "plan":         "pro",
                    "stores":       [],
                    "analyses_this_month": 0,
                    "is_active":    True,
                }).execute()
        except Exception as e:
            print(f"Demo kullanıcı hatası: {e}")

    def get_user(self, email: str) -> Optional[dict]:
        try:
            result = self.db.table("users").select("*").eq(
                "email", email.lower().strip()
            ).execute()
            return result.data[0] if result.data else None
        except Exception:
            return None

    def create_user(self, email: str, name: str, password: str, plan: str = "free") -> dict:
        email = email.lower().strip()

        if self.get_user(email):
            raise ValueError("Bu e-posta adresi zaten kayıtlı.")
        if len(password) < 6:
            raise ValueError("Şifre en az 6 karakter olmalı.")

        user = {
            "email":        email,
            "name":         name,
            "password_hash": self._hash(password),
            "plan":         plan,
            "stores":       [],
            "analyses_this_month": 0,
            "is_active":    True,
        }
        result = self.db.table("users").insert(user).execute()
        return result.data[0]

    def authenticate(self, email: str, password: str) -> Optional[dict]:
        user = self.get_user(email)
        if not user or not user.get("is_active"):
            return None
        if self._verify(password, user["password_hash"]):
            return user
        return None

    def update_plan(self, email: str, plan: str):
        self.db.table("users").update({"plan": plan}).eq("email", email).execute()

    def add_store(self, email: str, store: dict):
        user = self.get_user(email)
        if not user:
            return
        stores = user.get("stores", []) or []
        existing = [i for i, s in enumerate(stores) if s.get("domain") == store.get("domain")]
        if existing:
            stores[existing[0]] = store
        else:
            stores.append(store)
        self.db.table("users").update({"stores": stores}).eq("email", email).execute()

    def record_analysis(self, email: str, analysis_data: dict = None):
        """Analizi kaydet ve sayacı artır"""
        user = self.get_user(email)
        if not user:
            return

        # Sayacı artır
        self.db.table("users").update({
            "analyses_this_month": (user.get("analyses_this_month") or 0) + 1,
            "last_analysis": datetime.now().isoformat(),
        }).eq("email", email).execute()

        # Analiz geçmişine kaydet
        if analysis_data:
            try:
                analysis = analysis_data.get("analysis", {})
                metrics  = analysis_data.get("metrics", {})
                rev = metrics.get("revenue", {})
                self.db.table("analyses").insert({
                    "user_email":   email,
                    "shop_name":    analysis_data.get("shop_name", ""),
                    "health_score": analysis.get("overall_health_score", 0),
                    "total_revenue": rev.get("total_revenue", 0),
                    "findings":     analysis.get("findings", []),
                }).execute()
            except Exception as e:
                print(f"Analiz kayıt hatası: {e}")

    def get_analysis_history(self, email: str, limit: int = 10) -> list:
        """Kullanıcının analiz geçmişini getir"""
        try:
            result = self.db.table("analyses").select(
                "id,shop_name,health_score,total_revenue,created_at"
            ).eq("user_email", email).order(
                "created_at", desc=True
            ).limit(limit).execute()
            return result.data
        except Exception:
            return []

    def check_plan_limit(self, email: str) -> dict:
        user  = self.get_user(email)
        plan  = PLANS.get(user["plan"], PLANS["free"])
        count = user.get("analyses_this_month", 0) or 0

        return {
            "allowed":    count < plan.max_orders / 100,
            "plan":       plan,
            "used":       count,
            "limit":      plan.max_orders // 100,
            "can_ai":     plan.ai_reports,
            "can_pdf":    plan.pdf_export,
            "can_meta":   plan.meta_ads,
            "max_stores": plan.max_stores,
            "store_count": len(user.get("stores", []) or []),
        }


# ─────────────────────────────────────────────
# GLOBAL INSTANCE
# ─────────────────────────────────────────────

_db_instance = None

def get_db():
    global _db_instance
    if _db_instance is None:
        try:
            _db_instance = SupabaseUserDatabase()
        except Exception:
            # Supabase bağlantısı yoksa JSON'a geri dön
            from auth import UserDatabase
            _db_instance = UserDatabase("users.json")
    return _db_instance


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🔄 Supabase bağlantısı test ediliyor...")
    try:
        db = SupabaseUserDatabase()

        # Demo kullanıcı testi
        user = db.authenticate("demo@opsint.com", "demo123")
        if user:
            print(f"✅ Demo giriş: {user['name']} — {user['plan']}")
        else:
            print("❌ Demo giriş başarısız")

        # Yeni kullanıcı testi
        try:
            new_user = db.create_user("supatest@test.com", "Test User", "test123", "starter")
            print(f"✅ Yeni kullanıcı: {new_user['email']}")
        except ValueError as e:
            print(f"⚠️  {e}")

        # Plan limiti testi
        limits = db.check_plan_limit("demo@opsint.com")
        print(f"✅ Plan: {limits['plan'].name} | AI: {limits['can_ai']} | PDF: {limits['can_pdf']}")

        print("✅ Supabase entegrasyonu başarılı!")

    except Exception as e:
        print(f"❌ Hata: {e}")
