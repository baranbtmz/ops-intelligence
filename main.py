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
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional, Any, Dict, List
import os
import jwt
import bcrypt
import json
import requests
import hmac
import hashlib
import base64
import secrets
import re
import io
import logging
import pandas as pd
import numpy as np
from urllib.parse import urlencode, quote
from datetime import datetime, timedelta, date

logger = logging.getLogger("ops-intelligence")

# ── Analiz modülleri
import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig, WooCommerceConfig, MetricsEngine, run_pipeline, run_shopify_live_pipeline, run_woocommerce_pipeline
from ai_engine import AIConfig, AIAnalysisEngine, run_extended_analysis
from meta_ads import MetaConfig, run_meta_analysis
from pdf_report import generate_pdf_report

def load_local_env_file(filename: str = ".env.local"):
    """Load local development env values without requiring an extra dependency."""
    path = os.path.join(os.path.dirname(__file__), filename)
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass

load_local_env_file()

app = FastAPI(title="OPS Intelligence API", version="1.0.0")
app.mount("/assets", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "assets")), name="assets")

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
    shop = analysis_data.get("shop_name", "Your store")
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
            <div style="font-size:12px;color:rgba(255,255,255,0.4);margin-top:4px;letter-spacing:0.1em;text-transform:uppercase">Analysis Ready</div>
        </div>

        <div style="padding:32px">
            <p style="font-size:15px;color:#2c2a25;margin-bottom:24px">Hi {user_name.split()[0]},</p>
            <p style="font-size:14px;color:#8a8070;margin-bottom:24px">Your latest operations review for <strong>{shop}</strong> is ready.</p>

            <div style="background:#f8f7f4;border:1px solid #e0d8cc;border-radius:12px;padding:20px;text-align:center;margin-bottom:24px">
                <div style="font-size:56px;font-weight:400;color:{sc};font-family:Georgia,serif;line-height:1">{score}</div>
                <div style="font-size:11px;color:#8a8070;text-transform:uppercase;letter-spacing:0.12em;margin-top:6px">Store Health Score / 100</div>
            </div>

            <h3 style="font-size:16px;color:#0d0c0a;margin-bottom:12px;font-family:Georgia,serif">Top Findings</h3>
            {findings_html}

            <h3 style="font-size:16px;color:#0d0c0a;margin:20px 0 12px;font-family:Georgia,serif">What To Do This Week</h3>
            {wins_html}

            <div style="margin-top:28px;text-align:center">
                <a href="https://opsintelligence.org/app.html" style="display:inline-block;padding:12px 28px;background:#0d0c0a;color:#ffffff;text-decoration:none;border-radius:100px;font-size:14px;font-weight:500">Open dashboard →</a>
            </div>
        </div>

        <div style="padding:20px 32px;border-top:1px solid #e0d8cc;text-align:center">
            <p style="font-size:11px;color:#8a8070">OPS Intelligence · E-commerce Operations Intelligence</p>
        </div>
    </div>"""

    return await send_email(user_email, f"📊 {shop} Analysis Report — Health Score: {score}/100", html)

# ── Startup: DejaVu fontlarını indir (Türkçe PDF desteği)
@app.on_event("startup")
async def download_fonts():
    import urllib.request
    preferred_dir = os.environ.get("OPS_FONT_DIR", "/app/fonts")
    fallback_dir = os.path.join(os.path.dirname(__file__), "fonts")
    try:
        os.makedirs(preferred_dir, exist_ok=True)
        font_dir = preferred_dir
    except OSError:
        font_dir = fallback_dir
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
SHOPIFY_REQUIRED_SCOPES = [
    "read_orders",
    "read_products",
    "read_inventory",
    "read_fulfillments",
    "read_locations",
]
SHOPIFY_ENV_SCOPES = [s.strip() for s in os.environ.get("SHOPIFY_SCOPES", "").split(",") if s.strip()]
SHOPIFY_SCOPES = ",".join(dict.fromkeys(SHOPIFY_ENV_SCOPES + SHOPIFY_REQUIRED_SCOPES))
SHOPIFY_API_VERSION = os.environ.get("SHOPIFY_API_VERSION", "2026-01")
SHOPIFY_BILLING_TEST = os.environ.get("SHOPIFY_BILLING_TEST", "true").lower() != "false"
SHOPIFY_BILLING_ENABLED = os.environ.get("SHOPIFY_BILLING_ENABLED", "false").lower() in ("1", "true", "yes")
SHOPIFY_BILLING_MODE = os.environ.get("SHOPIFY_BILLING_MODE", "shopify_app_pricing").strip().lower()
SHOPIFY_APP_HANDLE = os.environ.get("SHOPIFY_APP_HANDLE", "ops-intelligence-aurellia").strip()
SHOPIFY_APP_PRICING_HANDLE = os.environ.get("SHOPIFY_APP_PRICING_HANDLE", SHOPIFY_APP_HANDLE).strip()
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
    use_mock: bool = False
    platform: str = "shopify"
    shopify_domain: Optional[str] = None
    shopify_token: Optional[str] = None
    connected_shop: Optional[str] = None
    fast_ai: bool = False
    meta_token: Optional[str] = None
    meta_account: Optional[str] = None
    use_mock_meta: bool = False
    language: str = "tr"

class PDFReportRequest(BaseModel):
    result: Dict[str, Any]
    shop_name: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

class ShopifyConnectStartRequest(BaseModel):
    shop: str

class ShopifyEmbeddedAnalyzeRequest(BaseModel):
    shop: str
    app_token: str


class ShopifyBillingRequest(BaseModel):
    shop: str
    plan: str
    app_token: str

class AIAskRequest(BaseModel):
    question: str
    context: Dict[str, Any] = {}
    mode: str = "founder"
    language: str = "en"


def make_analysis_context(report: dict, shop_name: str, data_source: str, model: str) -> dict:
    counts = report.get("record_counts") or {}
    mode = report.get("source_mode") or ("demo" if data_source == "demo" else "live")
    return {
        "shop_name": shop_name,
        "data_source": data_source,
        "analysis_mode": mode,
        "model": model,
        "record_counts": {
            "orders": int(counts.get("orders") or 0),
            "products": int(counts.get("products") or 0),
        },
    }


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

def make_json_safe(value):
    """Convert pandas/numpy analysis output into strict JSON-safe primitives."""
    try:
        import math
        import numpy as np
        import pandas as pd
    except Exception:
        math = None
        np = None
        pd = None

    if pd is not None:
        if isinstance(value, pd.DataFrame):
            return make_json_safe(value.to_dict("records"))
        if isinstance(value, pd.Series):
            return make_json_safe(value.tolist())
        if value is pd.NaT:
            return None

    if np is not None:
        if isinstance(value, np.generic):
            return make_json_safe(value.item())
        if isinstance(value, np.ndarray):
            return make_json_safe(value.tolist())

    if isinstance(value, dict):
        return {str(k): make_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [make_json_safe(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        if math is not None and not math.isfinite(value):
            return None
        return value
    return value

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
        raise HTTPException(status_code=401, detail="Session expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token.")


def strip_shopify_url(value: str) -> str:
    return (
        (value or "")
        .strip()
        .lower()
        .replace("https://", "")
        .replace("http://", "")
        .replace("/admin", "")
        .split("/")[0]
    )


def verify_shopify_session_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(status_code=500, detail="Shopify app credentials are missing.")
    try:
        payload = jwt.decode(
            credentials.credentials,
            SHOPIFY_API_SECRET,
            algorithms=["HS256"],
            audience=SHOPIFY_API_KEY,
            leeway=10,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Shopify session token expired. Retry the request.")
    except jwt.ImmatureSignatureError:
        raise HTTPException(status_code=401, detail="Shopify session token is not active yet.")
    except jwt.InvalidAudienceError:
        raise HTTPException(status_code=401, detail="Shopify session token audience is invalid.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid Shopify session token.")

    dest_shop = normalize_shop_domain(strip_shopify_url(payload.get("dest", "")))
    iss_shop = normalize_shop_domain(strip_shopify_url(payload.get("iss", "")))
    if dest_shop != iss_shop:
        raise HTTPException(status_code=401, detail="Shopify session token shop mismatch.")

    payload["shop"] = dest_shop
    return payload


def normalize_shop_domain(shop: str) -> str:
    shop = (shop or "").strip().lower()
    shop = shop.replace("https://", "").replace("http://", "").split("/")[0]
    if shop and "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*\.myshopify\.com", shop or ""):
        raise HTTPException(status_code=400, detail="Enter a valid Shopify store domain.")
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
        raise HTTPException(status_code=400, detail="Shopify connection session expired. Try again.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid Shopify connection session.")
    if payload.get("shop") != shop:
        raise HTTPException(status_code=400, detail="Shopify store verification failed.")
    return payload


def normalize_store_url(store_url: str) -> str:
    value = (store_url or "").strip()
    if not value:
        raise HTTPException(status_code=400, detail="Enter your WooCommerce store URL.")
    if not re.match(r"^https?://", value, flags=re.IGNORECASE):
        value = f"https://{value}"
    value = value.rstrip("/")
    if not re.fullmatch(r"https?://[^/]+\S*", value, flags=re.IGNORECASE):
        raise HTTPException(status_code=400, detail="Enter a valid WooCommerce store URL.")
    return value


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


def verify_shopify_webhook(raw_body: bytes, hmac_header: str) -> bool:
    if not SHOPIFY_API_SECRET or not hmac_header:
        return False
    digest = hmac.new(SHOPIFY_API_SECRET.encode(), raw_body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, hmac_header)


def build_shopify_install_url(shop: str) -> str:
    shop_domain = normalize_shop_domain(shop)
    state = create_shopify_state(f"shopify:{shop_domain}", shop_domain, mode="embedded")
    redirect_uri = f"{BACKEND_PUBLIC_URL}/shopify/callback"
    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"https://{shop_domain}/admin/oauth/authorize?{urlencode(params, doseq=True)}"


def build_shopify_app_launch_url(shop: str, app_token: str, section: str = "") -> str:
    params = {"shop": normalize_shop_domain(shop), "app_token": app_token}
    if section:
        params["section"] = section
    return f"{BACKEND_PUBLIC_URL}/shopify/app/launch?{urlencode(params)}"


def shopify_store_handle(shop: str) -> str:
    return normalize_shop_domain(shop).split(".myshopify.com")[0]


def build_shopify_app_pricing_url(shop: str) -> str:
    if not SHOPIFY_APP_PRICING_HANDLE:
        raise HTTPException(status_code=500, detail="SHOPIFY_APP_PRICING_HANDLE is missing.")
    return (
        f"https://admin.shopify.com/store/{quote(shopify_store_handle(shop))}"
        f"/charges/{quote(SHOPIFY_APP_PRICING_HANDLE)}/pricing_plans"
    )


def plan_from_shopify_handle(value: str) -> str:
    normalized = (value or "").strip().lower()
    if "pro" in normalized:
        return "pro"
    if "starter" in normalized:
        return "starter"
    return ""


def shopify_billing_fallback_response(shop: str, app_token: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=409,
        content={
            "success": False,
            "detail": message,
            "fallback_url": build_shopify_app_launch_url(shop, app_token, "plans"),
        },
    )


def connected_shopify_stores(stores: list) -> list[dict]:
    if not isinstance(stores, list):
        return []
    return [
        store
        for store in stores
        if isinstance(store, dict)
        and store.get("platform") == "shopify"
        and store.get("status") == "connected"
    ]


def active_shopify_billing_store(stores: list) -> Optional[dict]:
    for store in connected_shopify_stores(stores):
        if (
            store.get("billing_provider") == "shopify"
            and store.get("billing_status") == "active"
            and store.get("billing_plan") in ("starter", "pro")
        ):
            return store
    return None


def normalize_plan_key(plan: str) -> str:
    return plan if plan in PLANS else "free"


def get_user_billing_state(email: str) -> dict:
    db = get_supabase()
    result = db.table("users").select("email,plan,stores").eq("email", email).execute()
    user = result.data[0] if result.data else {}
    stores = user.get("stores") or []
    if not isinstance(stores, list):
        stores = []

    shopify_stores = connected_shopify_stores(stores)
    active_shopify = active_shopify_billing_store(stores)
    plan = normalize_plan_key(user.get("plan", "free") if user else "free")
    if active_shopify:
        shopify_plan = normalize_plan_key(active_shopify.get("billing_plan", "free"))
        if shopify_plan != plan:
            db.table("users").update({"plan": shopify_plan}).eq("email", email).execute()
            plan = shopify_plan
    provider = "shopify" if active_shopify else ("stripe" if plan in ("starter", "pro") else "none")
    billing_shop = active_shopify or (shopify_stores[0] if shopify_stores else None)

    pricing_url = ""
    if billing_shop:
        try:
            pricing_url = build_shopify_app_pricing_url(billing_shop.get("domain", ""))
        except Exception:
            pricing_url = ""

    return {
        "email": email,
        "plan": plan,
        "billing_provider": provider,
        "has_shopify_store": bool(shopify_stores),
        "shopify_billing_active": bool(active_shopify),
        "shopify_shop": (billing_shop or {}).get("domain", ""),
        "shopify_pricing_url": pricing_url,
        "source_of_truth": provider,
        "is_locked_to_shopify": bool(shopify_stores),
        "can_use_stripe_checkout": not bool(shopify_stores),
        "manage_url": pricing_url if billing_shop else "",
        "message": (
            "Plan is managed through Shopify Billing for this connected store."
            if active_shopify
            else (
                "This account has a connected Shopify store. Upgrade or change plans through Shopify to avoid duplicate billing."
                if shopify_stores
                else "Plan is managed through OPS web billing."
            )
        ),
    }


def exchange_shopify_id_token(shop: str, id_token: str) -> dict:
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(status_code=500, detail="Shopify app credentials are missing.")
    response = requests.post(
        f"https://{shop}/admin/oauth/access_token",
        data={
            "client_id": SHOPIFY_API_KEY,
            "client_secret": SHOPIFY_API_SECRET,
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "subject_token": id_token,
            "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
            "requested_token_type": "urn:shopify:params:oauth:token-type:offline-access-token",
            "expiring": "0",
        },
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
        timeout=30,
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Shopify token exchange did not return an access token.")
    return ensure_shopify_user(shop, access_token, token_data.get("scope", SHOPIFY_SCOPES))


def render_shopify_install_required(shop: str) -> HTMLResponse:
    install_url = build_shopify_install_url(shop)
    response = HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta name="shopify-api-key" content="{SHOPIFY_API_KEY}">
  <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
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
    response.headers["Content-Security-Policy"] = f"frame-ancestors https://{shop} https://admin.shopify.com;"
    return response


def render_shopify_missing_shop() -> HTMLResponse:
    response = HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OPS Intelligence for Shopify</title>
  <style>
    body{{margin:0;background:#faf8f4;color:#17140f;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}}
    .wrap{{min-height:100vh;display:grid;place-items:center;padding:28px}}
    .card{{max-width:680px;background:#fff;border:1px solid #e0d8cc;border-radius:18px;padding:30px;box-shadow:0 16px 42px rgba(30,24,10,.08)}}
    .k{{font-size:11px;font-weight:900;letter-spacing:.14em;text-transform:uppercase;color:#c89124;margin-bottom:10px}}
    h1{{font-size:36px;line-height:1.05;letter-spacing:-.045em;margin:0 0 12px}}
    p{{color:#756f64;line-height:1.65;margin:0 0 16px}}
    a{{display:inline-flex;border-radius:12px;background:#11100c;color:#fff;padding:13px 16px;font-weight:800;text-decoration:none;margin-top:8px}}
    code{{background:#f4efe5;border:1px solid #e1d8c9;border-radius:8px;padding:2px 6px}}
  </style>
</head>
<body>
  <div class="wrap">
    <section class="card">
      <div class="k">Shopify app URL ready</div>
      <h1>Open OPS from a Shopify store.</h1>
      <p>This endpoint is healthy, but Shopify did not provide a <code>shop</code> parameter. Install or open OPS from Shopify Admin so the app can identify the merchant store and sync live orders, products, inventory, fulfillment, and locations.</p>
      <p>Expected format: <code>/shopify/app?shop=your-store.myshopify.com</code></p>
      <a href="{FRONTEND_PUBLIC_URL}/app.html" target="_top">Open OPS web workspace</a>
    </section>
  </div>
</body>
</html>
""")
    response.headers["Content-Security-Policy"] = "frame-ancestors https://admin.shopify.com;"
    return response


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
        f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/shop.json",
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
    user_result = db.table("users").select("plan,stores").eq("email", email).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found.")

    user = user_result.data[0]
    stores = user.get("stores") or []
    if not isinstance(stores, list):
        stores = []
    ensure_store_slot_available(stores, user.get("plan", "free"), "shopify", shop)

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
            for key in ("billing_provider", "billing_plan", "billing_status", "billing_pending_plan", "billing_updated_at"):
                if store.get(key):
                    store_record[key] = store.get(key)
            stores[idx] = store_record
            replaced = True
            break
    if not replaced:
        stores.append(store_record)

    db.table("users").update({"stores": stores}).eq("email", email).execute()
    safe_record = {k: v for k, v in store_record.items() if k != "access_token"}
    return safe_record


