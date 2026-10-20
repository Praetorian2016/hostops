import os
from pathlib import Path
from datetime import datetime, date
from icalendar import Calendar, Event
from fastapi import APIRouter, HTTPException, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.supabase_client import supabase_admin
from app.services.calendar_sync import sync_external_ical_feeds

router = APIRouter(prefix="/calendar", tags=["Calendar"])

# Percorsi template compatibili con Vercel e ambiente locale
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

# Palette per i canali nel calendario
CHANNEL_COLORS = {
    "Airbnb": "#FF5A5F",
    "Booking.com": "#003580",
    "Diretto": "#16a34a",
    "BLOCKED": "#64748b"
}


def _get_user_property_id(request: Request) -> tuple[str, str]:
    """Verifica il token e recupera user_id e property_id primaria."""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Non autenticato")

    try:
        user_res = supabase_admin.auth.get_user(token)
        user_id = user_res.user.id
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sessione scaduta")

    prop_res = supabase_admin.table("properties").select("id").eq("user_id", user_id).execute()
    properties = prop_res.data or []
    if not properties:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Nessuna struttura associata")

    return user_id, properties[0]["id"]


@router.get("", response_class=HTMLResponse)
async def calendar_page(request: Request):
    """Renderizza la pagina con il calendario interattivo."""
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    try:
        _, property_id = _get_user_property_id(request)
    except HTTPException:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    prop_res = supabase_admin.table("properties").select("*").eq("id", property_id).execute()
    current_property = prop_res.data[0] if prop_res.data else None

    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={"request": request, "property": current_property}
    )


@router.get("/events")
async def get_calendar_events(request: Request):
    """Restituisce le prenotazioni e i blocchi formattati per FullCalendar da Supabase."""
    try:
        _, property_id = _get_user_property_id(request)
    except HTTPException as e:
        return JSONResponse(status_code=e.status_code, content={"error": e.detail})

    res = (
        supabase_admin.table("bookings")
        .select("id, guest_name, channel, check_in, check_out, guests_count, gross_revenue")
        .eq("property_id", property_id)
        .execute()
    )
    rows = res.data or []

    events = []
    for r in rows:
        channel = r.get("channel") or "Diretto"
        color = CHANNEL_COLORS.get(channel, "#2563eb")
        is_blocked = (channel == "BLOCKED")
        guest = r.get("guest_name") or "Ospite"

        events.append({
            "id": str(r["id"]),
            "title": f"⛔ Blocco: {guest}" if is_blocked else f"{guest} ({channel})",
            "start": r["check_in"],
            "end": r["check_out"],  # In FullCalendar end è esclusivo
            "backgroundColor": color,
            "borderColor": color,
            "allDay": True,
            "extendedProps": {
                "channel": channel,
                "guests_count": r.get("guests_count", 1),
                "gross_revenue": r.get("gross_revenue", 0.0),
                "is_blocked": is_blocked
            }
        })
    return JSONResponse(content=events)


@router.post("/block-dates")
async def block_dates(
    request: Request,
    reason: str = Form("Manutenzione / Uso Proprietario"),
    check_in: str = Form(...),
    check_out: str = Form(...)
):
    """Crea un blocco manuale date su Supabase."""
    _, property_id = _get_user_property_id(request)

    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (d2 - d1).days
        if nights <= 0:
            raise HTTPException(status_code=400, detail="La data di fine blocco deve essere successiva all'inizio.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato date non valido (richiesto YYYY-MM-DD).")

    supabase_admin.table("bookings").insert({
        "property_id": property_id,
        "guest_name": reason,
        "channel": "BLOCKED",
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "guests_count": 0,
        "gross_revenue": 0.0,
        "ota_commission": 0.0,
        "cleaning_cost": 0.0,
        "linen_kit_cost": 0.0,
        "utilities_est": 0.0,
        "net_profit": 0.0
    }).execute()

    return {"status": "ok", "message": "Date bloccate con successo"}


@router.post("/delete-entry/{entry_id}")
async def delete_entry(entry_id: str, request: Request):
    """Elimina una prenotazione o sblocca un periodo su Supabase."""
    _get_user_property_id(request)
    
    supabase_admin.table("guests").delete().eq("booking_id", entry_id).execute()
    supabase_admin.table("bookings").delete().eq("id", entry_id).execute()

    return {"status": "ok", "message": "Elemento rimosso"}


@router.post("/update-dates/{entry_id}")
async def update_dates(
    entry_id: str,
    request: Request,
    check_in: str = Form(...),
    check_out: str = Form(...)
):
    """Aggiorna le date di una prenotazione o blocco."""
    _get_user_property_id(request)

    d1 = datetime.strptime(check_in, "%Y-%m-%d")
    d2 = datetime.strptime(check_out, "%Y-%m-%d")
    nights = (d2 - d1).days
    if nights <= 0:
        raise HTTPException(status_code=400, detail="Intervallo date non valido.")

    supabase_admin.table("bookings").update({
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights
    }).eq("id", entry_id).execute()

    return {"status": "ok", "message": "Date aggiornate"}


@router.get("/export.ics")
async def export_calendar_ics(request: Request):
    """Genera ed esporta il feed iCal conforme a RFC 5545 per le OTA da Supabase."""
    _, property_id = _get_user_property_id(request)

    res = supabase_admin.table("bookings").select("id, guest_name, channel, check_in, check_out").eq("property_id", property_id).execute()
    rows = res.data or []

    cal = Calendar()
    cal.add('prodid', '-//HostOps Calendar//hostops.local//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'HostOps Disponibilita')

    for r in rows:
        event = Event()
        channel = r.get("channel") or "Diretto"
        summary = "Non disponibile" if channel == "BLOCKED" else f"Occupato ({channel})"

        event.add('summary', summary)
        start_date = datetime.strptime(r["check_in"][:10], "%Y-%m-%d").date()
        end_date = datetime.strptime(r["check_out"][:10], "%Y-%m-%d").date()

        event.add('dtstart', start_date)
        event.add('dtend', end_date)
        event.add('dtstamp', datetime.utcnow())
        event.add('uid', f"booking-{r['id']}@hostops.local")

        cal.add_component(event)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="hostops_calendar.ics"'}
    )


@router.post("/sync-now")
async def trigger_sync(request: Request):
    """Lancia la sincronizzazione immediata dei feed esterni."""
    _get_user_property_id(request)
    try:
        imported_count = await sync_external_ical_feeds()
        return {"status": "ok", "imported": imported_count}
    except Exception as e:
        return {"status": "warning", "message": str(e), "imported": 0}