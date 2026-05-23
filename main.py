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
from fastapi.responses import RedirectResponse
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
    meta_token: Optional[str] = None
    meta_account: Optional[str] = None
    use_mock_meta: bool = True
    language: str = "tr"

class ShopifyConnectStartRequest(BaseModel):
    shop: str


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


def create_shopify_state(email: str, shop: str) -> str:
    payload = {
        "sub": email,
        "shop": shop,
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

    save_shopify_store(
        state_payload["sub"],
        shop,
        access_token,
        token_data.get("scope", SHOPIFY_SCOPES),
    )

    return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_connected=1&shop={quote(shop)}")


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
    plan_key = payload.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])

    # Limit kontrolü
    user_data = db.table("users").select("analyses_this_month").eq("email", email).execute()
    used = user_data.data[0]["analyses_this_month"] if user_data.data else 0
    limit = plan["max_orders"] // 100

    if used >= limit:
        raise HTTPException(status_code=429, detail=f"Aylık limit doldu ({used}/{limit}). Plan yükselt.")

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
    if openai_key and plan["ai"]:
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
