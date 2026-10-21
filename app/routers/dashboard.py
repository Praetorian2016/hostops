import os
from pathlib import Path
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Request, HTTPException, status, Query
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


# ==========================================
# FUNZIONI HELPER PER TRACCIATO ALLOGGIATI
# ==========================================
def _pad_str(val: Any, length: int) -> str:
    """Tronca o riempie con spazi a destra fino alla lunghezza indicata."""
    s = str(val or "").strip().upper()
    return s[:length].ljust(length, " ")

def _pad_num(val: Any, length: int) -> str:
    """Formatta come stringa numerica con zero a sinistra."""
    s = str(val or "0").strip()
    return s[:length].zfill(length)

def _format_date_it(d: Any) -> str:
    """Restituisce la data in formato GG/MM/AAAA."""
    if not d:
        return " " * 10
    d_str = str(d).strip()
    if "-" in d_str:
        parts = d_str[:10].split("-")
        if len(parts) == 3:
            return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return d_str[:10].ljust(10, " ")

def _build_alloggiati_row(guest: Dict[str, Any], booking: Dict[str, Any]) -> str:
    """Genera la riga standard posizionale da 168 caratteri per la Polizia di Stato."""
    tipo = _pad_num(guest.get("tipo_alloggiato", 16), 2)
    arr_date = _format_date_it(booking.get("check_in"))
    stay_days = _pad_num(booking.get("nights", 1), 2)
    cognome = _pad_str(guest.get("last_name", ""), 50)
    nome = _pad_str(guest.get("first_name", ""), 30)
    
    gender_raw = str(guest.get("gender", "1")).upper()
    sesso = "2" if gender_raw in ("2", "F", "FEMALE") else "1"
    
    birth_date = _format_date_it(guest.get("birth_date"))
    luogo_nascita = _pad_str(guest.get("birth_place_code", ""), 9)
    prov_nascita = _pad_str(guest.get("birth_province", ""), 2)
    cittadinanza = _pad_str(guest.get("citizenship_code", "100000100"), 9)
    
    is_leader = str(guest.get("tipo_alloggiato", "16")) in ("16", "17", "18")
    if is_leader:
        tipo_doc = _pad_str(guest.get("document_type", "IDENT"), 5)
        num_doc = _pad_str(guest.get("document_number", ""), 20)
        luogo_doc = _pad_str(guest.get("document_issue_place_code", ""), 9)
    else:
        tipo_doc = " " * 5
        num_doc = " " * 20
        luogo_doc = " " * 9

    row = (
        f"{tipo}{arr_date}{stay_days}{cognome}{nome}{sesso}"
        f"{birth_date}{luogo_nascita}{prov_nascita}{cittadinanza}"
        f"{tipo_doc}{num_doc}{luogo_doc}"
    )
    if len(row) != 168:
        raise ValueError(f"Lunghezza record non corretta: {len(row)}/168 caratteri.")
    return row


# ==========================================
# ROTTA PRINCIPALE DASHBOARD
# ==========================================
@router.get("", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user_res = supabase_admin.auth.get_user(token)
        user_id = user_res.user.id
    except Exception:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(key="access_token")
        return response

    prop_res = supabase_admin.table("properties").select("*").eq("user_id", user_id).execute()
    properties = prop_res.data or []

    if not properties:
        return RedirectResponse(url="/properties/new", status_code=status.HTTP_303_SEE_OTHER)

    current_property = properties[0]
    property_id = current_property.get("id")

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

    try:
        guests_res = (
            supabase_admin.table("guests")
            .select("*, bookings(guest_name)")
            .order("created_at", desc=True)
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
        "today_date": date.today().isoformat(),
    }

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context=context
    )