def mark_shopify_billing(email: str, shop: str, plan: str, status: str = "active") -> None:
    if plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Invalid Shopify billing plan.")

    shop_domain = normalize_shop_domain(shop)
    db = get_supabase()
    result = db.table("users").select("stores").eq("email", email).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found.")

    stores = result.data[0].get("stores") or []
    if not isinstance(stores, list):
        stores = []

    now = datetime.utcnow().isoformat()
    for store in stores:
        if (
            isinstance(store, dict)
            and store.get("platform") == "shopify"
            and store.get("domain") == shop_domain
        ):
            store["billing_provider"] = "shopify"
            store["billing_plan"] = plan
            store["billing_status"] = status
            store["billing_updated_at"] = now
            store.pop("billing_pending_plan", None)
            break

    db.table("users").update({"plan": plan, "stores": stores}).eq("email", email).execute()


def clear_shopify_billing(email: str, shop: str, status: str = "cancelled") -> None:
    shop_domain = normalize_shop_domain(shop)
    db = get_supabase()
    result = db.table("users").select("stores").eq("email", email).execute()
    if not result.data:
        return

    stores = result.data[0].get("stores") or []
    if not isinstance(stores, list):
        stores = []

    now = datetime.utcnow().isoformat()
    changed = False
    for store in stores:
        if (
            isinstance(store, dict)
            and store.get("platform") == "shopify"
            and store.get("domain") == shop_domain
        ):
            store["billing_provider"] = "shopify"
            store["billing_status"] = status
            store["billing_updated_at"] = now
            store.pop("billing_pending_plan", None)
            changed = True

    if changed:
        remaining_active = active_shopify_billing_store(stores)
        next_plan = normalize_plan_key((remaining_active or {}).get("billing_plan", "free"))
        db.table("users").update({"plan": next_plan, "stores": stores}).eq("email", email).execute()


def mark_shopify_billing_intent(email: str, shop: str, plan: str) -> None:
    if plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Invalid Shopify billing plan.")

    shop_domain = normalize_shop_domain(shop)
    db = get_supabase()
    result = db.table("users").select("stores").eq("email", email).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found.")

    stores = result.data[0].get("stores") or []
    if not isinstance(stores, list):
        stores = []

    now = datetime.utcnow().isoformat()
    for store in stores:
        if (
            isinstance(store, dict)
            and store.get("platform") == "shopify"
            and store.get("domain") == shop_domain
        ):
            store["billing_provider"] = "shopify"
            store["billing_pending_plan"] = plan
            store["billing_status"] = store.get("billing_status") or "pending"
            store["billing_updated_at"] = now
            break

    db.table("users").update({"stores": stores}).eq("email", email).execute()


def connected_store_count(stores: list, platform: str = "shopify") -> int:
    if not isinstance(stores, list):
        return 0
    return sum(
        1
        for store in stores
        if isinstance(store, dict)
        and store.get("platform") == platform
        and store.get("status") == "connected"
    )


def store_already_connected(stores: list, platform: str, domain: str) -> bool:
    if not isinstance(stores, list):
        return False
    return any(
        isinstance(store, dict)
        and store.get("platform") == platform
        and store.get("domain") == domain
        and store.get("status") == "connected"
        for store in stores
    )


def ensure_store_slot_available(stores: list, plan_key: str, platform: str, domain: str) -> None:
    if store_already_connected(stores, platform, domain):
        return
    plan = PLANS.get(plan_key or "free", PLANS["free"])
    max_stores = int(plan.get("max_stores", 1))
    used = connected_store_count(stores, platform)
    if used >= max_stores:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Store limit reached for the {plan.get('name', plan_key).title()} plan "
                f"({used}/{max_stores}). Upgrade your plan or connect this store with a separate account."
            ),
        )


def disconnect_shopify_store(shop: str) -> None:
    db = get_supabase()
    result = db.table("users").select("email,stores").execute()
    for user in result.data or []:
        stores = user.get("stores") or []
        if not isinstance(stores, list):
            continue
        changed = False
        for store in stores:
            if isinstance(store, dict) and store.get("platform") == "shopify" and store.get("domain") == shop:
                store["status"] = "uninstalled"
                store.pop("access_token", None)
                store["updated_at"] = datetime.utcnow().isoformat()
                changed = True
        if changed:
            db.table("users").update({"stores": stores}).eq("email", user["email"]).execute()


def redact_shopify_store_data(shop: str) -> int:
    db = get_supabase()
    result = db.table("users").select("email,stores").execute()
    changed_users = 0
    for user in result.data or []:
        stores = user.get("stores") or []
        if not isinstance(stores, list):
            continue
        redacted_stores = []
        changed = False
        for store in stores:
            if (
                isinstance(store, dict)
                and store.get("platform") == "shopify"
                and store.get("domain") == shop
            ):
                changed = True
                continue
            redacted_stores.append(store)
        if changed:
            db.table("users").update({"stores": redacted_stores}).eq("email", user["email"]).execute()
            changed_users += 1
    return changed_users


