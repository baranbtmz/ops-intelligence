"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 8: Stripe Ödeme Entegrasyonu

Kurulum:
pip3 install stripe
"""

import stripe
import json
import os
from datetime import datetime

# ─────────────────────────────────────────────
# STRIPE KONFİGÜRASYON — Secrets'tan oku
# ─────────────────────────────────────────────

def _get_secret(key: str, default: str = "") -> str:
    """Streamlit secrets veya environment variable'dan oku"""
    try:
        import streamlit as st
        return st.secrets.get(key, os.environ.get(key, default))
    except Exception:
        return os.environ.get(key, default)

STRIPE_SECRET_KEY      = _get_secret("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = _get_secret("STRIPE_PUBLISHABLE_KEY")

PRICE_IDS = {
    "starter": _get_secret("STRIPE_PRICE_STARTER", "price_1TRf3JG1DLQ2LxkRn0eLrytf"),
    "pro":     _get_secret("STRIPE_PRICE_PRO",     "price_1TRf3aG1DLQ2LxkRqDhmI9jg"),
}

if STRIPE_SECRET_KEY:
    stripe.api_key = STRIPE_SECRET_KEY


# ─────────────────────────────────────────────
# ÖDEME LİNKİ OLUŞTUR
# ─────────────────────────────────────────────

def create_checkout_session(
    plan: str,
    customer_email: str,
    success_url: str = "http://localhost:8501/?payment=success&plan={plan}",
    cancel_url:  str = "http://localhost:8501/?payment=cancelled",
) -> dict:
    """
    Stripe Checkout oturumu oluşturur.
    Müşteri bu URL'ye yönlendirilerek ödeme yapar.
    """
    price_id = PRICE_IDS.get(plan)
    if not price_id:
        return {"success": False, "error": f"Geçersiz plan: {plan}"}

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            mode="subscription",
            customer_email=customer_email,
            line_items=[{
                "price":    price_id,
                "quantity": 1,
            }],
            success_url=success_url.replace("{plan}", plan),
            cancel_url=cancel_url,
            metadata={
                "plan":  plan,
                "email": customer_email,
            },
            subscription_data={
                "metadata": {
                    "plan":  plan,
                    "email": customer_email,
                }
            }
        )
        return {
            "success":     True,
            "session_id":  session.id,
            "checkout_url": session.url,
            "plan":        plan,
            "amount":      "€29" if plan == "starter" else "€79",
        }

    except stripe.StripeError as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────
# ABONELİK KONTROL
# ─────────────────────────────────────────────

def get_subscription_status(customer_email: str) -> dict:
    """
    Müşterinin aktif aboneliğini kontrol eder.
    """
    try:
        customers = stripe.Customer.list(email=customer_email, limit=1)
        if not customers.data:
            return {"has_subscription": False, "plan": "free"}

        customer = customers.data[0]
        subs = stripe.Subscription.list(customer=customer.id, status="active", limit=1)

        if not subs.data:
            return {"has_subscription": False, "plan": "free"}

        sub = subs.data[0]
        price_id = sub["items"]["data"][0]["price"]["id"]

        plan = "free"
        for plan_key, pid in PRICE_IDS.items():
            if pid == price_id:
                plan = plan_key
                break

        return {
            "has_subscription": True,
            "plan":             plan,
            "status":           sub.status,
            "current_period_end": datetime.fromtimestamp(
                sub.current_period_end
            ).strftime("%d.%m.%Y"),
            "subscription_id":  sub.id,
        }

    except stripe.StripeError as e:
        return {"has_subscription": False, "plan": "free", "error": str(e)}


# ─────────────────────────────────────────────
# ABONELİĞİ İPTAL ET
# ─────────────────────────────────────────────

def cancel_subscription(subscription_id: str) -> dict:
    """Aboneliği dönem sonunda iptal eder."""
    try:
        sub = stripe.Subscription.modify(
            subscription_id,
            cancel_at_period_end=True,
        )
        return {
            "success": True,
            "message": f"Abonelik {datetime.fromtimestamp(sub.current_period_end).strftime('%d.%m.%Y')} tarihinde sona erecek.",
        }
    except stripe.StripeError as e:
        return {"success": False, "error": str(e)}


# ─────────────────────────────────────────────
# TEST
# ─────────────────────────────────────────────

if __name__ == "__main__":
    print("🔄 Stripe bağlantısı test ediliyor...")

    # Checkout session testi
    result = create_checkout_session(
        plan="starter",
        customer_email="test@example.com",
    )

    if result["success"]:
        print(f"✅ Checkout session oluşturuldu!")
        print(f"   Plan: {result['plan']} ({result['amount']}/ay)")
        print(f"   Ödeme URL: {result['checkout_url']}")
    else:
        print(f"❌ Hata: {result['error']}")

    # Pro plan testi
    result2 = create_checkout_session(
        plan="pro",
        customer_email="pro@example.com",
    )
    if result2["success"]:
        print(f"✅ Pro checkout: {result2['checkout_url'][:60]}...")
