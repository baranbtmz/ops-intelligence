"""
E-Ticaret Operasyonel Analiz Sistemi
Adım 5: Müşteri Onboarding + Gerçek API Bağlantısı

Bu modül:
- Müşterinin Shopify ve Meta Ads bilgilerini alır
- Bağlantıyı test eder (hata varsa açıklar)
- Gerçek veriyle analizi başlatır
- Bağlantı bilgilerini şifreli saklar (session bazlı)
"""

import requests
import json
import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional


# ─────────────────────────────────────────────
# BAĞLANTI TEST SONUCU
# ─────────────────────────────────────────────

@dataclass
class ConnectionResult:
    success: bool
    platform: str          # "shopify" | "meta"
    message: str           # Kullanıcıya gösterilecek mesaj
    detail: str = ""       # Teknik detay (hata ayıklama için)
    shop_name: str = ""    # Shopify mağaza adı (başarılıysa)
    order_count: int = 0   # Sipariş sayısı (önizleme)
    ad_account: str = ""   # Meta hesap adı


# ─────────────────────────────────────────────
# SHOPIFY BAĞLANTI TESTİ
# ─────────────────────────────────────────────

def test_shopify_connection(shop_domain: str, access_token: str) -> ConnectionResult:
    """
    Shopify API bağlantısını test eder.
    Başarılıysa mağaza adını ve sipariş sayısını döndürür.
    """

    # Domain temizleme
    domain = shop_domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "")
    if not domain.endswith(".myshopify.com"):
        if "." not in domain:
            domain = f"{domain}.myshopify.com"

    url = f"https://{domain}/admin/api/2024-01/shop.json"
    headers = {
        "X-Shopify-Access-Token": access_token.strip(),
        "Content-Type": "application/json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)

        if resp.status_code == 200:
            shop_data = resp.json().get("shop", {})
            shop_name = shop_data.get("name", domain)

            # Sipariş sayısını al (önizleme)
            orders_url = f"https://{domain}/admin/api/2024-01/orders/count.json?status=any"
            orders_resp = requests.get(orders_url, headers=headers, timeout=10)
            order_count = orders_resp.json().get("count", 0) if orders_resp.status_code == 200 else 0

            return ConnectionResult(
                success=True,
                platform="shopify",
                message=f"✅ Bağlantı başarılı!",
                shop_name=shop_name,
                order_count=order_count,
                detail=f"Domain: {domain}",
            )

        elif resp.status_code == 401:
            return ConnectionResult(
                success=False,
                platform="shopify",
                message="❌ Access Token geçersiz",
                detail="401 Unauthorized — Token'ı kontrol et, 'Reveal token once' ile kopyaladığından emin ol.",
            )
        elif resp.status_code == 404:
            return ConnectionResult(
                success=False,
                platform="shopify",
                message="❌ Mağaza bulunamadı",
                detail=f"404 Not Found — '{domain}' adresi geçersiz. myshopify.com domain'ini doğru girdiğinden emin ol.",
            )
        else:
            return ConnectionResult(
                success=False,
                platform="shopify",
                message=f"❌ Bağlantı hatası (HTTP {resp.status_code})",
                detail=resp.text[:200],
            )

    except requests.exceptions.ConnectionError:
        return ConnectionResult(
            success=False,
            platform="shopify",
            message="❌ Sunucuya ulaşılamıyor",
            detail="İnternet bağlantını kontrol et veya domain adresini doğrula.",
        )
    except requests.exceptions.Timeout:
        return ConnectionResult(
            success=False,
            platform="shopify",
            message="❌ Bağlantı zaman aşımına uğradı",
            detail="Shopify sunucusu yanıt vermedi. Tekrar dene.",
        )
    except Exception as e:
        return ConnectionResult(
            success=False,
            platform="shopify",
            message="❌ Beklenmeyen hata",
            detail=str(e),
        )


# ─────────────────────────────────────────────
# META ADS BAĞLANTI TESTİ
# ─────────────────────────────────────────────

def test_meta_connection(access_token: str, ad_account_id: str) -> ConnectionResult:
    """
    Meta Graph API bağlantısını test eder.
    """

    token = access_token.strip()
    account = ad_account_id.strip()

    # act_ prefix kontrolü
    if account and not account.startswith("act_"):
        account = f"act_{account}"

    # Önce token geçerliliğini test et
    me_url = f"https://graph.facebook.com/v18.0/me?access_token={token}"

    try:
        me_resp = requests.get(me_url, timeout=10)

        if me_resp.status_code != 200:
            error = me_resp.json().get("error", {})
            return ConnectionResult(
                success=False,
                platform="meta",
                message="❌ Meta Access Token geçersiz",
                detail=error.get("message", me_resp.text[:200]),
            )

        # Hesap adını al
        if account:
            acc_url = (
                f"https://graph.facebook.com/v18.0/{account}"
                f"?fields=name,currency,account_status"
                f"&access_token={token}"
            )
            acc_resp = requests.get(acc_url, timeout=10)

            if acc_resp.status_code == 200:
                acc_data = acc_resp.json()
                status_map = {1: "Aktif", 2: "Devre Dışı", 3: "Askıya Alındı"}
                acc_status = status_map.get(acc_data.get("account_status", 0), "Bilinmiyor")

                return ConnectionResult(
                    success=True,
                    platform="meta",
                    message="✅ Meta Ads bağlantısı başarılı!",
                    ad_account=acc_data.get("name", account),
                    detail=f"Hesap Durumu: {acc_status} | Para Birimi: {acc_data.get('currency','?')}",
                )
            else:
                error = acc_resp.json().get("error", {})
                return ConnectionResult(
                    success=False,
                    platform="meta",
                    message="❌ Ad Account ID geçersiz",
                    detail=error.get("message", "Hesap bulunamadı. 'act_' ile başlayan ID'yi kontrol et."),
                )
        else:
            # Hesap ID girilmemişse sadece token doğrula
            user_data = me_resp.json()
            return ConnectionResult(
                success=True,
                platform="meta",
                message="✅ Token geçerli (Ad Account ID girilmedi)",
                detail=f"Kullanıcı: {user_data.get('name','?')}",
            )

    except requests.exceptions.Timeout:
        return ConnectionResult(
            success=False,
            platform="meta",
            message="❌ Bağlantı zaman aşımına uğradı",
            detail="Meta sunucusu yanıt vermedi. Tekrar dene.",
        )
    except Exception as e:
        return ConnectionResult(
            success=False,
            platform="meta",
            message="❌ Beklenmeyen hata",
            detail=str(e),
        )


# ─────────────────────────────────────────────
# TOKEN KILAVUZU (Müşteriye gösterilecek)
# ─────────────────────────────────────────────

SHOPIFY_GUIDE = """
**Shopify Access Token Nasıl Alınır?**

1. Shopify admin paneline gir → `mağazaadın.myshopify.com/admin`
2. Sol altta **Settings** → **Apps and sales channels**
3. Sağ üstte **"Develop apps"** butonuna tıkla
4. **"Allow custom app development"** → Onayla
5. **"Create an app"** → App adı: `OPS Intelligence` → **Create**
6. **"Configure Admin API scopes"** sekmesine tıkla
7. Şu izinleri seç ve **Save**:
   - ✅ `read_orders`
   - ✅ `read_products`  
   - ✅ `read_inventory`
8. **"Install app"** → **"Install"**
9. **"Admin API access token"** → **"Reveal token once"** → Kopyala
"""

META_GUIDE = """
**Meta Ads Access Token Nasıl Alınır?**

1. [business.facebook.com](https://business.facebook.com) → Sol menü **Business Settings**
2. **Users** → **System Users** → **Add**
3. Sistem kullanıcısı adı: `OPS Intelligence` → Rol: **Admin** → **Create system user**
4. **"Generate New Token"** → Uygulama seç → Şu izinleri seç:
   - ✅ `ads_read`
   - ✅ `ads_management`
5. Token'ı kopyala

**Ad Account ID Nerede?**
- [business.facebook.com](https://business.facebook.com) → **Ad Accounts**
- `act_` ile başlayan numara (örn: `act_123456789`)
"""
