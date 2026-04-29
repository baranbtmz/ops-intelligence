"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 7: Kullanıcı Girişi + Abonelik Sistemi

Kütüphaneler zaten kurulu:
- bcrypt (şifre hash)
- yaml (kullanıcı veritabanı)
"""

import bcrypt
import yaml
import json
import os
import hashlib
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


# ─────────────────────────────────────────────
# VERİ YAPILARI
# ─────────────────────────────────────────────

@dataclass
class Plan:
    name: str
    price_eur: float
    max_stores: int
    max_orders: int        # aylık analiz edilebilecek max sipariş
    ai_reports: bool
    pdf_export: bool
    meta_ads: bool
    support: str

@dataclass
class User:
    email: str
    name: str
    password_hash: str
    plan: str                          # "free" | "starter" | "pro"
    created_at: str
    stores: list = field(default_factory=list)   # Bağlı mağazalar
    analyses_this_month: int = 0
    last_analysis: str = ""
    is_active: bool = True


# ─────────────────────────────────────────────
# PLAN TANIMI
# ─────────────────────────────────────────────

PLANS = {
    "free": Plan(
        name="Ücretsiz",
        price_eur=0,
        max_stores=1,
        max_orders=100,
        ai_reports=False,
        pdf_export=False,
        meta_ads=False,
        support="Topluluk",
    ),
    "starter": Plan(
        name="Starter",
        price_eur=29,
        max_stores=2,
        max_orders=1000,
        ai_reports=True,
        pdf_export=True,
        meta_ads=False,
        support="E-posta",
    ),
    "pro": Plan(
        name="Pro",
        price_eur=79,
        max_stores=10,
        max_orders=10000,
        ai_reports=True,
        pdf_export=True,
        meta_ads=True,
        support="Öncelikli",
    ),
}


# ─────────────────────────────────────────────
# KULLANICI VERİTABANI (JSON dosyası)
# ─────────────────────────────────────────────

class UserDatabase:
    """
    Kullanıcıları JSON dosyasında saklar.
    Gerçek SaaS'ta PostgreSQL kullanılır — bu yapı aynı interface'i sağlar.
    """

    def __init__(self, db_path: str = "users.json"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """DB dosyası yoksa oluştur, demo kullanıcı ekle"""
        if not os.path.exists(self.db_path):
            demo_users = {
                "demo@opsint.com": {
                    "email":       "demo@opsint.com",
                    "name":        "Demo Kullanıcı",
                    "password_hash": self._hash("demo123"),
                    "plan":        "pro",
                    "created_at":  datetime.now().isoformat(),
                    "stores":      [],
                    "analyses_this_month": 0,
                    "last_analysis": "",
                    "is_active":   True,
                },
                "starter@test.com": {
                    "email":       "starter@test.com",
                    "name":        "Starter Test",
                    "password_hash": self._hash("test123"),
                    "plan":        "starter",
                    "created_at":  datetime.now().isoformat(),
                    "stores":      [],
                    "analyses_this_month": 0,
                    "last_analysis": "",
                    "is_active":   True,
                },
            }
            self._write(demo_users)

    def _read(self) -> dict:
        with open(self.db_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _hash(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def _verify(self, password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except Exception:
            return False

    # ── CRUD ────────────────────────────────

    def get_user(self, email: str) -> Optional[dict]:
        db = self._read()
        return db.get(email.lower().strip())

    def create_user(self, email: str, name: str, password: str, plan: str = "free") -> dict:
        db = self._read()
        email = email.lower().strip()

        if email in db:
            raise ValueError("Bu e-posta adresi zaten kayıtlı.")

        if len(password) < 6:
            raise ValueError("Şifre en az 6 karakter olmalı.")

        user = {
            "email":       email,
            "name":        name,
            "password_hash": self._hash(password),
            "plan":        plan,
            "created_at":  datetime.now().isoformat(),
            "stores":      [],
            "analyses_this_month": 0,
            "last_analysis": "",
            "is_active":   True,
        }
        db[email] = user
        self._write(db)
        return user

    def authenticate(self, email: str, password: str) -> Optional[dict]:
        """Doğruysa kullanıcı dict döndürür, yanlışsa None"""
        user = self.get_user(email)
        if not user:
            return None
        if not user.get("is_active", True):
            return None
        if self._verify(password, user["password_hash"]):
            return user
        return None

    def update_plan(self, email: str, plan: str):
        db = self._read()
        if email in db:
            db[email]["plan"] = plan
            self._write(db)

    def add_store(self, email: str, store: dict):
        db = self._read()
        if email in db:
            stores = db[email].get("stores", [])
            # Aynı domain varsa güncelle
            existing = [i for i, s in enumerate(stores) if s.get("domain") == store.get("domain")]
            if existing:
                stores[existing[0]] = store
            else:
                stores.append(store)
            db[email]["stores"] = stores
            self._write(db)

    def record_analysis(self, email: str):
        db = self._read()
        if email in db:
            db[email]["analyses_this_month"] += 1
            db[email]["last_analysis"] = datetime.now().isoformat()
            self._write(db)

    def check_plan_limit(self, email: str) -> dict:
        """Kullanıcının plan limitlerini kontrol et"""
        user  = self.get_user(email)
        plan  = PLANS.get(user["plan"], PLANS["free"])
        count = user.get("analyses_this_month", 0)

        return {
            "allowed":       count < plan.max_orders / 100,  # aylık analiz hakkı
            "plan":          plan,
            "used":          count,
            "limit":         plan.max_orders // 100,
            "can_ai":        plan.ai_reports,
            "can_pdf":       plan.pdf_export,
            "can_meta":      plan.meta_ads,
            "max_stores":    plan.max_stores,
            "store_count":   len(user.get("stores", [])),
        }


# ─────────────────────────────────────────────
# GLOBAL DB INSTANCE
# ─────────────────────────────────────────────

_db_instance = None

def get_db() -> UserDatabase:
    global _db_instance
    if _db_instance is None:
        _db_instance = UserDatabase("users.json")
    return _db_instance


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    db = UserDatabase("test_users.json")

    # Kayıt testi
    try:
        u = db.create_user("test@example.com", "Test User", "sifre123", "starter")
        print(f"✅ Kullanıcı oluşturuldu: {u['email']} — Plan: {u['plan']}")
    except ValueError as e:
        print(f"⚠️  {e}")

    # Giriş testi
    user = db.authenticate("test@example.com", "sifre123")
    print(f"✅ Giriş başarılı: {user['name']}" if user else "❌ Giriş başarısız")

    # Yanlış şifre
    user2 = db.authenticate("test@example.com", "yanlis")
    print(f"✅ Yanlış şifre reddedildi" if not user2 else "❌ Hata: kabul edildi")

    # Demo kullanıcı testi
    demo = db.authenticate("demo@opsint.com", "demo123")
    print(f"✅ Demo kullanıcı: {demo['name']} — {demo['plan']}" if demo else "❌")

    # Plan limiti
    limits = db.check_plan_limit("demo@opsint.com")
    plan = limits["plan"]
    print(f"✅ Plan: {plan.name} — €{plan.price_eur}/ay — AI: {plan.ai_reports} — PDF: {plan.pdf_export}")

    # Temizlik
    import os
    os.remove("test_users.json")
    print("✅ Tüm testler geçti!")