def parse_shopify_webhook_json(raw_body: bytes) -> dict:
    try:
        payload = json.loads(raw_body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    return payload if isinstance(payload, dict) else {}


def shop_domain_from_privacy_payload(payload: dict, request: Request) -> str:
    shop = (
        payload.get("shop_domain")
        or payload.get("shop")
        or request.headers.get("X-Shopify-Shop-Domain", "")
    )
    return normalize_shop_domain(shop)


def redact_customer_data(payload: dict) -> dict:
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    return {
        "customer_id": customer.get("id") or payload.get("customer_id"),
        "redacted": True,
        "stored_customer_profiles": 0,
        "note": "OPS stores Shopify tokens and aggregate analysis output, not Shopify customer profiles.",
    }


def customer_data_response(payload: dict) -> dict:
    customer = payload.get("customer") if isinstance(payload.get("customer"), dict) else {}
    return {
        "customer_id": customer.get("id") or payload.get("customer_id"),
        "data": [],
        "note": "OPS stores aggregate operational analysis output and does not persist Shopify customer profiles.",
    }


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
        "billing_provider": store.get("billing_provider", ""),
        "billing_plan": store.get("billing_plan", ""),
        "billing_status": store.get("billing_status", ""),
    }


def build_daily_revenue_points(report: dict) -> list[dict]:
    series = ((report.get("revenue") or {}).get("daily_revenue_series"))
    if series is None:
        return []
    points = []
    try:
        for day, amount in series.items():
            label = day.isoformat() if hasattr(day, "isoformat") else str(day)
            points.append({
                "date": label,
                "revenue": round(float(amount or 0), 2),
            })
    except Exception:
        return []
    return points


def build_metrics_payload(report: dict) -> dict:
    ft = report.get("fulfillment_time", {}) or {}
    rev = report.get("revenue", {}) or {}
    inv = report.get("inventory", {}) or {}
    inventory_details = inv.get("details")
    inventory_products = inventory_details.to_dict("records") if hasattr(inventory_details, "to_dict") else []
    for product in inventory_products:
        product["current_stock"] = product.get("inventory", 0)
    return {
        "fulfillment": {
            "mean": ft.get("mean", 0),
            "median": ft.get("median", 0),
            "p95": ft.get("p95", 0),
            "over72h": ft.get("orders_over_72h", 0),
            "status": ft.get("status", "Unknown"),
            "total": ft.get("total_fulfilled", 0),
        },
        "revenue": {
            "total": rev.get("total_revenue", 0),
            "orders": rev.get("total_orders", 0),
            "aov": rev.get("aov", 0),
            "cancel_rate": rev.get("cancellation_rate", 0),
            "refund_rate": rev.get("refund_rate", 0),
        },
        "inventory": {
            "avg_turnover": inv.get("avg_turnover", 0),
            "critical_count": len(inv["critical_items"]) if inv.get("critical_items") is not None else 0,
            "products": inventory_products,
        },
    }


def find_upload_column(df: pd.DataFrame, candidates: list[str]) -> Optional[str]:
    normalized = {
        re.sub(r"[^a-z0-9]+", "", str(col).lower()): col
        for col in df.columns
    }
    for candidate in candidates:
        key = re.sub(r"[^a-z0-9]+", "", candidate.lower())
        if key in normalized:
            return normalized[key]
    for key, col in normalized.items():
        if any(re.sub(r"[^a-z0-9]+", "", c.lower()) in key for c in candidates):
            return col
    return None


def read_upload_dataframe(filename: str, content: bytes) -> pd.DataFrame:
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(content))
    return pd.read_excel(io.BytesIO(content))


def build_report_from_upload(df: pd.DataFrame, platform: str, filename: str) -> dict:
    if df.empty:
        raise HTTPException(status_code=400, detail="The uploaded file has no rows.")

    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    id_col = find_upload_column(df, ["order_id", "order id", "order", "name", "order number", "amazon order id", "etsy order id"])
    date_col = find_upload_column(df, ["created_at", "created at", "date", "order date", "purchase date", "paid at"])
    fulfilled_col = find_upload_column(df, ["fulfilled_at", "fulfilled at", "shipped at", "shipment date", "dispatch date"])
    status_col = find_upload_column(df, ["fulfillment_status", "fulfillment status", "status", "order status"])
    total_col = find_upload_column(df, ["total_price", "total price", "total", "order total", "amount", "revenue", "sales", "gross sales"])
    qty_col = find_upload_column(df, ["item_count", "item count", "quantity", "qty", "items"])
    email_col = find_upload_column(df, ["customer_email", "customer email", "email", "buyer email"])
    product_col = find_upload_column(df, ["product_title", "product title", "product", "item name", "title", "sku title"])
    sku_col = find_upload_column(df, ["sku", "seller sku", "merchant sku"])
    inventory_col = find_upload_column(df, ["inventory", "stock", "current stock", "quantity available"])
    price_col = find_upload_column(df, ["price", "item price", "unit price"])
    category_col = find_upload_column(df, ["category", "product type", "type"])

    if not total_col:
        raise HTTPException(status_code=400, detail="Could not find a revenue/total column in the uploaded file.")

    order_ids = df[id_col].astype(str) if id_col else pd.Series([f"upload-{i+1}" for i in range(len(df))])
    created = pd.to_datetime(df[date_col], utc=True, errors="coerce") if date_col else pd.Series(pd.Timestamp.utcnow(), index=df.index)
    created = created.fillna(pd.Timestamp.utcnow())
    fulfilled = pd.to_datetime(df[fulfilled_col], utc=True, errors="coerce") if fulfilled_col else created + pd.to_timedelta(36, unit="h")

    status_raw = df[status_col].astype(str).str.lower() if status_col else pd.Series("fulfilled", index=df.index)
    fulfillment_status = np.where(
        status_raw.str.contains("cancel", na=False),
        "cancelled",
        np.where(status_raw.str.contains("refund|return", na=False), "refunded", "fulfilled"),
    )

    totals = pd.to_numeric(
        df[total_col].astype(str).str.replace(r"[^0-9,.-]", "", regex=True).str.replace(",", ".", regex=False),
        errors="coerce",
    ).fillna(0)
    qty = pd.to_numeric(df[qty_col], errors="coerce").fillna(1).clip(lower=1).astype(int) if qty_col else pd.Series(1, index=df.index)
    product_titles = df[product_col].fillna("Uploaded product").astype(str) if product_col else pd.Series("Uploaded product", index=df.index)
    skus = df[sku_col].fillna("").astype(str) if sku_col else pd.Series("", index=df.index)
    emails = df[email_col].fillna("").astype(str) if email_col else pd.Series("", index=df.index)

    line_items = []
    for idx in df.index:
        line_items.append([{
            "title": product_titles.loc[idx],
            "sku": skus.loc[idx],
            "quantity": int(qty.loc[idx] or 1),
        }])

    orders_df = pd.DataFrame({
        "order_id": order_ids,
        "created_at": created,
        "fulfilled_at": fulfilled,
        "fulfillment_status": fulfillment_status,
        "total_price": totals,
        "item_count": qty,
        "customer_email": emails,
        "product_title": product_titles,
        "line_items": line_items,
    })

    grouped = pd.DataFrame({
        "title": product_titles,
        "sku": skus,
        "price": pd.to_numeric(df[price_col], errors="coerce") if price_col else totals / qty.replace(0, 1),
        "inventory": pd.to_numeric(df[inventory_col], errors="coerce") if inventory_col else pd.Series(50, index=df.index),
        "category": df[category_col].fillna("Uploaded").astype(str) if category_col else pd.Series(platform.title(), index=df.index),
    }).groupby(["title", "sku"], dropna=False).agg({
        "price": "mean",
        "inventory": "max",
        "category": "first",
    }).reset_index()

    if grouped.empty:
        grouped = pd.DataFrame([{"title": "Uploaded product", "sku": "", "price": float(totals.mean() or 0), "inventory": 50, "category": platform.title()}])

    products_df = grouped.reset_index().rename(columns={"index": "product_id"})
    products_df["product_id"] = products_df["product_id"] + 1
    products_df["variant_id"] = products_df["product_id"]
    products_df["price"] = pd.to_numeric(products_df["price"], errors="coerce").fillna(0)
    products_df["cost"] = (pd.to_numeric(products_df["price"], errors="coerce").fillna(0) * 0.55).round(2)
    products_df["inventory"] = pd.to_numeric(products_df["inventory"], errors="coerce").fillna(0).astype(int)
    products_df["created_at"] = pd.Timestamp.utcnow()
    products_df["margin_pct"] = np.where(products_df["price"] > 0, ((products_df["price"] - products_df["cost"]) / products_df["price"] * 100).round(1), 0)

    engine = MetricsEngine(orders_df, products_df)
    report = engine.full_report()
    report["orders_df"] = orders_df
    report["products_df"] = products_df
    report["source_platform"] = platform
    report["source_mode"] = "upload"
    report["upload_filename"] = filename
    report["record_counts"] = {"orders": int(len(orders_df)), "products": int(len(products_df))}
    return report


# ─────────────────────────────────────────────
# PLAN TANIMLARI
# ─────────────────────────────────────────────

PLANS = {
    "free":    {"name": "Free", "price": 0,  "max_stores": 1,  "max_orders": 100,  "ai": False, "pdf": False, "meta": False},
    "starter": {"name": "Starter",  "price": 29, "max_stores": 1,  "max_orders": 1000, "ai": True,  "pdf": True,  "meta": True},
    "pro":     {"name": "Pro",      "price": 79, "max_stores": 3,  "max_orders": 10000,"ai": True,  "pdf": True,  "meta": True},
}


def analysis_limit_for_plan(plan: dict) -> int:
    return max(1, int(plan.get("max_orders", 0) // 100))


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
        raise HTTPException(status_code=400, detail="This email is already registered.")

    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

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
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    user = result.data[0]
    if not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="This account is disabled.")

    billing_state = get_user_billing_state(email)
    effective_plan = billing_state.get("plan", user["plan"])
    token = create_token(email, effective_plan)
    return {
        "success": True,
        "token": token,
        "user": {
            "email": user["email"],
            "name": user["name"],
            "plan": effective_plan,
            "analyses_this_month": user.get("analyses_this_month", 0),
            "billing": billing_state,
        },
    }


@app.get("/auth/me")
async def me(payload: dict = Depends(verify_token)):
    db = get_supabase()
    result = db.table("users").select("email,name,plan,analyses_this_month,stores").eq(
        "email", payload["sub"]
    ).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="User not found.")

    user = result.data[0]
    billing_state = get_user_billing_state(payload["sub"])
    user["plan"] = billing_state.get("plan", user.get("plan", "free"))
    user["stores"] = [
        public_store(store)
        for store in (user.get("stores") or [])
        if isinstance(store, dict)
    ]
    plan = PLANS.get(user["plan"], PLANS["free"])
    return {
        "user": user,
        "plan": plan,
        "billing": billing_state,
    }


# ─────────────────────────────────────────────
# SHOPIFY APP INSTALL / OAUTH
# ─────────────────────────────────────────────

@app.get("/screencast", response_class=HTMLResponse)
async def app_review_screencast():
    return FileResponse(os.path.join(os.path.dirname(__file__), "screencast.html"))


@app.get("/shopify/install")
async def shopify_install(shop: str):
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(status_code=500, detail="Shopify OAuth environment variables are missing.")

    shop_domain = normalize_shop_domain(shop)
    install_url = build_shopify_install_url(shop_domain)
    return RedirectResponse(install_url)


