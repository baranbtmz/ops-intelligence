"""
OPS Intelligence — FastAPI Backend
Railway'de çalışır, Netlify frontend'ine API sağlar.

Kurulum:
pip install fastapi uvicorn python-jose passlib bcrypt supabase openai pandas numpy faker python-dateutil stripe

Çalıştır:
uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, Depends, status, Request, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
import jwt
import bcrypt
import json
import requests
import hmac
import hashlib
import secrets
import re
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta

# ── Analiz modülleri
import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig, run_pipeline
from ai_engine import AIConfig, AIAnalysisEngine
from meta_ads import MetaConfig, run_meta_analysis
from pdf_report import generate_pdf_report

app = FastAPI(title="OPS Intelligence API", version="1.0.0")

# ── Mail gönderme (Resend)
async def send_email(to: str, subject: str, html: str):
    resend_key = os.environ.get("RESEND_API_KEY", "")
    if not resend_key:
        print("⚠️ RESEND_API_KEY eksik")
        return False
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {resend_key}", "Content-Type": "application/json"},
                json={"from": "OPS Intelligence <onboarding@resend.dev>", "to": [to], "subject": subject, "html": html},
                timeout=10
            )
            return r.status_code == 200
    except Exception as e:
        print(f"Mail hatası: {e}")
        return False

async def send_analysis_email(user_email: str, user_name: str, analysis_data: dict, pdf_bytes: bytes = None):
    score = analysis_data.get("analysis", {}).get("overall_health_score", 0)
    shop = analysis_data.get("shop_name", "Mağazanız")
    findings = analysis_data.get("analysis", {}).get("findings", [])[:3]
    quick_wins = analysis_data.get("analysis", {}).get("quick_wins", [])[:3]
    sc = "#1a7a4a" if score >= 75 else "#d4ac0d" if score >= 50 else "#c0392b"

    findings_html = "".join([f"""
        <div style="padding:12px 16px;background:#f8f7f4;border-left:3px solid {'#c0392b' if f.get('severity')=='critical' else '#d4ac0d' if f.get('severity')=='warning' else '#c9963a'};border-radius:4px;margin-bottom:8px">
            <div style="font-size:12px;font-weight:600;color:{'#c0392b' if f.get('severity')=='critical' else '#d4ac0d' if f.get('severity')=='warning' else '#c9963a'};margin-bottom:4px">{f.get('severity','').upper()}</div>
            <div style="font-size:14px;font-weight:500;color:#0d0c0a">{f.get('title','')}</div>
            <div style="font-size:13px;color:#8a8070;margin-top:4px">{f.get('description','')[:150]}...</div>
        </div>""" for f in findings])

    wins_html = "".join([f"""
        <div style="display:flex;gap:12px;padding:10px 0;border-bottom:1px solid #e0d8cc">
            <div style="font-size:18px;font-weight:400;color:#c9963a;min-width:28px;font-family:Georgia,serif">{str(i+1).zfill(2)}</div>
            <div style="font-size:13px;color:#2c2a25;line-height:1.6">{qw}</div>
        </div>""" for i, qw in enumerate(quick_wins)])

    html = f"""
    <div style="font-family:'DM Sans',Arial,sans-serif;max-width:600px;margin:0 auto;background:#ffffff">
        <div style="background:#0d0c0a;padding:28px 32px;text-align:center">
            <div style="font-size:24px;font-weight:600;color:#ffffff;letter-spacing:-0.02em">OPS<span style="color:#c9963a">.</span></div>
            <div style="font-size:12px;color:rgba(255,255,255,0.4);margin-top:4px;letter-spacing:0.1em;text-transform:uppercase">Analiz Raporu Hazır</div>
        </div>

        <div style="padding:32px">
            <p style="font-size:15px;color:#2c2a25;margin-bottom:24px">Merhaba {user_name.split()[0]},</p>
            <p style="font-size:14px;color:#8a8070;margin-bottom:24px"><strong>{shop}</strong> mağazanız için operasyonel analiz tamamlandı.</p>

            <div style="background:#f8f7f4;border:1px solid #e0d8cc;border-radius:12px;padding:20px;text-align:center;margin-bottom:24px">
                <div style="font-size:56px;font-weight:400;color:{sc};font-family:Georgia,serif;line-height:1">{score}</div>
                <div style="font-size:11px;color:#8a8070;text-transform:uppercase;letter-spacing:0.12em;margin-top:6px">Mağaza Sağlık Skoru / 100</div>
            </div>

            <h3 style="font-size:16px;color:#0d0c0a;margin-bottom:12px;font-family:Georgia,serif">Öne Çıkan Bulgular</h3>
            {findings_html}

            <h3 style="font-size:16px;color:#0d0c0a;margin:20px 0 12px;font-family:Georgia,serif">Bu Hafta Yapılacaklar</h3>
            {wins_html}

            <div style="margin-top:28px;text-align:center">
                <a href="https://opswebsitedot.netlify.app/app.html" style="display:inline-block;padding:12px 28px;background:#0d0c0a;color:#ffffff;text-decoration:none;border-radius:100px;font-size:14px;font-weight:500">Dashboard'a Git →</a>
            </div>
        </div>

        <div style="padding:20px 32px;border-top:1px solid #e0d8cc;text-align:center">
            <p style="font-size:11px;color:#8a8070">OPS Intelligence · E-Ticaret Operasyonel Analiz Platformu</p>
        </div>
    </div>"""

    return await send_email(user_email, f"📊 {shop} Analiz Raporu — Sağlık Skoru: {score}/100", html)

# ── Startup: DejaVu fontlarını indir (Türkçe PDF desteği)
@app.on_event("startup")
async def download_fonts():
    import urllib.request
    font_dir = "/app/fonts"
    os.makedirs(font_dir, exist_ok=True)
    fonts = {
        "DejaVuSans.ttf": "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2",
    }
    # Direkt TTF indirme
    ttf_urls = {
        "DejaVuSans.ttf":        "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans.ttf",
        "DejaVuSans-Bold.ttf":   "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Bold.ttf",
        "DejaVuSans-Oblique.ttf":"https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSans-Oblique.ttf",
        "DejaVuSansMono.ttf":    "https://cdn.jsdelivr.net/npm/dejavu-fonts-ttf@2.37.3/ttf/DejaVuSansMono.ttf",
    }
    for fname, url in ttf_urls.items():
        fpath = os.path.join(font_dir, fname)
        if not os.path.exists(fpath):
            try:
                urllib.request.urlretrieve(url, fpath)
                print(f"✅ Font indirildi: {fname}")
            except Exception as e:
                print(f"⚠️ Font indirilemedi: {fname} — {e}")

# ── CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── JWT Ayarları
JWT_SECRET = os.environ.get("JWT_SECRET", "ops-intelligence-secret-2025")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 7 gün

# ── Supabase
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://zyygkcknlcnoabwqbfij.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

# ── Shopify OAuth
SHOPIFY_API_KEY = os.environ.get("SHOPIFY_API_KEY", "")
SHOPIFY_API_SECRET = os.environ.get("SHOPIFY_API_SECRET", "")
SHOPIFY_SCOPES = os.environ.get("SHOPIFY_SCOPES", "read_orders,read_products,read_inventory")
SHOPIFY_BILLING_TEST = os.environ.get("SHOPIFY_BILLING_TEST", "true").lower() != "false"
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "https://ops-intelligence-production.up.railway.app").rstrip("/")
FRONTEND_PUBLIC_URL = os.environ.get("FRONTEND_PUBLIC_URL", "https://opsintelligence.org").rstrip("/")
SHOPIFY_STATE_EXPIRE_MINUTES = 10

security = HTTPBearer()


# ─────────────────────────────────────────────
# MODELLER
# ─────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class AnalysisRequest(BaseModel):
    use_mock: bool = True
    shopify_domain: Optional[str] = None
    shopify_token: Optional[str] = None
    connected_shop: Optional[str] = None
    fast_ai: bool = False
    meta_token: Optional[str] = None
    meta_account: Optional[str] = None
    use_mock_meta: bool = True
    language: str = "tr"

class ShopifyConnectStartRequest(BaseModel):
    shop: str

class ShopifyEmbeddedAnalyzeRequest(BaseModel):
    shop: str
    app_token: str


class ShopifyBillingRequest(BaseModel):
    shop: str
    plan: str
    app_token: str


# ─────────────────────────────────────────────
# VERİTABANI (Supabase)
# ─────────────────────────────────────────────

def get_supabase():
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def create_token(email: str, plan: str) -> str:
    payload = {
        "sub": email,
        "plan": plan,
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token süresi doldu")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Geçersiz token")


def normalize_shop_domain(shop: str) -> str:
    shop = (shop or "").strip().lower()
    shop = shop.replace("https://", "").replace("http://", "").split("/")[0]
    if shop and "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", shop or ""):
        raise HTTPException(status_code=400, detail="Geçerli bir Shopify mağaza domain'i girin.")
    return shop


def create_shopify_state(email: str, shop: str, mode: str = "user") -> str:
    payload = {
        "sub": email,
        "shop": shop,
        "mode": mode,
        "nonce": secrets.token_urlsafe(16),
        "exp": datetime.utcnow() + timedelta(minutes=SHOPIFY_STATE_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_shopify_state(state: str, shop: str) -> dict:
    try:
        payload = jwt.decode(state, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Shopify bağlantı oturumu süresi doldu. Tekrar deneyin.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Shopify bağlantı oturumu geçersiz.")
    if payload.get("shop") != shop:
        raise HTTPException(status_code=400, detail="Shopify mağaza doğrulaması başarısız.")
    return payload


def verify_shopify_hmac(query_params: dict) -> bool:
    if not SHOPIFY_API_SECRET:
        return False
    provided_hmac = query_params.get("hmac", "")
    if not provided_hmac:
        return False
    params = []
    for key in sorted(query_params.keys()):
        if key in ("hmac", "signature"):
            continue
        params.append(f"{key}={query_params[key]}")
    message = "&".join(params)
    digest = hmac.new(SHOPIFY_API_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, provided_hmac)


def build_shopify_install_url(shop: str) -> str:
    shop_domain = normalize_shop_domain(shop)
    state = create_shopify_state(f"shopify:{shop_domain}", shop_domain, mode="embedded")
    redirect_uri = f"{BACKEND_PUBLIC_URL}/shopify/callback"
    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "grant_options[]": "offline",
    }
    return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params, doseq=True)}"


def render_shopify_install_required(shop: str) -> HTMLResponse:
    install_url = build_shopify_install_url(shop)
    return HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Connect OPS to Shopify</title>
  <style>
    body{{margin:0;background:#faf8f4;color:#17140f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
    .wrap{{min-height:100vh;display:grid;place-items:center;padding:28px}}
    .card{{max-width:620px;background:#fff;border:1px solid #e0d8cc;border-radius:14px;padding:26px;box-shadow:0 16px 40px rgba(30,24,10,.08)}}
    h1{{font-family:Georgia,serif;font-size:34px;font-weight:400;margin:0 0 10px}}
    p{{color:#887f70;line-height:1.6}}
    a{{display:inline-flex;border-radius:12px;background:#11100c;color:#fff;padding:13px 16px;font-weight:700;text-decoration:none;margin-top:8px}}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <h1>Connect OPS</h1>
      <p>OPS needs Shopify permission for {shop}. The approval screen will open now. If Safari blocks the redirect, use the button below.</p>
      <a href="{install_url}" target="_top">Open Shopify permission screen</a>
    </section>
  </div>
  <script>
    const url = {json.dumps(install_url)};
    if (window.top) window.top.location.href = url;
    else window.location.href = url;
  </script>
</body>
</html>
""")


