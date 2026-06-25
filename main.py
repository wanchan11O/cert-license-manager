import os
import socket
import ssl
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, date, timedelta

from fastapi import FastAPI, Request, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import bcrypt as _bcrypt
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from database import init_db, get_db

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
DB_PATH = os.environ.get("DB_PATH", "app.db")


def hash_password(password: str) -> str:
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return _bcrypt.checkpw(password.encode(), hashed.encode())


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db(DB_PATH)
    yield


app = FastAPI(title="Cert & License Manager", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")


def uid(request: Request):
    return request.session.get("user_id")


def get_status(expires_at: str) -> str:
    today = date.today()
    exp = date.fromisoformat(expires_at)
    if exp < today:
        return "expired"
    if exp <= today + timedelta(days=30):
        return "warning"
    return "ok"


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    if uid(request):
        return RedirectResponse("/", 302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login")
async def login_post(request: Request,
                     email: str = Form(...), password: str = Form(...)):
    with get_db(DB_PATH) as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return templates.TemplateResponse("login.html",
            {"request": request, "error": "メールまたはパスワードが違います"})
    request.session["user_id"] = row["id"]
    return RedirectResponse("/", 302)


@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    if uid(request):
        return RedirectResponse("/", 302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@app.post("/register")
async def register_post(request: Request,
                        email: str = Form(...), password: str = Form(...)):
    if len(password) < 8:
        return templates.TemplateResponse("register.html",
            {"request": request, "error": "パスワードは8文字以上にしてください"})
    try:
        with get_db(DB_PATH) as db:
            db.execute("INSERT INTO users (email, password_hash) VALUES (?,?)",
                       (email, hash_password(password)))
            db.commit()
    except sqlite3.IntegrityError:
        return templates.TemplateResponse("register.html",
            {"request": request, "error": "そのメールアドレスは既に登録されています"})
    return RedirectResponse("/login", 302)


@app.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", 302)


# ── Certificate auto-fetch ────────────────────────────────────────────────────

@app.get("/api/cert-info")
async def cert_info(request: Request, domain: str = Query(...)):
    if not uid(request):
        return JSONResponse({"error": "認証が必要です"}, status_code=401)

    # Strip scheme / path / port
    domain = domain.strip().lower()
    domain = domain.replace("https://", "").replace("http://", "")
    domain = domain.split("/")[0].split(":")[0]

    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((domain, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=domain) as ssock:
                cert = ssock.getpeercert()
    except socket.timeout:
        return JSONResponse({"error": f"{domain} への接続がタイムアウトしました"}, status_code=400)
    except socket.gaierror:
        return JSONResponse({"error": f"ドメイン '{domain}' が見つかりません"}, status_code=400)
    except ssl.SSLError as e:
        return JSONResponse({"error": f"SSL エラー: {e.reason}"}, status_code=400)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)

    subject = dict(x[0] for x in cert["subject"])
    issuer  = dict(x[0] for x in cert["issuer"])
    expires = datetime.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").date()

    return JSONResponse({
        "domain":     subject.get("commonName", domain),
        "issuer":     issuer.get("organizationName") or issuer.get("commonName", ""),
        "expires_at": expires.isoformat(),
    })


# ── Dashboard ─────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        certs = db.execute(
            "SELECT * FROM certificates WHERE user_id=? ORDER BY expires_at", (user_id,)).fetchall()
        lics = db.execute(
            "SELECT * FROM licenses WHERE user_id=? ORDER BY expires_at", (user_id,)).fetchall()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "certs":    [{**dict(c), "status": get_status(c["expires_at"])} for c in certs],
        "licenses": [{**dict(l), "status": get_status(l["expires_at"])} for l in lics],
    })


# ── Certificates ──────────────────────────────────────────────────────────────

@app.get("/certificates/new", response_class=HTMLResponse)
async def cert_new(request: Request):
    if not uid(request):
        return RedirectResponse("/login", 302)
    return templates.TemplateResponse("cert_form.html", {"request": request, "cert": None})


@app.post("/certificates")
async def cert_create(request: Request,
                      domain: str = Form(...), issuer: str = Form(...), expires_at: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute("INSERT INTO certificates (user_id,domain,issuer,expires_at) VALUES (?,?,?,?)",
                   (user_id, domain, issuer, expires_at))
        db.commit()
    return RedirectResponse("/", 302)


@app.get("/certificates/{cid}/edit", response_class=HTMLResponse)
async def cert_edit(request: Request, cid: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        cert = db.execute(
            "SELECT * FROM certificates WHERE id=? AND user_id=?", (cid, user_id)).fetchone()
    if not cert:
        return RedirectResponse("/", 302)
    return templates.TemplateResponse("cert_form.html", {"request": request, "cert": dict(cert)})


@app.post("/certificates/{cid}/edit")
async def cert_update(request: Request, cid: int,
                      domain: str = Form(...), issuer: str = Form(...), expires_at: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute(
            "UPDATE certificates SET domain=?,issuer=?,expires_at=? WHERE id=? AND user_id=?",
            (domain, issuer, expires_at, cid, user_id))
        db.commit()
    return RedirectResponse("/", 302)


@app.post("/certificates/{cid}/delete")
async def cert_delete(request: Request, cid: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute("DELETE FROM certificates WHERE id=? AND user_id=?", (cid, user_id))
        db.commit()
    return RedirectResponse("/", 302)


# ── Licenses ──────────────────────────────────────────────────────────────────

@app.get("/licenses/new", response_class=HTMLResponse)
async def license_new(request: Request):
    if not uid(request):
        return RedirectResponse("/login", 302)
    return templates.TemplateResponse("license_form.html", {"request": request, "license": None})


@app.post("/licenses")
async def license_create(request: Request,
                         product_name: str = Form(...), license_key: str = Form(...), expires_at: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute("INSERT INTO licenses (user_id,product_name,license_key,expires_at) VALUES (?,?,?,?)",
                   (user_id, product_name, license_key, expires_at))
        db.commit()
    return RedirectResponse("/", 302)


@app.get("/licenses/{lid}/edit", response_class=HTMLResponse)
async def license_edit(request: Request, lid: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        lic = db.execute(
            "SELECT * FROM licenses WHERE id=? AND user_id=?", (lid, user_id)).fetchone()
    if not lic:
        return RedirectResponse("/", 302)
    return templates.TemplateResponse("license_form.html", {"request": request, "license": dict(lic)})


@app.post("/licenses/{lid}/edit")
async def license_update(request: Request, lid: int,
                         product_name: str = Form(...), license_key: str = Form(...), expires_at: str = Form(...)):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute(
            "UPDATE licenses SET product_name=?,license_key=?,expires_at=? WHERE id=? AND user_id=?",
            (product_name, license_key, expires_at, lid, user_id))
        db.commit()
    return RedirectResponse("/", 302)


@app.post("/licenses/{lid}/delete")
async def license_delete(request: Request, lid: int):
    user_id = uid(request)
    if not user_id:
        return RedirectResponse("/login", 302)
    with get_db(DB_PATH) as db:
        db.execute("DELETE FROM licenses WHERE id=? AND user_id=?", (lid, user_id))
        db.commit()
    return RedirectResponse("/", 302)