@app.get("/shopify/app", response_class=HTMLResponse)
async def shopify_app_home(request: Request):
    params = dict(request.query_params)
    raw_shop = params.get("shop", "")
    if not raw_shop:
        return render_shopify_missing_shop()
    try:
        shop = normalize_shop_domain(raw_shop)
    except HTTPException:
        return render_shopify_missing_shop()
    id_token = params.get("id_token", "")
    if id_token and verify_shopify_hmac(params):
        try:
            exchange_shopify_id_token(shop, id_token)
        except requests.exceptions.HTTPError as e:
            print(f"Shopify token exchange HTTP error for {shop}: {e}")
        except requests.exceptions.RequestException as e:
            print(f"Shopify token exchange failed for {shop}: {e}")
        except HTTPException as e:
            print(f"Shopify token exchange rejected for {shop}: {e.detail}")

    try:
        connected = find_shopify_store_by_domain(shop)
    except Exception as e:
        logger.warning("Shopify app store lookup failed for %s: %s", shop, e)
        connected = None
    if not connected:
        return render_shopify_install_required(shop)

    user = connected["user"]
    store = connected["store"]
    plan_key = user.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])
    app_token = create_shopify_embedded_token(user["email"], shop)
    safe_scope = (store.get("scope") or "").replace("<", "").replace(">", "")
    used = int(user.get("analyses_this_month") or 0)
    max_analyses = analysis_limit_for_plan(plan)
    usage_pct = min(100, int((used / max(max_analyses, 1)) * 100))
    ops_launch_url = build_shopify_app_launch_url(shop, app_token)
    ops_plans_url = build_shopify_app_launch_url(shop, app_token, "plans")
    install_url = build_shopify_install_url(shop)
    if SHOPIFY_BILLING_MODE in ("shopify_app_pricing", "app_pricing", "managed_pricing"):
        billing_status = "Shopify App Pricing"
    elif SHOPIFY_BILLING_MODE == "billing_api" and SHOPIFY_BILLING_ENABLED:
        billing_status = "Billing API enabled"
    else:
        billing_status = "pending Partner app migration"

    response = HTMLResponse(f"""
<!doctype html>
<html>
<head>
  <meta name="shopify-api-key" content="{SHOPIFY_API_KEY}">
  <script src="https://cdn.shopify.com/shopifycloud/app-bridge.js"></script>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>OPS Intelligence</title>
  <style>
    :root{{--ink:#17140f;--muted:#756f64;--line:#ded7cc;--soft:#f4f1ea;--gold:#d39b2a;--green:#0f7a4a;--purple:#cfc5ff}}
    *{{box-sizing:border-box}}
    body{{margin:0;background:#f2f1ef;color:var(--ink);font-family:-apple-system,BlinkMacSystemFont,'Inter','Segoe UI',sans-serif}}
    .shell{{max-width:1240px;margin:0 auto;padding:24px 28px 42px}}
    .appbar{{height:64px;background:#fff;border:1px solid #ddd8cf;border-radius:16px;padding:0 20px;display:flex;align-items:center;justify-content:space-between;gap:16px;box-shadow:0 1px 0 rgba(0,0,0,.04)}}
    .brand{{display:flex;align-items:center;gap:12px;font-weight:800;font-size:21px;letter-spacing:-.03em}}
    .mark{{width:34px;height:34px;border-radius:9px;background:#11100c;color:#fff;display:grid;place-items:center;font-family:Georgia,serif;font-size:18px}}
    .muted{{color:var(--muted)}} .small{{font-size:12px;line-height:1.5}}
    .actions{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
    button,a.btn{{appearance:none;border:0;border-radius:12px;background:#25221c;color:#fff;padding:12px 16px;font-weight:800;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;justify-content:center;gap:8px;box-shadow:inset 0 1px 0 rgba(255,255,255,.12)}}
    button.secondary,a.secondary{{background:#fff;color:#25221c;border:1px solid #d8d2c7;box-shadow:none}}
    .hero{{margin-top:24px;background:linear-gradient(135deg,#fff 0%,#faf6ec 58%,#efe2c4 100%);border:1px solid rgba(211,155,42,.22);border-radius:20px;padding:26px;display:grid;grid-template-columns:1.15fr .85fr;gap:22px;box-shadow:0 18px 44px rgba(26,21,12,.07)}}
    h1{{font-size:34px;line-height:1.05;letter-spacing:-.045em;margin:0 0 10px}}
    .kicker{{font-size:11px;text-transform:uppercase;letter-spacing:.14em;color:var(--gold);font-weight:900;margin-bottom:10px}}
    .hero p{{margin:0;color:var(--muted);font-size:15px;line-height:1.6;max-width:68ch}}
    .banner{{background:#cec6ff;border:1px solid #b7acf6;border-radius:16px;padding:18px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px}}
    .banner strong{{display:block;font-size:20px;letter-spacing:-.03em;margin-bottom:5px}} .banner span{{font-size:13px;color:#504b66;line-height:1.45}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}}
    .card{{background:#fff;border:1px solid #ddd8cf;border-radius:18px;padding:22px;box-shadow:0 12px 32px rgba(26,21,12,.06)}}
    .card-head{{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px}}
    h2{{font-size:22px;letter-spacing:-.035em;margin:0}} h3{{font-size:16px;margin:0 0 4px}}
    .pill{{display:inline-flex;border-radius:999px;background:rgba(15,122,74,.09);border:1px solid rgba(15,122,74,.18);color:var(--green);padding:7px 10px;font-size:11px;font-weight:900;letter-spacing:.07em;text-transform:uppercase}}
    .stats{{display:grid;grid-template-columns:repeat(4,1fr);border:1px solid #e3ded5;border-radius:16px;overflow:hidden;background:#fff;margin-top:16px}}
    .stat{{padding:20px;text-align:center;border-right:1px solid #e3ded5}} .stat:last-child{{border-right:0}}
    .label{{font-size:12px;color:var(--muted);margin-bottom:8px}} .value{{font-size:31px;font-weight:800;letter-spacing:-.04em}}
    .row{{display:flex;justify-content:space-between;gap:12px;padding:12px 0;border-bottom:1px solid #eee9df;font-size:14px}}
    .row:last-child{{border-bottom:0}} .scope{{max-width:58%;text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
    .usage{{height:8px;border-radius:999px;background:#eee8dc;overflow:hidden;margin-top:8px}} .usage span{{display:block;height:100%;width:{usage_pct}%;background:linear-gradient(90deg,var(--gold),#ebc66d)}}
    .plan-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:16px}}
    .plan{{border:1px solid #e1dbd1;border-radius:15px;padding:15px;background:#fbfaf7}} .plan.active{{background:#18150f;color:#fff;border-color:#18150f}}
    .plan-name{{font-size:12px;text-transform:uppercase;letter-spacing:.11em;color:var(--muted);font-weight:900}} .plan.active .plan-name{{color:rgba(255,255,255,.55)}}
    .price{{font-size:30px;font-weight:900;margin:8px 0 4px;letter-spacing:-.04em}} .plan-copy{{font-size:12px;line-height:1.45;color:var(--muted)}} .plan.active .plan-copy{{color:rgba(255,255,255,.62)}}
    #result{{white-space:pre-wrap;background:#18150f;color:#f8f1df;border-radius:15px;padding:16px;font-size:13px;line-height:1.55;min-height:112px;margin-top:16px}}
    .ops-list{{display:grid;gap:12px}}
    .ops-item{{display:grid;grid-template-columns:42px 1fr auto;gap:14px;align-items:center;border:1px solid #e5dfd4;border-radius:15px;padding:14px;background:#fff}}
    .ico{{width:42px;height:42px;border-radius:12px;background:#f3ecd9;color:#a87314;display:grid;place-items:center;font-weight:900}}
    @media(max-width:900px){{.hero,.grid{{grid-template-columns:1fr}}.stats,.plan-grid{{grid-template-columns:1fr 1fr}}.actions{{justify-content:flex-start}}}}
    @media(max-width:560px){{.shell{{padding:14px}}.appbar{{height:auto;align-items:flex-start;flex-direction:column}}.hero{{padding:18px}}.stats,.plan-grid{{grid-template-columns:1fr}}.stat{{border-right:0;border-bottom:1px solid #e3ded5}}.stat:last-child{{border-bottom:0}}.scope{{max-width:100%;white-space:normal;text-align:left}}.row{{flex-direction:column}}}}
  </style>
</head>
<body>
  <div class="shell">
    <div class="appbar">
      <div class="brand"><div class="mark">O</div><div>OPS Intelligence<div class="small muted">Embedded Shopify app for {shop}</div></div></div>
      <div class="actions">
        <button class="secondary" onclick="reinstallPermissions()">Reinstall permissions</button>
        <button onclick="openOpsDashboard()">Go to OPS Intelligence →</button>
      </div>
    </div>

    <section class="hero">
      <div>
        <div class="kicker">Operations intelligence</div>
        <h1>Your Shopify store is connected to OPS.</h1>
        <p>Use this Shopify app home as the lightweight control room. Run a quick live check here, manage plan access through Shopify Billing, then open the full OPS workspace for deeper analysis, product tables, forecasts, churn, pricing, ledger and team workflows.</p>
      </div>
      <div class="banner">
        <div><strong>Founder-ready brief</strong><span>Live store data stays labeled, scoped, and separated from demo results.</span></div>
        <button class="secondary" onclick="runAnalysis()">Run quick check</button>
      </div>
    </section>

    <section class="stats">
      <div class="stat"><div class="label">Plan</div><div class="value">{plan_key.title()}</div></div>
      <div class="stat"><div class="label">Monthly usage</div><div class="value">{used}/{max_analyses}</div></div>
      <div class="stat"><div class="label">Store</div><div class="value" style="font-size:18px">{shop.split('.')[0]}</div></div>
      <div class="stat"><div class="label">Access</div><div class="value" style="color:var(--green)">Live</div></div>
    </section>

    <div class="grid">
      <section class="card">
        <div class="card-head"><div><h2>Connection status</h2><div class="small muted">Permissions and usage for this Shopify install.</div></div><span class="pill">Connected</span></div>
        <div class="row"><span>Shop domain</span><strong>{shop}</strong></div>
        <div class="row"><span>Plan</span><strong>{plan_key.title()}</strong></div>
        <div class="row"><span>Usage</span><strong>{used}/{max_analyses} analyses</strong></div>
        <div class="usage"><span></span></div>
        <div class="row"><span>Permissions</span><span class="muted scope" title="{safe_scope}">{safe_scope}</span></div>
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:18px">
          <button onclick="runAnalysis()">Analyze Shopify data</button>
          <button class="secondary" onclick="openOpsDashboard()">Open full OPS dashboard</button>
        </div>
        <div id="result">Ready. Click “Analyze Shopify data” to fetch orders/products and produce a live summary. For the full report and all product rows, use “Go to OPS Intelligence”.</div>
      </section>
      <section class="card">
        <div class="card-head"><div><h2>Plans & Shopify Billing</h2><div class="small muted">Merchants can upgrade without leaving Shopify.</div></div></div>
        <div class="plan-grid">
          <div class="plan {'active' if plan_key == 'free' else ''}"><div class="plan-name">Free</div><div class="price">€0</div><div class="plan-copy">1 store, basic live check.</div></div>
          <div class="plan {'active' if plan_key == 'starter' else ''}"><div class="plan-name">Starter</div><div class="price">€29</div><div class="plan-copy">1 store, AI brief, PDF, 10 analyses.</div><button class="secondary" style="margin-top:12px;width:100%" onclick="startBilling('starter')">Choose Starter</button></div>
          <div class="plan {'active' if plan_key == 'pro' else ''}"><div class="plan-name">Pro</div><div class="price">€79</div><div class="plan-copy">3 stores, forecast, churn, pricing.</div><button class="secondary" style="margin-top:12px;width:100%" onclick="startBilling('pro')">Choose Pro</button></div>
        </div>
        <p class="small muted">Billing status: {billing_status}. Paid plan buttons open Shopify-hosted plan selection when the app has Partner-owned pricing configured; otherwise OPS opens its own billing page as a fallback.</p>
      </section>
    </div>

    <section class="card" style="margin-top:18px">
      <div class="card-head"><div><h2>What merchants do here</h2><div class="small muted">A Shopify-native landing area, with deep analysis handled in OPS.</div></div></div>
      <div class="ops-list">
        <div class="ops-item"><div class="ico">1</div><div><h3>Confirm connection</h3><div class="small muted">The app shows whether Shopify permissions are active and which store is connected.</div></div><span class="pill">Inside Shopify</span></div>
        <div class="ops-item"><div class="ico">2</div><div><h3>Run quick check</h3><div class="small muted">A lightweight summary can run from Shopify admin for confidence.</div></div><button class="secondary" onclick="runAnalysis()">Analyze</button></div>
        <div class="ops-item"><div class="ico">3</div><div><h3>Open full OPS workspace</h3><div class="small muted">Full product rows, forecasts, pricing, churn, ledger and team tools live on opsintelligence.org.</div></div><button onclick="openOpsDashboard()">Go to OPS Intelligence →</button></div>
      </div>
    </section>
  </div>
  <script>
    const shop = {json.dumps(shop)};
    const appToken = {json.dumps(app_token)};
    const installUrl = {json.dumps(install_url)};
    const opsLaunchUrl = {json.dumps(ops_launch_url)};
    const opsPlansUrl = {json.dumps(ops_plans_url)};

    function leaveShopifyFrame(url) {{
      try {{
        if (window.top && window.top !== window) {{
          window.top.location.href = url;
          return;
        }}
      }} catch(e) {{}}
      window.location.href = url;
    }}

    function reinstallPermissions() {{
      leaveShopifyFrame(installUrl);
    }}

    function openOpsDashboard(section) {{
      leaveShopifyFrame(section === 'plans' ? opsPlansUrl : opsLaunchUrl);
    }}

    function readApiError(data, fallback) {{
      if (!data) return fallback;
      if (typeof data.detail === 'string') return data.detail;
      if (data.detail && typeof data.detail.message === 'string') return data.detail.message;
      if (typeof data.message === 'string') return data.message;
      return fallback;
    }}

    function readFallbackUrl(data) {{
      if (!data) return '';
      return data.fallback_url || (data.detail && data.detail.fallback_url) || '';
    }}

    async function shopifySessionHeaders(extraHeaders) {{
      const headers = Object.assign({{}}, extraHeaders || {{}});
      if (window.shopify && typeof shopify.idToken === 'function') {{
        const token = await shopify.idToken();
        headers.Authorization = `Bearer ${{token}}`;
      }}
      return headers;
    }}

    async function verifyEmbeddedSession() {{
      try {{
        await fetch('/shopify/app/session', {{
          method:'POST',
          headers:await shopifySessionHeaders({{'Content-Type':'application/json'}}),
          body:JSON.stringify({{shop}})
        }});
      }} catch(e) {{}}
    }}

    async function runAnalysis(){{
      const box=document.getElementById('result');
      box.textContent='Fetching Shopify data and analyzing... This can take up to 2 minutes.';
      try{{
        const res=await fetch('/shopify/app/analyze',{{
          method:'POST',
          headers:await shopifySessionHeaders({{'Content-Type':'application/json'}}),
          body:JSON.stringify({{shop,app_token:appToken}})
        }});
        const data=await res.json();
        if(!res.ok) throw new Error(readApiError(data,'Analysis failed'));
        const rev=data.metrics.revenue||{{}};
        const inv=data.metrics.inventory||{{}};
        const counts=data.record_counts||{{}};
        const warning=data.warning ? `Note: ${{data.warning}}\\n\\n` : '';
        box.textContent =
          warning+
          `Health score: ${{data.analysis.overall_health_score || 0}}/100\\n`+
          `Revenue: €${{Number(rev.total || 0).toLocaleString()}}\\n`+
          `Orders: ${{rev.orders || 0}}\\n`+
          `Products analyzed: ${{counts.products || 0}}\\n`+
          `AOV: €${{Number(rev.aov || 0).toFixed(2)}}\\n`+
          `Critical inventory items: ${{inv.critical_count || 0}}\\n\\n`+
          `${{data.analysis.executive_summary || 'Analysis completed.'}}`;
        if (window.shopify && shopify.toast) shopify.toast.show('OPS analysis complete');
      }}catch(e){{
        box.textContent='Analysis error: '+e.message+'\\n\\nUse Reinstall permissions if Shopify access was recently changed, then run the check again.';
        if (window.shopify && shopify.toast) shopify.toast.show('OPS analysis failed', {{isError:true}});
      }}
    }}
    async function startBilling(plan){{
      const box=document.getElementById('result');
      box.textContent='Opening Shopify plan selection...';
      try{{
        const res=await fetch('/shopify/app/billing',{{
          method:'POST',
          headers:await shopifySessionHeaders({{'Content-Type':'application/json'}}),
          body:JSON.stringify({{shop,plan,app_token:appToken}})
        }});
        const data=await res.json().catch(()=>({{}}));
        if(!res.ok){{
          const fallbackUrl = readFallbackUrl(data);
          const msg = readApiError(data,'Billing failed');
          if(fallbackUrl){{
            box.textContent=msg+' Opening OPS billing fallback...';
            setTimeout(()=>leaveShopifyFrame(fallbackUrl), 700);
            return;
          }}
          throw new Error(msg);
        }}
        leaveShopifyFrame(data.confirmation_url);
      }}catch(e){{
        box.textContent='Billing error: '+e.message;
      }}
    }}
    verifyEmbeddedSession();
  </script>
</body>
</html>
""")
    response.headers["Content-Security-Policy"] = f"frame-ancestors https://{shop} https://admin.shopify.com;"
    return response


