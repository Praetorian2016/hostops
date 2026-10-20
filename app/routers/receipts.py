import os
from pathlib import Path
import uuid
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from app.supabase_client import supabase_admin

# Risoluzione percorso assoluto alla cartella templates (compatibile con Vercel)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

router = APIRouter()

def is_valid_uuid(val: str) -> bool:
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False

@router.get("/receipt/{booking_id}")
async def get_tourist_tax_receipt(booking_id: str, request: Request):
    # 1. Recupero prenotazione
    if is_valid_uuid(booking_id):
        booking_res = supabase_admin.table("bookings").select("*").eq("id", booking_id).execute()
    else:
        booking_res = supabase_admin.table("bookings").select("*").eq("channel_booking_id", booking_id).execute()

    if not booking_res.data:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    booking = booking_res.data[0]
    property_id = booking.get("property_id")

    # 2. Recupero struttura
    prop_res = supabase_admin.table("properties").select("*").eq("id", property_id).execute()
    if not prop_res.data:
        raise HTTPException(status_code=404, detail="Struttura non trovata")
    
    prop = prop_res.data[0]

    # 3. Calcolo date, notti e importi
    d_in = datetime.strptime(booking["check_in"], "%Y-%m-%d")
    d_out = datetime.strptime(booking["check_out"], "%Y-%m-%d")
    total_nights = max((d_out - d_in).days, 1)

    max_nights = prop.get("max_taxable_nights") or 10
    taxable_nights = min(total_nights, max_nights)
    rate = float(prop.get("tax_rate", 6.00))
    adults = int(booking.get("adults_count") or 1)
    total_amount = float(taxable_nights * adults * rate)
    
    now = datetime.now()
    current_date = now.strftime("%d/%m/%Y")
    current_year = str(now.year)
    
    # Se presente, usa il channel_booking_id come id visualizzato, altrimenti i primi caratteri dell'UUID
    display_id = str(booking.get("channel_booking_id") or booking.get("id", "")[:8])
    booking["id"] = display_id
    booking["channel"] = booking.get("channel") or "Booking.com"

    # Campi per il rendering nel template HTML
    booking["nights"] = total_nights
    booking["total_nights"] = total_nights
    booking["taxable_nights"] = taxable_nights
    booking["adults"] = adults
    booking["adults_count"] = adults
    booking["guests_count"] = adults
    booking["taxable_guests"] = adults
    booking["rate"] = rate
    booking["tourist_tax"] = total_amount

    context = {
        "request": request,
        "property": prop,
        "booking": booking,
        "receipt_year": current_year,
        "today_date": current_date,
        "tourist_tax": total_amount,
        "tourist_tax_amount": total_amount,
        "tourist_tax_rate": rate,
        "tax_rate": rate,
        "total_amount": total_amount,
        "rate": rate,
        "taxable_nights": taxable_nights,
        "total_nights": total_nights,
        "nights": total_nights,
        "adults": adults,
        "adults_count": adults,
        "guests_count": adults,
        "taxable_guests": adults,
        "guests": adults,
        "total_amount_formatted": f"{total_amount:.2f}",
        "rate_formatted": f"{rate:.2f}"
    }

    return templates.TemplateResponse(
        request=request,
        name="receipt_tourist_tax.html",
        context=context
    )