def create_shopify_embedded_token(email: str, shop: str) -> str:
    payload = {
        "sub": email,
        "shop": shop,
        "purpose": "shopify_embedded",
        "exp": datetime.utcnow() + timedelta(minutes=30),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_shopify_embedded_token(token: str, shop: str) -> dict:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Shopify app session expired. Reopen OPS in Shopify.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Shopify app session.")
    if payload.get("purpose") != "shopify_embedded" or payload.get("shop") != shop:
        raise HTTPException(status_code=401, detail="Invalid Shopify app session.")
    return payload


def fetch_shop_profile(shop: str, access_token: str) -> dict:
    response = requests.get(
        f"https://{shop}/admin/api/2024-01/shop.json",
        headers={"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json().get("shop", {})


def find_shopify_store_by_domain(shop: str) -> Optional[dict]:
    db = get_supabase()
    result = db.table("users").select("email,name,plan,analyses_this_month,stores").execute()
    for user in result.data or []:
        stores = user.get("stores") or []
        if not isinstance(stores, list):
            continue
        for store in stores:
            if (
                isinstance(store, dict)
                and store.get("platform") == "shopify"
                and store.get("status") == "connected"
                and store.get("domain") == shop
                and store.get("access_token")
            ):
                return {"user": user, "store": store}
    return None


def ensure_shopify_user(shop: str, access_token: str, scope: str) -> dict:
    db = get_supabase()
    try:
        profile = fetch_shop_profile(shop, access_token)
    except requests.exceptions.RequestException:
        profile = {}

    email = (profile.get("email") or profile.get("customer_email") or f"shopify-{shop}@ops.local").lower().strip()
    name = profile.get("name") or profile.get("shop_owner") or shop
    existing = db.table("users").select("email,name,plan,stores").eq("email", email).execute()
    if not existing.data:
        db.table("users").insert({
            "email": email,
            "name": name,
            "password_hash": hash_password(secrets.token_urlsafe(24)),
            "plan": "free",
            "stores": [],
            "analyses_this_month": 0,
            "is_active": True,
        }).execute()

    safe_store = save_shopify_store(email, shop, access_token, scope)
    return {"email": email, "name": name, "store": safe_store}


def save_shopify_store(email: str, shop: str, access_token: str, scope: str) -> dict:
    db = get_supabase()
    user_result = db.table("users").select("stores").eq("email", email).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    stores = user_result.data[0].get("stores") or []
    if not isinstance(stores, list):
        stores = []

    now = datetime.utcnow().isoformat()
    store_record = {
        "platform": "shopify",
        "domain": shop,
        "access_token": access_token,
        "scope": scope,
        "connected_at": now,
        "updated_at": now,
        "status": "connected",
    }

    replaced = False
    for idx, store in enumerate(stores):
        if store.get("platform") == "shopify" and store.get("domain") == shop:
            store_record["connected_at"] = store.get("connected_at", now)
            stores[idx] = store_record
            replaced = True
            break
    if not replaced:
        stores.append(store_record)

    db.table("users").update({"stores": stores}).eq("email", email).execute()
    safe_record = {k: v for k, v in store_record.items() if k != "access_token"}
    return safe_record


def get_connected_shop(email: str, requested_shop: Optional[str] = None) -> Optional[dict]:
    db = get_supabase()
    result = db.table("users").select("stores").eq("email", email).execute()
    if not result.data:
        return None
    stores = result.data[0].get("stores") or []
    if not isinstance(stores, list):
        return None
    requested = normalize_shop_domain(requested_shop) if requested_shop else None
    for store in stores:
        if store.get("platform") != "shopify" or store.get("status") != "connected":
            continue
        if requested and store.get("domain") != requested:
            continue
        if store.get("access_token"):
            return store
    return None


def set_user_plan(email: str, plan: str) -> None:
    if plan not in ("free", "starter", "pro"):
        raise HTTPException(status_code=400, detail="Invalid plan.")
    db = get_supabase()
    db.table("users").update({"plan": plan}).eq("email", email).execute()


def public_store(store: dict) -> dict:
    return {
        "platform": store.get("platform", "shopify"),
        "domain": store.get("domain", ""),
        "scope": store.get("scope", ""),
        "connected_at": store.get("connected_at", ""),
        "updated_at": store.get("updated_at", ""),
        "status": store.get("status", "connected"),
    }


# ─────────────────────────────────────────────
# PLAN TANIMLARI
# ─────────────────────────────────────────────

PLANS = {
    "free":    {"name": "Ücretsiz", "price": 0,  "max_stores": 1,  "max_orders": 100,  "ai": False, "pdf": False, "meta": False},
    "starter": {"name": "Starter",  "price": 29, "max_stores": 2,  "max_orders": 1000, "ai": True,  "pdf": True,  "meta": False},
    "pro":     {"name": "Pro",      "price": 79, "max_stores": 10, "max_orders": 10000,"ai": True,  "pdf": True,  "meta": True},
}


# ─────────────────────────────────────────────
# AUTH ENDPOINTLERİ
# ─────────────────────────────────────────────

@app.post("/auth/register")
async def register(req: RegisterRequest):
    db = get_supabase()
    email = req.email.lower().strip()

    # Mevcut kullanıcı kontrolü
    existing = db.table("users").select("email").eq("email", email).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail="Bu e-posta zaten kayıtlı.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Şifre en az 6 karakter olmalı.")

    # Kullanıcı oluştur
    user = {
        "email": email,
        "name": req.name,
        "password_hash": hash_password(req.password),
        "plan": "free",
        "stores": [],
        "analyses_this_month": 0,
        "is_active": True,
    }
    result = db.table("users").insert(user).execute()

    token = create_token(email, "free")
    return {
        "success": True,
        "token": token,
        "user": {"email": email, "name": req.name, "plan": "free"},
    }


@app.post("/auth/login")
async def login(req: LoginRequest):
    db = get_supabase()
    email = req.email.lower().strip()

    result = db.table("users").select("*").eq("email", email).execute()
    if not result.data:
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    user = result.data[0]
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı.")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="Hesap devre dışı.")

    token = create_token(email, user["plan"])
    return {
        "success": True,
        "token": token,
        "user": {
            "email": user["email"],
            "name": user["name"],
            "plan": user["plan"],
            "analyses_this_month": user.get("analyses_this_month", 0),
        },
    }


@app.get("/auth/me")
async def me(payload: dict = Depends(verify_token)):
    db = get_supabase()
    result = db.table("users").select("email,name,plan,analyses_this_month,stores").eq(
        "email", payload["sub"]
    ).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    user = result.data[0]
    user["stores"] = [
        public_store(store)
        for store in (user.get("stores") or [])
        if isinstance(store, dict)
    ]
    plan = PLANS.get(user["plan"], PLANS["free"])
    return {
        "user": user,
        "plan": plan,
    }


# ─────────────────────────────────────────────
# SHOPIFY APP INSTALL / OAUTH
# ─────────────────────────────────────────────

@app.get("/shopify/install")
async def shopify_install(shop: str):
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(status_code=500, detail="Shopify OAuth env ayarları eksik.")

    shop_domain = normalize_shop_domain(shop)
    install_url = build_shopify_install_url(shop_domain)
    return RedirectResponse(install_url)


@app.get("/shopify/app", response_class=HTMLResponse)
async def shopify_app_home(request: Request):
    params = dict(request.query_params)
    shop = normalize_shop_domain(params.get("shop", ""))
    connected = find_shopify_store_by_domain(shop)
    if not connected:
        return render_shopify_install_required(shop)

    user = connected["user"]
    store = connected["store"]
    plan_key = user.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])
    app_token = create_shopify_embedded_token(user["email"], shop)
    safe_scope = (store.get("scope") or "").replace("<", "").replace(">", "")
    used = int(user.get("analyses_this_month") or 0)
    max_analyses = max(1, plan["max_orders"] // 100)

    return HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OPS Intelligence</title>
  <style>
    body{{margin:0;background:#faf8f4;color:#17140f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
    .wrap{{padding:28px;max-width:1180px;margin:0 auto}}
    h1{{font-family:Georgia,serif;font-size:34px;font-weight:400;margin:0 0 6px}}
    .muted{{color:#887f70}} .grid{{display:grid;grid-template-columns:1.2fr .8fr;gap:18px;margin-top:22px}}
    .card{{background:#fff;border:1px solid #e0d8cc;border-radius:14px;padding:20px;box-shadow:0 14px 34px rgba(30,24,10,.06)}}
    .row{{display:flex;justify-content:space-between;gap:12px;padding:10px 0;border-bottom:1px solid #eee7dc}}
    .row:last-child{{border-bottom:0}} .pill{{display:inline-flex;border-radius:999px;background:#d09b36;color:#fff;padding:5px 10px;font-size:12px;font-weight:700}}
    button,a.btn{{appearance:none;border:0;border-radius:12px;background:#11100c;color:#fff;padding:13px 16px;font-weight:700;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:8px}}
    button.secondary{{background:#fff;color:#11100c;border:1px solid #ded5c8}} .plans{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}}
    .plan{{border:1px solid #e0d8cc;border-radius:12px;padding:14px;background:#faf8f4}} .price{{font-size:24px;font-weight:800;margin-top:8px}}
    #result{{white-space:pre-wrap;background:#11100c;color:#f8f1df;border-radius:12px;padding:14px;font-size:13px;min-height:90px;margin-top:14px}}
    @media(max-width:800px){{.grid,.plans{{grid-template-columns:1fr}}}}
  </style>
</head>
<body>
  <div class="wrap">
    <h1>OPS Intelligence</h1>
    <div class="muted">Shopify admin app home for {shop}</div>
    <div class="grid">
      <section class="card">
        <span class="pill">Connected</span>
        <h2>Store overview</h2>
        <div class="row"><span>Shop</span><strong>{shop}</strong></div>
        <div class="row"><span>Plan</span><strong>{plan_key.title()}</strong></div>
        <div class="row"><span>Usage</span><strong>{used}/{max_analyses} analyses</strong></div>
        <div class="row"><span>Permissions</span><span class="muted">{safe_scope}</span></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">
          <button onclick="runAnalysis()">Analyze Shopify data</button>
          <a class="btn secondary" href="{FRONTEND_PUBLIC_URL}/app.html?shop={quote(shop)}" target="_blank">Open full OPS dashboard</a>
        </div>
        <div id="result">Ready. Click “Analyze Shopify data” to fetch orders/products and produce a summary.</div>
      </section>
      <section class="card">
        <h2>Plans</h2>
        <div class="plans">
          <div class="plan"><strong>Free</strong><div class="price">€0</div><div class="muted">100 orders</div></div>
          <div class="plan"><strong>Starter</strong><div class="price">€29</div><div class="muted">AI + PDF</div><button class="secondary" style="margin-top:12px;width:100%" onclick="startBilling('starter')">Choose Starter</button></div>
          <div class="plan"><strong>Pro</strong><div class="price">€79</div><div class="muted">Forecast, churn, pricing</div><button class="secondary" style="margin-top:12px;width:100%" onclick="startBilling('pro')">Choose Pro</button></div>
        </div>
        <p class="muted">Paid plans open Shopify Billing confirmation inside Shopify. Billing is currently controlled by SHOPIFY_BILLING_TEST.</p>
      </section>
    </div>
  </div>
  <script>
    const shop = {json.dumps(shop)};
    const appToken = {json.dumps(app_token)};
    async function runAnalysis(){{
      const box=document.getElementById('result');
      box.textContent='Fetching Shopify data and analyzing... This can take up to 2 minutes.';
      try{{
        const res=await fetch('/shopify/app/analyze',{{
          method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body:JSON.stringify({{shop,app_token:appToken}})
        }});
        const data=await res.json();
        if(!res.ok) throw new Error(data.detail||'Analysis failed');
        const rev=data.metrics.revenue||{{}};
        const inv=data.metrics.inventory||{{}};
        box.textContent =
          `Health score: ${{data.analysis.overall_health_score || 0}}/100\\n`+
          `Revenue: €${{Number(rev.total || 0).toLocaleString()}}\\n`+
          `Orders: ${{rev.orders || 0}}\\n`+
          `AOV: €${{Number(rev.aov || 0).toFixed(2)}}\\n`+
          `Critical inventory items: ${{inv.critical_count || 0}}\\n\\n`+
          `${{data.analysis.executive_summary || 'Analysis completed.'}}`;
      }}catch(e){{
        box.textContent='Error: '+e.message;
      }}
    }}
    async function startBilling(plan){{
      const box=document.getElementById('result');
      box.textContent='Opening Shopify Billing confirmation...';
      try{{
        const res=await fetch('/shopify/app/billing',{{
          method:'POST',
          headers:{{'Content-Type':'application/json'}},
          body:JSON.stringify({{shop,plan,app_token:appToken}})
        }});
        const data=await res.json();
        if(!res.ok) throw new Error(data.detail||'Billing failed');
        window.top.location.href=data.confirmation_url;
      }}catch(e){{
        box.textContent='Billing error: '+e.message;
      }}
    }}
  </script>
</body>
</html>
""")


@app.post("/shopify/app/analyze")
async def shopify_embedded_analyze(req: ShopifyEmbeddedAnalyzeRequest):
    shop = normalize_shop_domain(req.shop)
    payload = verify_shopify_embedded_token(req.app_token, shop)
    connected = get_connected_shop(payload["sub"], shop)
    if not connected:
        raise HTTPException(status_code=404, detail="Connected Shopify store not found.")

    try:
        report = run_pipeline(ShopifyConfig(
            shop_domain=shop,
            access_token=connected["access_token"],
            use_mock=False,
            mock_order_count=200,
        ))
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        if status_code in (401, 403):
            raise HTTPException(status_code=status_code, detail="Shopify permissions are missing or expired. Reinstall OPS from Shopify.")
        raise HTTPException(status_code=502, detail=f"Shopify API returned HTTP {status_code}.")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Shopify API timed out. Please retry.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Shopify connection error: {str(e)}")
    ai_result = AIAnalysisEngine(AIConfig(use_mock_ai=True, language="en")).analyze(report)
    return {
        "success": True,
        "shop_name": shop,
        "analysis": ai_result.get("analysis", {}),
        "metrics": {
            "revenue": {
                "total": report["revenue"]["total_revenue"],
                "orders": report["revenue"]["total_orders"],
                "aov": report["revenue"]["aov"],
                "cancel_rate": report["revenue"]["cancellation_rate"],
            },
            "inventory": {
                "total_products": len(report["inventory"]["details"]),
                "critical_count": len(report["inventory"]["critical_items"]) if report["inventory"]["critical_items"] is not None else 0,
            },
        },
    }


@app.post("/shopify/app/billing")
async def shopify_embedded_billing(req: ShopifyBillingRequest):
    shop = normalize_shop_domain(req.shop)
    payload = verify_shopify_embedded_token(req.app_token, shop)
    connected = get_connected_shop(payload["sub"], shop)
    if not connected:
        raise HTTPException(status_code=404, detail="Connected Shopify store not found.")

    if req.plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Only Starter and Pro can be purchased through Shopify Billing.")

    amount = 29.0 if req.plan == "starter" else 79.0
    name = "OPS Starter" if req.plan == "starter" else "OPS Pro"
    return_url = f"{BACKEND_PUBLIC_URL}/shopify/billing/return?shop={quote(shop)}&plan={quote(req.plan)}"
    mutation = """
    mutation AppSubscriptionCreate($name: String!, $returnUrl: URL!, $test: Boolean!, $lineItems: [AppSubscriptionLineItemInput!]!) {
      appSubscriptionCreate(name: $name, returnUrl: $returnUrl, test: $test, lineItems: $lineItems) {
        confirmationUrl
        userErrors { field message }
      }
    }
    """
    variables = {
        "name": name,
        "returnUrl": return_url,
        "test": SHOPIFY_BILLING_TEST,
        "lineItems": [{
            "plan": {
                "appRecurringPricingDetails": {
                    "price": {"amount": amount, "currencyCode": "EUR"},
                    "interval": "EVERY_30_DAYS",
                }
            }
        }],
    }
    response = requests.post(
        f"https://{shop}/admin/api/2024-01/graphql.json",
        headers={"X-Shopify-Access-Token": connected["access_token"], "Content-Type": "application/json"},
        json={"query": mutation, "variables": variables},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    create_result = payload.get("data", {}).get("appSubscriptionCreate", {})
    errors = create_result.get("userErrors") or payload.get("errors") or []
    if errors:
        first_error = errors[0].get("message") if isinstance(errors[0], dict) else str(errors[0])
        raise HTTPException(status_code=400, detail=first_error or "Shopify Billing could not be started.")

    confirmation_url = create_result.get("confirmationUrl")
    if not confirmation_url:
        raise HTTPException(status_code=502, detail="Shopify did not return a billing confirmation URL.")

    return {"success": True, "confirmation_url": confirmation_url, "test": SHOPIFY_BILLING_TEST}


@app.get("/shopify/billing/return")
async def shopify_billing_return(shop: str, plan: str):
    shop_domain = normalize_shop_domain(shop)
    connected = find_shopify_store_by_domain(shop_domain)
    if connected and plan in ("starter", "pro"):
        set_user_plan(connected["user"]["email"], plan)
    return RedirectResponse(f"{BACKEND_PUBLIC_URL}/shopify/app?shop={quote(shop_domain)}&billing_return=1")


@app.post("/shopify/connect/start")
async def start_shopify_connect(req: ShopifyConnectStartRequest, payload: dict = Depends(verify_token)):
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Shopify OAuth ayarları eksik. Railway env içinde SHOPIFY_API_KEY ve SHOPIFY_API_SECRET tanımlanmalı.",
        )

    shop = normalize_shop_domain(req.shop)
    state = create_shopify_state(payload["sub"], shop)
    redirect_uri = f"{BACKEND_PUBLIC_URL}/shopify/callback"
    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
        "grant_options[]": "offline",
    }
    install_url = f"https://{shop}/admin/oauth/authorize?{urlencode(params, doseq=True)}"
    return {"success": True, "install_url": install_url, "shop": shop, "scopes": SHOPIFY_SCOPES}


@app.get("/shopify/callback")
async def shopify_callback(request: Request):
    params = dict(request.query_params)
    shop = normalize_shop_domain(params.get("shop", ""))
    state = params.get("state", "")
    code = params.get("code", "")

    if not code:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error=missing_code")
    if not verify_shopify_hmac(params):
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error=bad_hmac")

    try:
        state_payload = verify_shopify_state(state, shop)
    except HTTPException:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error=bad_state")

    try:
        token_response = requests.post(
            f"https://{shop}/admin/oauth/access_token",
            json={
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET,
                "code": code,
            },
            timeout=30,
        )
        token_response.raise_for_status()
        token_data = token_response.json()
    except requests.exceptions.RequestException as e:
        print(f"Shopify token exchange failed for {shop}: {e}")
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error=token_exchange_failed")

    access_token = token_data.get("access_token")
    if not access_token:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error=no_access_token")

    if state_payload.get("mode") == "embedded":
        ensure_shopify_user(
            shop,
            access_token,
            token_data.get("scope", SHOPIFY_SCOPES),
        )
        return RedirectResponse(f"{BACKEND_PUBLIC_URL}/shopify/app?shop={quote(shop)}&shopify_connected=1")

    user_email = state_payload["sub"]
    save_shopify_store(
        user_email,
        shop,
        access_token,
        token_data.get("scope", SHOPIFY_SCOPES),
    )

    db = get_supabase()
    user_result = db.table("users").select("plan").eq("email", user_email).execute()
    plan_key = user_result.data[0].get("plan", "free") if user_result.data else "free"
    ops_token = create_token(user_email, plan_key)
    return RedirectResponse(
        f"{FRONTEND_PUBLIC_URL}/app.html#shopify_connected=1&shop={quote(shop)}&token={quote(ops_token)}"
    )


@app.get("/shopify/status")
async def shopify_status(payload: dict = Depends(verify_token)):
    db = get_supabase()
    result = db.table("users").select("stores").eq("email", payload["sub"]).execute()
    stores = result.data[0].get("stores", []) if result.data else []
    shopify_stores = [
        public_store(store)
        for store in stores
        if isinstance(store, dict) and store.get("platform") == "shopify"
    ]
    return {"success": True, "stores": shopify_stores}


# ─────────────────────────────────────────────
# ANALİZ ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/run")
async def run_analysis(req: AnalysisRequest, payload: dict = Depends(verify_token)):
    db = get_supabase()
    email = payload["sub"]

    user_data = db.table("users").select("plan,analyses_this_month").eq("email", email).execute()
    if not user_data.data:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı.")

    # JWT plan bilgisi eski kalabilir; kullanım ve limit için her zaman DB'deki güncel planı esas al.
    plan_key = user_data.data[0].get("plan") or payload.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])
    used = user_data.data[0].get("analyses_this_month") or 0
    limit = plan["max_orders"] // 100

    if used >= limit:
        raise HTTPException(status_code=429, detail=f"Aylık limit doldu ({used}/{limit}). Güncel plan: {plan_key}.")

    connected_store = None
    if not req.use_mock and not req.shopify_token:
        connected_store = get_connected_shop(email, req.connected_shop or req.shopify_domain)
        if not connected_store:
            raise HTTPException(
                status_code=400,
                detail="Bu hesapta bağlı Shopify mağazası bulunamadı. Önce Connect Shopify ile uygulamayı mağazaya kurun.",
            )

    shop_domain = (connected_store or {}).get("domain") or req.shopify_domain or ""
    shop_token = (connected_store or {}).get("access_token") or req.shopify_token or ""

    # Shopify config
    shopify_cfg = ShopifyConfig(
        shop_domain=shop_domain,
        access_token=shop_token,
        use_mock=req.use_mock,
        mock_order_count=200,
    )

    # Veri çek
    try:
        report = run_pipeline(shopify_cfg)
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        if status_code in (401, 403):
            raise HTTPException(
                status_code=status_code,
                detail=(
                    "Shopify bağlantısı yetkisiz. Token'ın doğru olduğundan ve "
                    "read_orders, read_products, read_inventory scope'larının açık olduğundan emin olun."
                ),
            )
        raise HTTPException(status_code=502, detail=f"Shopify API hata döndürdü: HTTP {status_code}")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Shopify API yanıtı zaman aşımına uğradı. Birazdan tekrar deneyin.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Shopify bağlantı hatası: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analiz başlatılamadı: {str(e)}")

    # AI analiz
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if req.fast_ai:
        ai_cfg = AIConfig(use_mock_ai=True, language=req.language)
    elif openai_key and plan["ai"]:
        ai_cfg = AIConfig(api_key=openai_key, use_mock_ai=False, language=req.language)
    else:
        ai_cfg = AIConfig(use_mock_ai=True, language=req.language)

    engine = AIAnalysisEngine(ai_cfg)
    ai_result = engine.analyze(report)

    # Fallback
    if not ai_result.get("success") or "analysis" not in ai_result:
        engine2 = AIAnalysisEngine(AIConfig(use_mock_ai=True, language=req.language))
        ai_result = engine2.analyze(report)

    # Meta Ads (Pro plan)
    meta_data = None
    if plan["meta"] and (req.meta_token or req.use_mock_meta):
        meta_cfg = MetaConfig(
            access_token=req.meta_token or "",
            ad_account_id=req.meta_account or "",
            use_mock=req.use_mock_meta,
        )
        products_df = report.get("products_df")
        meta_result = run_meta_analysis(meta_cfg, products_df)
        meta_data = {
            "roas_analysis": meta_result["roas_analysis"],
            "cross_alarms": meta_result["cross_alarms"],
            "campaign_summary": meta_result["campaign_summary"].to_dict("records"),
        }

    # Kullanım sayacını artır
    db.table("users").update({
        "analyses_this_month": used + 1,
        "last_analysis": datetime.now().isoformat(),
    }).eq("email", email).execute()

    inventory_products = report["inventory"]["details"].to_dict("records")
    for product in inventory_products:
        product["current_stock"] = product.get("inventory", 0)

    # Analiz sonucu
    result_data = {
        "analysis": ai_result.get("analysis", {}),
        "shop_name": shop_domain or "Demo Mağaza",
        "metrics": {
            "fulfillment": {"mean": report["fulfillment_time"]["mean"], "median": report["fulfillment_time"]["median"], "p95": report["fulfillment_time"]["p95"], "over72h": report["fulfillment_time"]["orders_over_72h"], "status": report["fulfillment_time"]["status"], "total": report["fulfillment_time"]["total_fulfilled"]},
            "revenue": {"total": report["revenue"]["total_revenue"], "orders": report["revenue"]["total_orders"], "aov": report["revenue"]["aov"], "cancel_rate": report["revenue"]["cancellation_rate"], "refund_rate": report["revenue"]["refund_rate"]},
            "inventory": {"avg_turnover": report["inventory"]["avg_turnover"], "critical_count": len(report["inventory"]["critical_items"]) if report["inventory"]["critical_items"] is not None else 0, "products": inventory_products},
        },
    }

    # Mail gönder
    user_info = db.table("users").select("name").eq("email", email).execute()
    user_name = user_info.data[0]["name"] if user_info.data else email
    try:
        mail_sent = await send_analysis_email(email, user_name, result_data)
        print(f"📧 Mail {'gönderildi' if mail_sent else 'gönderilemedi'}: {email}")
    except Exception as e:
        print(f"📧 Mail hatası: {e}")

    # Metrikleri hazırla
    ft  = report["fulfillment_time"]
    rev = report["revenue"]
    inv = report["inventory"]

    return {
        "success": True,
        "analysis": ai_result.get("analysis", {}),
        "model": ai_result.get("model", "mock"),
        "generated_at": ai_result.get("generated_at", datetime.now().isoformat()),
        "metrics": {
            "fulfillment": {
                "mean":   ft["mean"],
                "median": ft["median"],
                "p95":    ft["p95"],
                "over72h": ft["orders_over_72h"],
                "status": ft["status"],
                "total":  ft["total_fulfilled"],
            },
            "revenue": {
                "total":       rev["total_revenue"],
                "orders":      rev["total_orders"],
                "aov":         rev["aov"],
                "cancel_rate": rev["cancellation_rate"],
                "refund_rate": rev["refund_rate"],
            },
            "inventory": {
                "avg_turnover":   inv["avg_turnover"],
                "critical_count": len(inv["critical_items"]) if inv["critical_items"] is not None else 0,
                "products": inventory_products,
            },
        },
        "meta": meta_data,
        "shop_name": shop_domain or "Demo Mağaza",
    }


# ─────────────────────────────────────────────
# CSV / EXCEL UPLOAD ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/upload")
async def upload_analysis(
    file: UploadFile = File(...),
    platform: str = Form("generic"),
    language: str = Form("tr"),
    payload: dict = Depends(verify_token),
):
    filename = file.filename or "upload"
    allowed_ext = (".csv", ".xlsx", ".xls")
    if not filename.lower().endswith(allowed_ext):
        raise HTTPException(status_code=400, detail="CSV veya Excel dosyası yükleyin.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Dosya boş görünüyor.")

    result = await run_analysis(
        AnalysisRequest(
            use_mock=True,
            shopify_domain=f"{platform.title()} Upload",
            use_mock_meta=True,
            language=language,
        ),
        payload,
    )
    result["shop_name"] = f"{platform.title()} Upload"
    result["uploaded_file"] = filename
    result["model"] = result.get("model") or "mock-upload"
    return result


# ─────────────────────────────────────────────
# PDF ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/pdf")
async def get_pdf(req: AnalysisRequest, payload: dict = Depends(verify_token)):
    from fastapi.responses import Response
    plan_key = payload.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])

    if not plan["pdf"]:
        raise HTTPException(status_code=403, detail="PDF export Starter+ plan gerektirir.")

    # Analiz çalıştır
    analysis_response = await run_analysis(req, payload)

    # PDF oluştur (mock result formatına çevir)
    mock_result = {
        "success": True,
        "analysis": analysis_response["analysis"],
        "metrics": {
            "fulfillment_time": {**analysis_response["metrics"]["fulfillment"], "total_fulfilled": analysis_response["metrics"]["fulfillment"]["total"]},
            "revenue": analysis_response["metrics"]["revenue"],
            "inventory": analysis_response["metrics"]["inventory"],
        },
        "generated_at": analysis_response["generated_at"],
    }

    pdf_bytes = generate_pdf_report(mock_result, None, req.shopify_domain or "Demo Mağaza")

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=ops_report.pdf"},
    )


# ─────────────────────────────────────────────
# STRIPE ÖDEMELERİ
# ─────────────────────────────────────────────

class CheckoutRequest(BaseModel):
    plan: str
    success_url: str
    cancel_url: str

@app.post("/payments/create-checkout")
async def create_checkout(req: CheckoutRequest, payload: dict = Depends(verify_token)):
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe yapılandırılmamış.")

    price_ids = {
        "starter": os.environ.get("STRIPE_PRICE_STARTER", "price_1TRf3JG1DLQ2LxkRn0eLrytf"),
        "pro":     os.environ.get("STRIPE_PRICE_PRO",     "price_1TRf3aG1DLQ2LxkRqDhmI9jg"),
    }
    price_id = price_ids.get(req.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Geçersiz plan.")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            customer_email=payload["sub"],
            metadata={"user_email": payload["sub"], "plan": req.plan},
        )
        return {"success": True, "checkout_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/payments/webhook")
async def stripe_webhook(request: Request):
    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")

    body = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        if webhook_secret:
            event = stripe.Webhook.construct_event(body, sig, webhook_secret)
        else:
            event = stripe.Event.construct_from(body, stripe.api_key)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        email = session.get("customer_email") or session.get("metadata", {}).get("user_email")
        plan = session.get("metadata", {}).get("plan", "starter")
        if email:
            db = get_supabase()
            db.table("users").update({"plan": plan}).eq("email", email).execute()
            print(f"✅ Plan güncellendi: {email} → {plan}")

    return {"status": "ok"}

async def cancel_subscription_for_user(payload: dict) -> dict:
    email = payload["sub"]

    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
        if stripe.api_key:
            customers = stripe.Customer.list(email=email, limit=1)
            if customers.data:
                subscriptions = stripe.Subscription.list(
                    customer=customers.data[0].id,
                    status="active",
                    limit=10,
                )
                for subscription in subscriptions.data:
                    stripe.Subscription.modify(
                        subscription.id,
                        cancel_at_period_end=True,
                    )
    except Exception as e:
        print(f"Stripe iptal uyarısı: {e}")

    db = get_supabase()
    db.table("users").update({"plan": "free"}).eq("email", email).execute()

    new_token = create_token(email, "free")
    return {
        "success": True,
        "token": new_token,
        "plan": "free",
        "message": "Abonelik iptal edildi, plan Free olarak güncellendi.",
    }

@app.post("/payments/cancel")
async def cancel_payment(payload: dict = Depends(verify_token)):
    return await cancel_subscription_for_user(payload)

@app.post("/payments/cancel-subscription")
async def cancel_subscription(payload: dict = Depends(verify_token)):
    return await cancel_subscription_for_user(payload)

@app.put("/user/plan")
async def update_plan(plan: str, payload: dict = Depends(verify_token)):
    if plan not in PLANS:
        raise HTTPException(status_code=400, detail="Geçersiz plan.")

    db = get_supabase()
    db.table("users").update({"plan": plan}).eq("email", payload["sub"]).execute()

    new_token = create_token(payload["sub"], plan)
    return {"success": True, "token": new_token, "plan": plan}


# ─────────────────────────────────────────────
# SAĞLIK KONTROLÜ
# ─────────────────────────────────────────────

@app.get("/")
async def root():
    return {"status": "ok", "service": "OPS Intelligence API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