@app.get("/shopify/app/launch")
async def shopify_app_launch(shop: str, app_token: str, section: str = ""):
    shop_domain = normalize_shop_domain(shop)
    payload = verify_shopify_embedded_token(app_token, shop_domain)
    db = get_supabase()
    user_result = db.table("users").select("plan").eq("email", payload["sub"]).execute()
    plan_key = user_result.data[0].get("plan", "free") if user_result.data else "free"
    ops_token = create_token(payload["sub"], plan_key)
    launch_params = {
        "shopify_connected": "1",
        "shop": shop_domain,
        "token": ops_token,
    }
    if section:
        launch_params["section"] = section
    return RedirectResponse(
        f"{FRONTEND_PUBLIC_URL}/app.html#{urlencode(launch_params)}"
    )


@app.post("/shopify/app/session")
async def shopify_embedded_session(
    req: ShopifyConnectStartRequest,
    shopify_session: dict = Depends(verify_shopify_session_token),
):
    shop = normalize_shop_domain(req.shop)
    if shopify_session.get("shop") != shop:
        raise HTTPException(status_code=401, detail="Shopify session token does not match this store.")
    return {
        "success": True,
        "shop": shop,
        "session_user_id": str(shopify_session.get("sub", "")),
    }


@app.post("/shopify/app/analyze")
async def shopify_embedded_analyze(
    req: ShopifyEmbeddedAnalyzeRequest,
    shopify_session: dict = Depends(verify_shopify_session_token),
):
    shop = normalize_shop_domain(req.shop)
    if shopify_session.get("shop") != shop:
        raise HTTPException(status_code=401, detail="Shopify session token does not match this store.")
    payload = verify_shopify_embedded_token(req.app_token, shop)
    connected = get_connected_shop(payload["sub"], shop)
    if not connected:
        raise HTTPException(status_code=404, detail="Connected Shopify store not found.")
    db = get_supabase()
    user_result = db.table("users").select("plan").eq("email", payload["sub"]).execute()
    plan_key = user_result.data[0].get("plan", "free") if user_result.data else "free"
    plan = PLANS.get(plan_key, PLANS["free"])
    usage_result = db.table("users").select("analyses_this_month").eq("email", payload["sub"]).execute()
    used = usage_result.data[0].get("analyses_this_month", 0) if usage_result.data else 0
    limit = analysis_limit_for_plan(plan)
    usage_warning = ""
    count_usage = used < limit
    if not count_usage:
        usage_warning = (
            f"Monthly quick-check limit reached ({used}/{limit}) for the {plan_key} plan. "
            "Showing a review-safe quick check without incrementing usage."
        )

    try:
        report = run_shopify_live_pipeline(ShopifyConfig(
            shop_domain=shop,
            access_token=connected["access_token"],
            api_version=SHOPIFY_API_VERSION,
            use_mock=False,
            mock_order_count=200,
        ))
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        if status_code in (401, 403):
            raise HTTPException(
                status_code=status_code,
                detail="Shopify rejected the stored access token. Reinstall OPS permissions from this Shopify admin, then run the check again.",
            )
        raise HTTPException(status_code=502, detail=f"Shopify API returned HTTP {status_code}.")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Shopify API timed out. Please retry.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Shopify connection error: {str(e)}")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    ai_cfg = AIConfig(api_key=openai_key, use_mock_ai=not (openai_key and plan["ai"]), language="en")
    ai_result = AIAnalysisEngine(ai_cfg).analyze(report)
    if not ai_result.get("success") or "analysis" not in ai_result:
        ai_result = AIAnalysisEngine(AIConfig(use_mock_ai=True, language="en")).analyze(report)

    extended = run_extended_analysis(report)
    usage_update = {"last_analysis": datetime.now().isoformat()}
    if count_usage:
        usage_update["analyses_this_month"] = used + 1
    db.table("users").update(usage_update).eq("email", payload["sub"]).execute()
    payload = {
        "success": True,
        **make_analysis_context(
            report,
            shop,
            "shopify",
            ai_result.get("model", "ops-rules-real-data"),
        ),
        "analysis": ai_result.get("analysis", {}),
        "generated_at": ai_result.get("generated_at", datetime.now().isoformat()),
        "user_plan": plan_key,
        "extended": extended,
        "metrics": build_metrics_payload(report),
        "series": {
            "daily_revenue": build_daily_revenue_points(report),
        },
    }
    sync_warnings = ((report.get("sync_status") or {}).get("warnings") or [])
    if sync_warnings:
        payload["sync_status"] = report.get("sync_status")
        payload["warning"] = " ".join(w.get("message", "") for w in sync_warnings if isinstance(w, dict)).strip()
    if usage_warning:
        payload["warning"] = f"{payload.get('warning', '')}\n{usage_warning}".strip()
    return make_json_safe(payload)


@app.post("/shopify/app/billing")
async def shopify_embedded_billing(
    req: ShopifyBillingRequest,
    shopify_session: dict = Depends(verify_shopify_session_token),
):
    shop = normalize_shop_domain(req.shop)
    if shopify_session.get("shop") != shop:
        raise HTTPException(status_code=401, detail="Shopify session token does not match this store.")
    payload = verify_shopify_embedded_token(req.app_token, shop)
    connected = get_connected_shop(payload["sub"], shop)
    if not connected:
        raise HTTPException(status_code=404, detail="Connected Shopify store not found.")

    if req.plan not in ("starter", "pro"):
        raise HTTPException(status_code=400, detail="Only Starter and Pro can be purchased through Shopify Billing.")

    if SHOPIFY_BILLING_MODE in ("shopify_app_pricing", "app_pricing", "managed_pricing"):
        try:
            pricing_url = build_shopify_app_pricing_url(shop)
        except HTTPException as e:
            return shopify_billing_fallback_response(shop, req.app_token, str(e.detail))
        mark_shopify_billing_intent(payload["sub"], shop, req.plan)
        return {
            "success": True,
            "confirmation_url": pricing_url,
            "billing_mode": "shopify_app_pricing",
            "plan": req.plan,
        }

    if SHOPIFY_BILLING_MODE != "billing_api" or not SHOPIFY_BILLING_ENABLED:
        return shopify_billing_fallback_response(
            shop,
            req.app_token,
            "Shopify Billing is not active for this app yet. OPS will open its own billing page until the app is Partner-owned and Shopify pricing is configured.",
        )

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
    try:
        response = requests.post(
            f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json",
            headers={"X-Shopify-Access-Token": connected["access_token"], "Content-Type": "application/json"},
            json={"query": mutation, "variables": variables},
            timeout=30,
        )
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        raise HTTPException(status_code=502, detail=f"Shopify Billing API returned HTTP {status_code}.")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Shopify Billing timed out. Please retry.")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Shopify Billing connection error: {str(e)}")

    payload = response.json()
    create_result = payload.get("data", {}).get("appSubscriptionCreate", {})
    errors = create_result.get("userErrors") or payload.get("errors") or []
    if errors:
        first_error = errors[0].get("message") if isinstance(errors[0], dict) else str(errors[0])
        if first_error and ("owned by a Shop" in first_error or "Shopify partners area" in first_error):
            return shopify_billing_fallback_response(
                shop,
                req.app_token,
                "Shopify Billing rejected this app because it is still shop-owned. OPS is opening its own billing page while the app is moved to the Shopify Partner area.",
            )
        raise HTTPException(status_code=400, detail=first_error or "Shopify Billing could not be started.")

    confirmation_url = create_result.get("confirmationUrl")
    if not confirmation_url:
        raise HTTPException(status_code=502, detail="Shopify did not return a billing confirmation URL.")

    return {"success": True, "confirmation_url": confirmation_url, "test": SHOPIFY_BILLING_TEST, "billing_mode": "billing_api"}


@app.get("/shopify/billing/return")
async def shopify_billing_return(request: Request, shop: str = "", plan: str = "", plan_handle: str = ""):
    params = dict(request.query_params)
    shop_value = shop or params.get("shop_domain") or params.get("shop") or ""
    if not shop_value:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html#shopify_error=missing_shop")

    shop_domain = normalize_shop_domain(shop_value)
    connected = find_shopify_store_by_domain(shop_domain)
    selected_plan = plan if plan in ("starter", "pro") else plan_from_shopify_handle(plan_handle or params.get("plan_handle", ""))
    if not selected_plan and connected:
        selected_plan = connected["store"].get("billing_pending_plan", "")
    if connected and selected_plan in ("starter", "pro"):
        mark_shopify_billing(connected["user"]["email"], shop_domain, selected_plan)
    return RedirectResponse(f"{BACKEND_PUBLIC_URL}/shopify/app?shop={quote(shop_domain)}&billing_return=1")


@app.post("/shopify/connect/start")
async def start_shopify_connect(req: ShopifyConnectStartRequest, payload: dict = Depends(verify_token)):
    if not SHOPIFY_API_KEY or not SHOPIFY_API_SECRET:
        raise HTTPException(
            status_code=500,
            detail="Shopify OAuth configuration is missing. Set SHOPIFY_API_KEY and SHOPIFY_API_SECRET in Railway.",
        )

    shop = normalize_shop_domain(req.shop)
    db = get_supabase()
    user_result = db.table("users").select("plan,stores").eq("email", payload["sub"]).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found.")
    stores = user_result.data[0].get("stores") or []
    if not isinstance(stores, list):
        stores = []
    ensure_store_slot_available(stores, user_result.data[0].get("plan", "free"), "shopify", shop)

    state = create_shopify_state(payload["sub"], shop)
    redirect_uri = f"{BACKEND_PUBLIC_URL}/shopify/callback"
    params = {
        "client_id": SHOPIFY_API_KEY,
        "scope": SHOPIFY_SCOPES,
        "redirect_uri": redirect_uri,
        "state": state,
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
            data={
                "client_id": SHOPIFY_API_KEY,
                "client_secret": SHOPIFY_API_SECRET,
                "code": code,
            },
            headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
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
        try:
            ensure_shopify_user(
                shop,
                access_token,
                token_data.get("scope", SHOPIFY_SCOPES),
            )
        except HTTPException as e:
            return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error={quote(str(e.detail))}")
        return RedirectResponse(f"{BACKEND_PUBLIC_URL}/shopify/app?shop={quote(shop)}&shopify_connected=1")

    user_email = state_payload["sub"]
    try:
        save_shopify_store(
            user_email,
            shop,
            access_token,
            token_data.get("scope", SHOPIFY_SCOPES),
        )
    except HTTPException as e:
        return RedirectResponse(f"{FRONTEND_PUBLIC_URL}/app.html?shopify_error={quote(str(e.detail))}")

    db = get_supabase()
    user_result = db.table("users").select("plan").eq("email", user_email).execute()
    billing_state = get_user_billing_state(user_email)
    plan_key = billing_state.get("plan", user_result.data[0].get("plan", "free") if user_result.data else "free")
    ops_token = create_token(user_email, plan_key)
    return RedirectResponse(
        f"{FRONTEND_PUBLIC_URL}/app.html#shopify_connected=1&shop={quote(shop)}&token={quote(ops_token)}"
    )


@app.get("/shopify/status")
async def shopify_status(payload: dict = Depends(verify_token)):
    db = get_supabase()
    result = db.table("users").select("plan,stores").eq("email", payload["sub"]).execute()
    user_row = result.data[0] if result.data else {}
    stores = user_row.get("stores", []) if user_row else []
    if not isinstance(stores, list):
        stores = []
    billing_state = get_user_billing_state(payload["sub"])
    plan_key = billing_state.get("plan", user_row.get("plan", payload.get("plan", "free")) if user_row else payload.get("plan", "free"))
    plan = PLANS.get(plan_key, PLANS["free"])
    shopify_stores = [
        public_store(store)
        for store in stores
        if isinstance(store, dict) and store.get("platform") == "shopify"
    ]
    connected_count = connected_store_count(stores, "shopify")
    max_stores = int(plan.get("max_stores", 1))
    return {
        "success": True,
        "stores": shopify_stores,
        "plan": plan_key,
        "max_stores": max_stores,
        "connected_count": connected_count,
        "can_add_store": connected_count < max_stores,
        "billing": billing_state,
    }


@app.post("/shopify/webhooks/app-uninstalled")
async def shopify_app_uninstalled(request: Request):
    raw_body = await request.body()
    if not verify_shopify_webhook(raw_body, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature.")
    shop = normalize_shop_domain(request.headers.get("X-Shopify-Shop-Domain", ""))
    disconnect_shopify_store(shop)
    return {"success": True}


@app.post("/shopify/webhooks/app-subscriptions-update")
async def shopify_app_subscription_update(request: Request):
    raw_body = await request.body()
    if not verify_shopify_webhook(raw_body, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature.")

    shop = normalize_shop_domain(request.headers.get("X-Shopify-Shop-Domain", ""))
    payload = parse_shopify_webhook_json(raw_body)
    subscription = payload.get("app_subscription") if isinstance(payload.get("app_subscription"), dict) else payload
    connected = find_shopify_store_by_domain(shop)
    if not connected:
        return {"success": True, "ignored": "shop_not_connected"}

    store = connected["store"]
    status_value = str(subscription.get("status") or "").strip().lower()
    plan = plan_from_shopify_handle(
        subscription.get("name")
        or subscription.get("plan_handle")
        or store.get("billing_pending_plan", "")
    )
    if status_value in ("active", "accepted") and plan in ("starter", "pro"):
        mark_shopify_billing(connected["user"]["email"], shop, plan, "active")
    elif status_value in ("cancelled", "canceled", "declined", "expired", "frozen", "inactive"):
        clear_shopify_billing(connected["user"]["email"], shop, status_value or "cancelled")

    return {"success": True}


@app.post("/shopify/webhooks/privacy")
async def shopify_privacy_webhook(request: Request):
    raw_body = await request.body()
    if not verify_shopify_webhook(raw_body, request.headers.get("X-Shopify-Hmac-Sha256", "")):
        raise HTTPException(status_code=401, detail="Invalid Shopify webhook signature.")
    payload = parse_shopify_webhook_json(raw_body)
    topic = (request.headers.get("X-Shopify-Topic") or "").strip().lower()

    if topic == "customers/data_request":
        return {"success": True, "request": customer_data_response(payload)}

    if topic == "customers/redact":
        return {"success": True, "request": redact_customer_data(payload)}

    if topic == "shop/redact":
        shop = shop_domain_from_privacy_payload(payload, request)
        changed_users = redact_shopify_store_data(shop)
        return {"success": True, "shop": shop, "redacted_users": changed_users}

    return {"success": True, "topic": topic or "unknown"}


# ─────────────────────────────────────────────
# ANALİZ ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/run")
async def run_analysis(req: AnalysisRequest, payload: dict = Depends(verify_token)):
    db = get_supabase()
    email = payload["sub"]

    user_data = db.table("users").select("plan,analyses_this_month,stores").eq("email", email).execute()
    if not user_data.data:
        raise HTTPException(status_code=404, detail="User not found.")

    # JWT plan bilgisi eski kalabilir; kullanım ve limit için her zaman DB'deki güncel planı esas al.
    plan_key = user_data.data[0].get("plan") or payload.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])
    used = user_data.data[0].get("analyses_this_month") or 0
    limit = analysis_limit_for_plan(plan)

    if not req.use_mock and used >= limit:
        raise HTTPException(status_code=429, detail=f"Monthly analysis limit reached ({used}/{limit}). Current plan: {plan_key}.")

    platform = (req.platform or "shopify").lower()
    connected_store = None
    if platform == "shopify" and not req.use_mock and not req.shopify_token:
        connected_store = get_connected_shop(email, req.connected_shop or req.shopify_domain)
        if not connected_store:
            raise HTTPException(
                status_code=400,
                detail="No connected Shopify store was found for this account. Install OPS through Shopify first.",
            )

    shop_domain = (connected_store or {}).get("domain") or req.shopify_domain or ""
    shop_token = (connected_store or {}).get("access_token") or req.shopify_token or ""
    if platform == "shopify" and not req.use_mock:
        if not shop_domain:
            raise HTTPException(status_code=400, detail="A Shopify store domain is required for live analysis.")
        shop_domain = normalize_shop_domain(shop_domain)
        if req.shopify_token and not connected_store:
            stores = user_data.data[0].get("stores") or []
            if not isinstance(stores, list):
                stores = []
            ensure_store_slot_available(stores, plan_key, "shopify", shop_domain)
        if not shop_token:
            raise HTTPException(status_code=400, detail="A Shopify access token is required for live analysis.")
    elif platform == "woocommerce":
        if not req.use_mock:
            if not shop_domain:
                raise HTTPException(status_code=400, detail="A WooCommerce store URL is required for live analysis.")
            if "::" not in (shop_token or ""):
                raise HTTPException(status_code=400, detail="WooCommerce Consumer Key and Secret are required.")
            shop_domain = normalize_store_url(shop_domain)

    # Veri çek
    try:
        if platform == "woocommerce":
            consumer_key, consumer_secret = shop_token.split("::", 1)
            report = run_woocommerce_pipeline(WooCommerceConfig(
                store_url=shop_domain,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                use_mock=req.use_mock,
            ))
        else:
            shopify_config = ShopifyConfig(
                shop_domain=shop_domain,
                access_token=shop_token,
                api_version=SHOPIFY_API_VERSION,
                use_mock=req.use_mock,
                mock_order_count=200,
            )
            report = run_pipeline(shopify_config) if req.use_mock else run_shopify_live_pipeline(shopify_config)
    except requests.exceptions.HTTPError as e:
        status_code = e.response.status_code if e.response is not None else 502
        if platform == "woocommerce":
            if status_code in (401, 403):
                raise HTTPException(
                    status_code=status_code,
                    detail="WooCommerce credentials were rejected. Verify the Consumer Key and Consumer Secret.",
                )
            raise HTTPException(status_code=502, detail=f"WooCommerce API returned HTTP {status_code}.")
        if status_code in (401, 403):
            raise HTTPException(
                status_code=status_code,
                detail=(
                    "Shopify credentials were rejected. Confirm the token is valid and the "
                    "read_orders, read_products, read_inventory scopes are granted."
                ),
            )
        raise HTTPException(status_code=502, detail=f"Shopify API returned HTTP {status_code}.")
    except requests.exceptions.Timeout:
        if platform == "woocommerce":
            raise HTTPException(status_code=504, detail="WooCommerce API timed out. Try again shortly.")
        raise HTTPException(status_code=504, detail="Shopify API timed out. Try again shortly.")
    except requests.exceptions.RequestException as e:
        if platform == "woocommerce":
            raise HTTPException(status_code=502, detail=f"WooCommerce connection error: {str(e)}")
        raise HTTPException(status_code=502, detail=f"Shopify connection error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis could not be started: {str(e)}")

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
    should_run_meta = plan["meta"] and (
        (req.meta_token and req.meta_account) or (req.use_mock and req.use_mock_meta)
    )
    if should_run_meta:
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

    extended = run_extended_analysis(report)

    if not req.use_mock:
        db.table("users").update({
            "analyses_this_month": used + 1,
            "last_analysis": datetime.now().isoformat(),
        }).eq("email", email).execute()

    # Analiz sonucu
    result_data = make_json_safe({
        "analysis": ai_result.get("analysis", {}),
        **make_analysis_context(
            report,
            shop_domain or "Demo Store",
            "demo" if req.use_mock else platform,
            ai_result.get("model", "ops-rules-real-data"),
        ),
        "extended": extended,
        "metrics": build_metrics_payload(report),
        "series": {
            "daily_revenue": build_daily_revenue_points(report),
        },
    })

    # Mail gönder
    user_info = db.table("users").select("name").eq("email", email).execute()
    user_name = user_info.data[0]["name"] if user_info.data else email
    try:
        mail_sent = await send_analysis_email(email, user_name, result_data)
        print(f"📧 Analysis email {'sent' if mail_sent else 'not sent'}: {email}")
    except Exception as e:
        print(f"📧 Analysis email error: {e}")

    return make_json_safe({
        "success": True,
        **make_analysis_context(
            report,
            shop_domain or "Demo Store",
            "demo" if req.use_mock else platform,
            ai_result.get("model", "ops-rules-real-data"),
        ),
        "analysis": ai_result.get("analysis", {}),
        "generated_at": ai_result.get("generated_at", datetime.now().isoformat()),
        "metrics": build_metrics_payload(report),
        "meta": meta_data,
        "extended": extended,
        "series": {
            "daily_revenue": build_daily_revenue_points(report),
        },
        "sync_status": report.get("sync_status", {}),
        "user_plan": plan_key,
    })


@app.post("/report/pdf")
async def create_pdf_report(req: PDFReportRequest, payload: dict = Depends(verify_token)):
    result = make_json_safe(req.result or {})
    shop_name = (req.shop_name or result.get("shop_name") or "OPS Store").strip()
    meta_result = req.meta if req.meta is not None else result.get("meta")

    if not result.get("analysis"):
        raise HTTPException(status_code=400, detail="Run an analysis before downloading a PDF report.")

    try:
        pdf_bytes = generate_pdf_report(result, meta_result, shop_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF report could not be generated: {str(e)}")

    safe_shop = re.sub(r"[^A-Za-z0-9._-]+", "_", shop_name).strip("_") or "OPS_Report"
    filename = f"OPS_Report_{safe_shop}_{datetime.utcnow().strftime('%Y-%m-%d')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# ─────────────────────────────────────────────
# ASK OPS — AI OPERATOR ENDPOINT
# ─────────────────────────────────────────────

def compact_ai_context(ctx: dict) -> dict:
    """Keep the model context focused on operating signals instead of raw store dumps."""
    ctx = ctx or {}
    analysis = ctx.get("analysis") or {}
    metrics = ctx.get("metrics") or {}
    extended = ctx.get("extended") or {}
    meta = ctx.get("meta") or {}
    return make_json_safe({
        "shop_name": ctx.get("shop_name"),
        "data_source": ctx.get("data_source"),
        "record_counts": ctx.get("record_counts"),
        "analysis": {
            "overall_health_score": analysis.get("overall_health_score"),
            "executive_summary": analysis.get("executive_summary"),
            "findings": (analysis.get("findings") or [])[:6],
            "quick_wins": (analysis.get("quick_wins") or [])[:8],
            "swot": analysis.get("swot") or {},
        },
        "metrics": {
            "revenue": metrics.get("revenue") or {},
            "fulfillment": metrics.get("fulfillment") or {},
            "inventory": {
                **(metrics.get("inventory") or {}),
                "products": ((metrics.get("inventory") or {}).get("products") or [])[:12],
            },
        },
        "extended": {
            "churn": extended.get("churn") or {},
            "price_elasticity": extended.get("price_elasticity") or {},
            "forecast": {
                **(extended.get("forecast") or {}),
                "forecast_30_days": ((extended.get("forecast") or {}).get("forecast_30_days") or [])[:10],
            },
            "benchmark": extended.get("benchmark") or {},
        },
        "meta": {
            "cross_alarms": (meta.get("cross_alarms") or [])[:6],
            "campaign_summary": (meta.get("campaign_summary") or [])[:8],
        } if isinstance(meta, dict) else {},
    })


def fallback_ops_answer(question: str, ctx: dict, mode: str, language: str = "en") -> dict:
    metrics = (ctx or {}).get("metrics") or {}
    analysis = (ctx or {}).get("analysis") or {}
    revenue = metrics.get("revenue") or {}
    fulfillment = metrics.get("fulfillment") or {}
    inventory = metrics.get("inventory") or {}
    products = inventory.get("products") or []
    findings = analysis.get("findings") or []
    quick_wins = analysis.get("quick_wins") or []
    cancel_rate = float(revenue.get("cancel_rate") or revenue.get("cancellation_rate") or 0)
    refund_rate = float(revenue.get("refund_rate") or 0)
    ft_mean = float(fulfillment.get("mean") or 0)
    critical_products = [
        p for p in products
        if float(p.get("current_stock") or p.get("inventory") or 0) <= 10
    ]
    total = float(revenue.get("total") or revenue.get("total_revenue") or 0)
    leakage = round(
        max(
            1200,
            (total * 0.08 if cancel_rate > 2.5 else 0)
            + (total * 0.05 if refund_rate > 5 else 0)
            + len(critical_products) * 650
            + (900 if ft_mean > 24 else 0),
        )
    )
    q = (question or "").lower()
    lang = "tr" if (language or "").lower().startswith("tr") else "en"
    if lang == "tr":
        if "iade" in q or "refund" in q or "return" in q:
            answer = (
                f"OPS iade baskısını %{refund_rate:.1f} seviyesinde görüyor. "
                f"Muhtemel operasyon nedeni {ft_mean:.1f} saatlik fulfillment gecikmesi ve SKU bazlı ürün riski. "
                f"Bu baskı sürerse yaklaşık €{leakage:,.0f} aylık gelir risk altında kalabilir."
            )
        elif "stok" in q or "stock" in q or "sku" in q or "envanter" in q:
            names = ", ".join((p.get("title") or p.get("name") or "SKU") for p in critical_products[:3]) or "kritik SKU yok"
            answer = (
                f"OPS {len(critical_products)} üründe stok riski buldu. "
                f"Önce {names} ürünlerine bak. Kampanyalar trafik göndermeye devam ederse kaçan talep ve boşa giden reklam harcaması oluşabilir."
            )
        elif "aov" in q or "bundle" in q or "sepet" in q:
            answer = (
                f"AOV yaklaşık €{float(revenue.get('aov') or 0):.0f}. "
                "OPS bunu yüksek marjlı ana ürünleri yavaş dönen stoklarla bundle yaparak ve düşük elastikiyetli SKU'larda küçük fiyat artışı test ederek korurdu."
            )
        else:
            top = findings[0] if findings else {}
            action = quick_wins[0] if quick_wins else "En yüksek riskli bulguya bir sorumlu ata ve sonraki veri senkronundan sonra tekrar kontrol et."
            answer = (
                f"OPS şununla başlardı: {top.get('title', 'en yüksek riskli operasyon sinyali')}. "
                f"Neden önemli: {top.get('description') or top.get('root_cause') or 'mağaza aktivitesini gereksiz marj kaybına çevirebilir.'} "
                f"Sonraki aksiyon: {action}"
            )
    elif "refund" in q or "return" in q:
        answer = (
            f"OPS sees refund pressure at {refund_rate:.1f}%. "
            f"The likely operating driver is fulfillment drag at {ft_mean:.1f}h plus SKU-level product risk. "
            f"If sustained, this can keep roughly €{leakage:,} of monthly revenue under pressure."
        )
    elif "stock" in q or "sku" in q or "inventory" in q:
        names = ", ".join((p.get("title") or p.get("name") or "SKU") for p in critical_products[:3]) or "no critical SKU"
        answer = (
            f"OPS found {len(critical_products)} products at stock risk. "
            f"Start with {names}. The consequence is missed demand and wasted acquisition spend if campaigns keep driving traffic."
        )
    elif "aov" in q or "bundle" in q:
        answer = (
            f"AOV is €{float(revenue.get('aov') or 0):.0f}. "
            "OPS would protect this by bundling high-margin hero products with slower-moving inventory, then testing a small price lift on low-elasticity SKUs."
        )
    else:
        top = findings[0] if findings else {}
        action = quick_wins[0] if quick_wins else "Assign an owner to the highest-risk finding and review again after the next data sync."
        answer = (
            f"OPS would start with: {top.get('title', 'the highest-risk operating signal')}. "
            f"Why it matters: {top.get('description') or top.get('root_cause') or 'it can turn store activity into avoidable margin loss.'} "
            f"Next action: {action}"
        )
    return {
        "success": True,
        "mode": mode,
        "model": "ops-rule-fallback",
        "answer": answer,
        "confidence": ("Yüksek" if (ctx or {}).get("record_counts", {}).get("orders", 0) >= 100 else "Orta") if lang == "tr" else ("High" if (ctx or {}).get("record_counts", {}).get("orders", 0) >= 100 else "Medium"),
        "based_on": {
            "orders": (ctx or {}).get("record_counts", {}).get("orders", 0),
            "products": (ctx or {}).get("record_counts", {}).get("products", 0),
        },
        "suggested_actions": quick_wins[:3],
    }


@app.post("/ai/ask")
async def ask_ops(req: AIAskRequest, payload: dict = Depends(verify_token)):
    question = (req.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is required.")

    context = compact_ai_context(req.context)
    language = "tr" if (req.language or "").lower().startswith("tr") else "en"
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return fallback_ops_answer(question, context, req.mode, language)

    system = (
        "You are OPS, an AI operations analyst for Shopify founders. "
        "Answer like an opinionated AI COO, not a generic dashboard assistant. "
        "Use the provided context only. Focus on profit leaks, operational risk, cause, consequence, next action, and confidence. "
        "Be concise, evidence-based, and practical. Do not invent exact data not present in context. "
        f"Answer in {'Turkish' if language == 'tr' else 'English'}. "
        "Return valid JSON only."
    )
    user_prompt = {
        "question": question,
        "mode": req.mode,
        "language": language,
        "context": context,
        "response_contract": {
            "answer": "3-6 sentence answer with cause, consequence, and next action",
            "confidence": "Low, Medium, or High; use Turkish equivalents when language is tr",
            "based_on": "short evidence summary",
            "suggested_actions": "array of up to 3 action strings",
        },
    }
    try:
        from openai import OpenAI
        client = OpenAI(api_key=openai_key, timeout=20.0, max_retries=0)
        response = client.chat.completions.create(
            model=os.environ.get("OPENAI_ASK_MODEL", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(user_prompt, ensure_ascii=False)},
            ],
            temperature=0.25,
            response_format={"type": "json_object"},
            max_tokens=650,
        )
        raw = response.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        return make_json_safe({
            "success": True,
            "mode": req.mode,
            "model": response.model,
            "answer": parsed.get("answer") or "",
            "confidence": parsed.get("confidence") or "Medium",
            "based_on": parsed.get("based_on") or context.get("record_counts") or {},
            "suggested_actions": parsed.get("suggested_actions") or [],
        })
    except Exception as exc:
        logger.warning("Ask OPS OpenAI fallback: %s", exc.__class__.__name__)
        return fallback_ops_answer(question, context, req.mode, language)


# ─────────────────────────────────────────────
# CSV / EXCEL UPLOAD ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/upload")
async def upload_analysis(
    file: UploadFile = File(...),
    platform: str = Form("generic"),
    language: str = Form("en"),
    payload: dict = Depends(verify_token),
):
    filename = file.filename or "upload"
    allowed_ext = (".csv", ".xlsx", ".xls")
    if not filename.lower().endswith(allowed_ext):
        raise HTTPException(status_code=400, detail="Upload a CSV or Excel file.")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    db = get_supabase()
    user_result = db.table("users").select("plan,analyses_this_month").eq("email", payload["sub"]).execute()
    if not user_result.data:
        raise HTTPException(status_code=404, detail="User not found.")
    plan_key = user_result.data[0].get("plan", payload.get("plan", "free"))
    plan = PLANS.get(plan_key, PLANS["free"])
    used = user_result.data[0].get("analyses_this_month") or 0
    limit = analysis_limit_for_plan(plan)
    if used >= limit:
        raise HTTPException(status_code=429, detail=f"Monthly analysis limit reached ({used}/{limit}). Current plan: {plan_key}.")

    try:
        df = read_upload_dataframe(filename, content)
        report = build_report_from_upload(df, platform.lower().strip() or "generic", filename)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse upload: {str(e)}")

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if openai_key and plan["ai"]:
        ai_cfg = AIConfig(api_key=openai_key, use_mock_ai=False, language=language)
    else:
        ai_cfg = AIConfig(use_mock_ai=True, language=language)

    engine = AIAnalysisEngine(ai_cfg)
    ai_result = engine.analyze(report)
    if not ai_result.get("success") or "analysis" not in ai_result:
        ai_result = AIAnalysisEngine(AIConfig(use_mock_ai=True, language=language)).analyze(report)

    extended = run_extended_analysis(report)
    db.table("users").update({
        "analyses_this_month": used + 1,
        "last_analysis": datetime.now().isoformat(),
    }).eq("email", payload["sub"]).execute()

    result_data = make_json_safe({
        "analysis": ai_result.get("analysis", {}),
        **make_analysis_context(
            report,
            f"{platform.title()} Upload",
            platform.lower().strip() or "upload",
            ai_result.get("model", "ops-rules-upload-data"),
        ),
        "extended": extended,
        "metrics": build_metrics_payload(report),
        "series": {
            "daily_revenue": build_daily_revenue_points(report),
        },
    })
    result_data["user_plan"] = plan_key
    result_data["upload_filename"] = filename
    return result_data


# ─────────────────────────────────────────────
# PDF ENDPOINTİ
# ─────────────────────────────────────────────

@app.post("/analysis/pdf")
async def get_pdf(req: AnalysisRequest, payload: dict = Depends(verify_token)):
    from fastapi.responses import Response
    db = get_supabase()
    user_result = db.table("users").select("plan").eq("email", payload["sub"]).execute()
    plan_key = user_result.data[0].get("plan", payload.get("plan", "free")) if user_result.data else payload.get("plan", "free")
    plan = PLANS.get(plan_key, PLANS["free"])

    if not plan["pdf"]:
        raise HTTPException(status_code=403, detail="PDF export requires Starter or Pro.")

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

    shop_label = analysis_response.get("shop_name") or (
        "Demo Store" if req.use_mock else
        (req.shopify_domain or req.connected_shop or ("WooCommerce Store" if (req.platform or "").lower() == "woocommerce" else "Connected Store"))
    )
    pdf_bytes = generate_pdf_report(mock_result, None, shop_label)

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


def stripe_price_ids() -> dict:
    return {
        "starter": os.environ.get("STRIPE_PRICE_STARTER", "price_1TRf3JG1DLQ2LxkRn0eLrytf"),
        "pro": os.environ.get("STRIPE_PRICE_PRO", "price_1TRf3aG1DLQ2LxkRqDhmI9jg"),
    }


def stripe_plan_from_subscription(subscription: dict) -> str:
    items = ((subscription or {}).get("items") or {}).get("data") or []
    plan_by_price = {price_id: plan for plan, price_id in stripe_price_ids().items() if price_id}
    for item in items:
        price_id = ((item.get("price") or {}).get("id") or "")
        if price_id in plan_by_price:
            return plan_by_price[price_id]
    metadata_plan = ((subscription or {}).get("metadata") or {}).get("plan", "")
    return metadata_plan if metadata_plan in ("starter", "pro") else ""


def stripe_customer_email(stripe_module, customer_id: str) -> str:
    if not customer_id:
        return ""
    try:
        customer = stripe_module.Customer.retrieve(customer_id)
        return (customer.get("email") or "").lower().strip()
    except Exception as exc:
        print(f"Stripe customer email lookup warning: {exc.__class__.__name__}")
        return ""


def has_active_stripe_subscription(stripe_module, email: str) -> bool:
    try:
        customers = stripe_module.Customer.list(email=email, limit=1)
        if not customers.data:
            return False
        for status_name in ("active", "trialing"):
            subscriptions = stripe_module.Subscription.list(
                customer=customers.data[0].id,
                status=status_name,
                limit=1,
            )
            if subscriptions.data:
                return True
    except Exception as exc:
        print(f"Stripe duplicate subscription check warning: {exc.__class__.__name__}")
    return False


@app.get("/billing/status")
async def billing_status(payload: dict = Depends(verify_token)):
    state = get_user_billing_state(payload["sub"])
    return {"success": True, **state}


@app.post("/payments/create-checkout")
async def create_checkout(req: CheckoutRequest, payload: dict = Depends(verify_token)):
    billing = get_user_billing_state(payload["sub"])
    if billing.get("has_shopify_store"):
        raise HTTPException(
            status_code=409,
            detail="This account is connected to Shopify. Manage the plan through Shopify to avoid duplicate billing.",
            headers={"X-OPS-Billing-Provider": "shopify"},
        )

    import stripe
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not stripe.api_key:
        raise HTTPException(status_code=500, detail="Stripe is not configured.")

    if has_active_stripe_subscription(stripe, payload["sub"]):
        raise HTTPException(
            status_code=409,
            detail="This account already has an active OPS web subscription. Manage or cancel the current subscription before starting a new checkout.",
        )

    price_id = stripe_price_ids().get(req.plan)
    if not price_id:
        raise HTTPException(status_code=400, detail="Invalid plan.")

    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=req.success_url,
            cancel_url=req.cancel_url,
            customer_email=payload["sub"],
            metadata={"user_email": payload["sub"], "plan": req.plan},
            subscription_data={"metadata": {"user_email": payload["sub"], "plan": req.plan}},
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
            billing = get_user_billing_state(email)
            if billing.get("shopify_billing_active"):
                print(f"Stripe checkout ignored for Shopify-billed user: {email}")
                return {"status": "ok", "ignored": "shopify_billing_active"}
            db = get_supabase()
            db.table("users").update({"plan": plan}).eq("email", email).execute()
            print(f"✅ Plan updated: {email} -> {plan}")

    if event["type"] in ("customer.subscription.updated", "customer.subscription.deleted"):
        subscription = event["data"]["object"]
        email = (
            (subscription.get("metadata") or {}).get("user_email")
            or stripe_customer_email(stripe, subscription.get("customer", ""))
        )
        if email:
            billing = get_user_billing_state(email)
            if billing.get("shopify_billing_active"):
                print(f"Stripe subscription event ignored for Shopify-billed user: {email}")
                return {"status": "ok", "ignored": "shopify_billing_active"}
            status_value = str(subscription.get("status") or "").lower()
            next_plan = stripe_plan_from_subscription(subscription)
            if event["type"] == "customer.subscription.deleted" or status_value in ("canceled", "cancelled", "incomplete_expired", "unpaid"):
                next_plan = "free"
            elif status_value not in ("active", "trialing"):
                next_plan = "free"
            if next_plan in PLANS:
                db = get_supabase()
                db.table("users").update({"plan": next_plan}).eq("email", email).execute()
                print(f"✅ Stripe subscription synced: {email} -> {next_plan}")

    return {"status": "ok"}

async def cancel_subscription_for_user(payload: dict) -> dict:
    email = payload["sub"]
    billing = get_user_billing_state(email)
    if billing.get("shopify_billing_active"):
        return {
            "success": False,
            "plan": billing.get("plan", "free"),
            "billing_provider": "shopify",
            "shopify_pricing_url": billing.get("shopify_pricing_url", ""),
            "message": "This subscription is managed in Shopify. Open Shopify billing to change or cancel the plan.",
        }

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
        "message": "Subscription canceled. Plan updated to Free.",
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
        raise HTTPException(status_code=400, detail="Invalid plan.")
    if plan != "free":
        raise HTTPException(
            status_code=402,
            detail="Paid plans must be activated through Shopify Billing or OPS checkout.",
        )
    billing = get_user_billing_state(payload["sub"])
    if billing.get("shopify_billing_active") and plan != billing.get("plan"):
        raise HTTPException(
            status_code=409,
            detail="This plan is managed through Shopify. Change or cancel it from Shopify billing.",
        )

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
