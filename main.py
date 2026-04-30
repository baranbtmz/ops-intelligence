"""
OPS Intelligence — FastAPI Backend
Railway'de çalışır, Netlify frontend'ine API sağlar.

Kurulum:
pip install fastapi uvicorn python-jose passlib bcrypt supabase openai pandas numpy faker python-dateutil stripe

Çalıştır:
uvicorn main:app --reload
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import os
import jwt
import bcrypt
import json
from datetime import datetime, timedelta

# ── Analiz modülleri
import sys
sys.path.insert(0, os.path.dirname(__file__))
from data_layer import ShopifyConfig, run_pipeline
from ai_engine import AIConfig, AIAnalysisEngine
from meta_ads import MetaConfig, run_meta_analysis
from pdf_report import generate_pdf_report

app = FastAPI(title="OPS Intelligence API", version="1.0.0")

# ── CORS — Netlify'dan gelen isteklere izin ver
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://opswebsitedot.netlify.app",
        "http://localhost:3000",
        "http://localhost:8080",
        "*",  # Geliştirme için
    ],
    allow_credentials=True,
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
    meta_token: Optional[str] = None
    meta_account: Optional[str] = None
    use_mock_meta: bool = True
    language: str = "tr"


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
    plan = PLANS.get(user["plan"], PLANS["free"])
    return {
        "user": user,
        "plan": plan,
    }


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

    # Shopify config
    shopify_cfg = ShopifyConfig(
        shop_domain=req.shopify_domain or "",
        access_token=req.shopify_token or "",
        use_mock=req.use_mock,
        mock_order_count=200,
    )

    # Veri çek
    report = run_pipeline(shopify_cfg)

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
                "products": inv["details"].to_dict("records"),
            },
        },
        "meta": meta_data,
        "shop_name": req.shopify_domain or "Demo Mağaza",
    }


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
# PLAN ENDPOINTİ
# ─────────────────────────────────────────────

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
