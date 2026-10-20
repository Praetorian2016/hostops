import os
from pathlib import Path
from datetime import date
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from app.supabase_client import supabase_admin
from app.services.tourist_tax import calculate_tourist_tax

# Percorsi robusti per i template su Vercel e in locale
BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

search_paths = [
    str(BASE_DIR / "templates"),
    str(ROOT_DIR / "templates"),
    "/var/task/app/templates",
    "/var/task/templates",
]
valid_paths = [p for p in search_paths if os.path.exists(p)] or [str(BASE_DIR / "templates")]
templates = Jinja2Templates(directory=valid_paths)

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user_res = supabase_admin.auth.get_user(token)
        user_id = user_res.user.id
    except Exception:
        # Se il token è scaduto o non valido, rimanda al login
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key="access_token")
        return response

    # 1. Recupera la struttura associata all'utente
    prop_res = supabase_admin.table("properties").select("*").eq("user_id", user_id).execute()
    properties = prop_res.data or []

    if not properties:
        return RedirectResponse(url="/properties/new", status_code=status.HTTP_303_SEE_OTHER)

    current_property = properties[0]
    property_id = current_property.get("id")

    # 2. Recupera prenotazioni della struttura da Supabase
    try:
        bookings_res = (
            supabase_admin.table("bookings")
            .select("*")
            .eq("property_id", property_id)
            .order("check_in", desc=True)
            .execute()
        )
        raw_bookings = bookings_res.data or []
    except Exception:
        raw_bookings = []

    # 3. Elaborazione prenotazioni e imposte
    bookings = []
    total_tourist_tax = 0.0

    for b in raw_bookings:
        nights = b.get("nights", 1) or 1
        guests_count = b.get("guests_count", 1) or 1
        
        try:
            tax_info = calculate_tourist_tax(nights, guests_count)
            tax_amount = tax_info.get("total_tax", 0.0)
        except Exception:
            tax_amount = min(nights, 10) * guests_count * float(current_property.get("tax_rate", 6.0))

        b["tourist_tax"] = tax_amount
        total_tourist_tax += tax_amount

        # Coalesce dei valori finanziari
        gross = float(b.get("gross_revenue") or 0.0)
        ota = float(b.get("ota_commission") or 0.0)
        cleaning = float(b.get("cleaning_cost") or 0.0)
        linen = float(b.get("linen_kit_cost") or 0.0)
        utilities = float(b.get("utilities_est") or 0.0)
        
        b["gross_revenue"] = gross
        b["ota_commission"] = ota
        b["cleaning_cost"] = cleaning
        b["linen_kit_cost"] = linen
        b["utilities_est"] = utilities
        b["calculated_net_profit"] = gross - ota - cleaning - linen - utilities
        bookings.append(b)

    totals = {
        "total_bookings": len(bookings),
        "gross": sum(b["gross_revenue"] for b in bookings),
        "ota_commission": sum(b["ota_commission"] for b in bookings),
        "cleaning_linen": sum(b["cleaning_cost"] + b["linen_kit_cost"] for b in bookings),
        "utilities": sum(b["utilities_est"] for b in bookings),
        "net_profit": sum(b["calculated_net_profit"] for b in bookings),
        "total_tourist_tax": total_tourist_tax,
    }

    # 4. Recupera ospiti da Supabase
    try:
        guests_res = (
            supabase_admin.table("guests")
            .select("*, bookings(guest_name)")
            .order("id", desc=True)
            .execute()
        )
        guests = guests_res.data or []
    except Exception:
        guests = []

    context = {
        "request": request,
        "property": current_property,
        "properties": properties,
        "bookings": bookings,
        "totals": totals,
        "guests": guests,
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context
    )


@router.get("/receipt/tourist-tax/{booking_id}")
async def generate_tourist_tax_receipt(booking_id: int, request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    booking_res = supabase_admin.table("bookings").select("*").eq("id", booking_id).execute()
    if not booking_res.data:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    booking = booking_res.data[0]
    nights = booking.get("nights", 1)
    guests_count = booking.get("guests_count", 1)

    effective_nights = min(nights, 10)
    tax_total = guests_count * effective_nights * 6.0

    today_str = date.today().strftime("%d/%m/%Y")
    receipt_year = str(booking.get("check_in", ""))[:4]

    return templates.TemplateResponse(
        request=request,
        name="receipt_tourist_tax.html",
        context={
            "booking": booking,
            "receipt_year": receipt_year,
            "tourist_tax": tax_total,
            "today_date": today_str
        }
    )