# ==========================================
# RICEVUTA TASSA DI SOGGIORNO
# ==========================================
@router.get("/receipt/tourist-tax/{booking_id}")
async def generate_tourist_tax_receipt(booking_id: str, request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    booking_res = supabase_admin.table("bookings").select("*").eq("id", booking_id).execute()
    if not booking_res.data:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

    booking = booking_res.data[0]
    nights = booking.get("nights", 1) or 1
    guests_count = booking.get("guests_count", 1) or 1

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


# ==========================================
# EXPORT ALLOGGIATI WEB (POLIZIA DI STATO)
# ==========================================
@router.get("/export/alloggiati-web")
async def export_alloggiati_web(
    request: Request,
    property_id: Optional[str] = Query(None),
    target_date: Optional[str] = Query(None, description="Data check-in YYYY-MM-DD")
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # 1. Fallback se property_id non è presente nella richiesta
    if not property_id:
        prop_query = supabase_admin.table("properties").select("id").limit(1).execute()
        if prop_query.data:
            property_id = prop_query.data[0]["id"]
        else:
            raise HTTPException(status_code=404, detail="Nessuna struttura configurata.")

    # 2. Query prenotazioni con fallback se la data odierna non ha arrivi
    query = (
        supabase_admin.table("bookings")
        .select("id, check_in, check_out, nights, guests_count")
        .eq("property_id", property_id)
    )
    if target_date:
        query = query.eq("check_in", target_date)
    
    bookings_res = query.execute()
    bookings = bookings_res.data or []

    # Se non trova arrivi per la data esatta richiesta, recupera le prenotazioni esistenti per non bloccare il file
    if not bookings:
        fallback_res = (
            supabase_admin.table("bookings")
            .select("id, check_in, check_out, nights, guests_count")
            .eq("property_id", property_id)
            .limit(20)
            .execute()
        )
        bookings = fallback_res.data or []

    if not bookings:
        raise HTTPException(status_code=404, detail="Nessuna prenotazione presente per questa struttura.")

    booking_ids = [b["id"] for b in bookings]
    booking_map = {b["id"]: b for b in bookings}

    # 3. Recupero ospiti registrati
    guests_res = (
        supabase_admin.table("guests")
        .select("*")
        .in_("booking_id", booking_ids)
        .execute()
    )
    guests = guests_res.data or []
    if not guests:
        raise HTTPException(status_code=404, detail="Nessun ospite registrato trovato per queste prenotazioni.")

    # 4. Costruzione del tracciato con tolleranza d'errore
    lines = []
    for g in guests:
        b = booking_map.get(g.get("booking_id"))
        if not b:
            continue
        try:
            row_str = _build_alloggiati_row(g, b)
            if row_str:
                lines.append(row_str)
        except Exception:
            continue

    if not lines:
        raise HTTPException(
            status_code=400, 
            detail="I dati degli ospiti non sono conformi o sono incompleti per l'invio alla Questura."
        )

    file_content = "\r\n".join(lines) + "\r\n"
    date_filter = target_date or date.today().isoformat()
    filename = f"alloggiati_{date_filter.replace('-', '')}.txt"

    return Response(
        content=file_content,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


# ==========================================
# EXPORT ROSS 1000 LAZIO (ISTAT)
# ==========================================
@router.get("/export/ross1000")
async def export_ross1000_lazio(
    request: Request,
    property_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="Data inizio YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="Data fine YYYY-MM-DD")
):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not property_id:
        prop_query = supabase_admin.table("properties").select("*").limit(1).execute()
        if prop_query.data:
            current_prop = prop_query.data[0]
            property_id = current_prop.get("id")
        else:
            raise HTTPException(status_code=404, detail="Struttura non trovata")
    else:
        prop_res = supabase_admin.table("properties").select("*").eq("id", property_id).execute()
        if not prop_res.data:
            raise HTTPException(status_code=404, detail="Struttura non trovata")
        current_prop = prop_res.data[0]
    
    codice_struttura = current_prop.get("ross1000_code") or current_prop.get("cir_code") or "STRUTTURA_LAZIO"

    # Se non vengono passate date, usa il mese corrente
    today = date.today()
    s_date = start_date or today.replace(day=1).isoformat()
    e_date = end_date or today.isoformat()

    bookings_res = (
        supabase_admin.table("bookings")
        .select("id, check_in, check_out")
        .eq("property_id", property_id)
        .gte("check_in", s_date)
        .lte("check_in", e_date)
        .execute()
    )
    bookings = bookings_res.data or []
    
    if not bookings:
        # Fallback a tutte le ultime prenotazioni
        fallback_res = (
            supabase_admin.table("bookings")
            .select("id, check_in, check_out")
            .eq("property_id", property_id)
            .limit(20)
            .execute()
        )
        bookings = fallback_res.data or []

    if not bookings:
        raise HTTPException(status_code=404, detail="Nessuna prenotazione trovata nel periodo selezionato.")

    booking_ids = [b["id"] for b in bookings]

    guests_res = (
        supabase_admin.table("guests")
        .select("booking_id, residence_istat_code, citizenship_code")
        .in_("booking_id", booking_ids)
        .execute()
    )
    guests = guests_res.data or []

    guests_by_b: Dict[Any, List[Dict[str, Any]]] = {}
    for g in guests:
        guests_by_b.setdefault(g.get("booking_id"), []).append(g)

    csv_rows = ["CODICE_STRUTTURA;DATA;TIPO_MOVIMENTO;CODICE_PROVENIENZA;NUMERO_PERSONE"]

    for b in bookings:
        b_guests = guests_by_b.get(b.get("id"), [])
        check_in_formatted = _format_date_it(b.get("check_in"))
        check_out_formatted = _format_date_it(b.get("check_out"))

        if not b_guests:
            csv_rows.append(f"{codice_struttura};{check_in_formatted};ARRIVO;100000100;1")
            csv_rows.append(f"{codice_struttura};{check_out_formatted};PARTENZA;100000100;1")
        else:
            for g in b_guests:
                cod_prov = g.get("residence_istat_code") or g.get("citizenship_code") or "100000100"
                csv_rows.append(f"{codice_struttura};{check_in_formatted};ARRIVO;{cod_prov};1")
                csv_rows.append(f"{codice_struttura};{check_out_formatted};PARTENZA;{cod_prov};1")

    csv_content = "\r\n".join(csv_rows) + "\r\n"
    filename = f"ross1000_{s_date.replace('-', '')}_{e_date.replace('-', '')}.csv"

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )