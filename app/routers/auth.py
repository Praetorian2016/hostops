import os
from pathlib import Path
from fastapi import APIRouter, Request, Form, status, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from app.supabase_client import supabase_admin

# Percorso assoluto verso app/templates
TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()




templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()

# --- LOGIN ---
@router.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"request": request, "error": None}
    )

@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        res = supabase_admin.auth.sign_in_with_password({
            "email": email,
            "password": password
        })

        if not res.session:
            return templates.TemplateResponse(
                request=request,
                name="login.html",
                context={"request": request, "error": "Credenziali errate."},
                status_code=400
            )

        user_id = res.user.id
        prop_res = supabase_admin.table("properties").select("id").eq("user_id", user_id).execute()

        # Se l'host non ha ancora registrato strutture, va alla pagina nuova struttura
        next_url = "/dashboard" if (prop_res.data and len(prop_res.data) > 0) else "/properties/new"

        response = RedirectResponse(url=next_url, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            key="access_token",
            value=res.session.access_token,
            httponly=True,
            max_age=3600 * 24 * 7,
            samesite="lax"
        )
        return response

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"request": request, "error": f"Errore di accesso: {str(e)}"},
            status_code=400
        )

# --- REGISTRAZIONE ---
@router.get("/register")
async def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"request": request, "error": None}
    )

@router.post("/register")
async def register_submit(
    request: Request,
    full_name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...)
):
    try:
        res = supabase_admin.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {"full_name": full_name}
            }
        })

        if not res.user:
            return templates.TemplateResponse(
                request=request,
                name="register.html",
                context={"request": request, "error": "Impossibile completare la registrazione."},
                status_code=400
            )

        # Se la sessione è già attiva
        if res.session:
            response = RedirectResponse(url="/properties/new", status_code=status.HTTP_303_SEE_OTHER)
            response.set_cookie(
                key="access_token",
                value=res.session.access_token,
                httponly=True,
                max_age=3600 * 24 * 7,
                samesite="lax"
            )
            return response
        else:
            # Login diretto se la conferma email è disabilitata su Supabase
            login_res = supabase_admin.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            response = RedirectResponse(url="/properties/new", status_code=status.HTTP_303_SEE_OTHER)
            if login_res.session:
                response.set_cookie(
                    key="access_token",
                    value=login_res.session.access_token,
                    httponly=True,
                    max_age=3600 * 24 * 7,
                    samesite="lax"
                )
            return response

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"request": request, "error": f"Errore registrazione: {str(e)}"},
            status_code=400
        )

# --- NUOVA STRUTTURA ---
@router.get("/properties/new")
async def new_property_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    return templates.TemplateResponse(
        request=request,
        name="new_property.html",
        context={"request": request, "error": None}
    )

@router.post("/properties/new")
async def create_property(
    request: Request,
    name: str = Form(...),
    manager_name: str = Form(...),
    city: str = Form(...),
    province: str = Form(...),
    tax_rate: float = Form(6.00),
    max_taxable_nights: int = Form(10),
    ical_booking_url: str = Form(None)
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user_res = supabase_admin.auth.get_user(token)
        user_id = user_res.user.id

        new_prop = {
            "user_id": user_id,
            "name": name,
            "manager_name": manager_name,
            "city": city,
            "province": province.upper(),
            "tax_rate": tax_rate,
            "max_taxable_nights": max_taxable_nights,
            "ical_booking_url": ical_booking_url or ""
        }

        supabase_admin.table("properties").insert(new_prop).execute()
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)

    except Exception as e:
        return templates.TemplateResponse(
            request=request,
            name="new_property.html",
            context={"request": request, "error": f"Errore salvataggio struttura: {str(e)}"},
            status_code=400
        )

# --- LOGOUT ---
@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(key="access_token")
    return response