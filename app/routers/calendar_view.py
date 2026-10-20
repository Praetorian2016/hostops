import os
from pathlib import Path
from datetime import datetime
from icalendar import Calendar, Event
from fastapi import APIRouter, HTTPException, Request, Form, status
from fastapi.responses import JSONResponse, HTMLResponse, Response, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.supabase_client import supabase_admin

router = APIRouter(prefix="/calendar", tags=["Calendar"])

# Percorsi robusti per Jinja2 identici a dashboard.py
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

CHANNEL_COLORS = {
    "Airbnb": "#FF5A5F",
    "Booking.com": "#003580",
    "Diretto": "#16a34a",
    "BLOCKED": "#64748b"
}


def _get_user_property(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return None, None

    try:
        user_res = supabase_admin.auth.get_user(token)
        user_id = user_res.user.id
    except Exception:
        return None, None

    prop_res = supabase_admin.table("properties").select("*").eq("user_id", user_id).execute()
    properties = prop_res.data or []
    if not properties:
        return user_id, None

    return user_id, properties[0]


@router.get("", response_class=HTMLResponse)
async def calendar_page(request: Request):
    user_id, current_property = _get_user_property(request)
    if not user_id:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    if not current_property:
        return RedirectResponse(url="/properties/new", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request=request,
        name="calendar.html",
        context={"request": request, "property": current_property}
    )


@router.get("/events")
async def get_calendar_events(request: Request):
    _, current_property = _get_user_property(request)
    if not current_property:
        return JSONResponse(status_code=401, content={"error": "Non autenticato"})

    res = (
        supabase_admin.table("bookings")
        .select("id, guest_name, channel, check_in, check_out, guests_count, gross_revenue")
        .eq("property_id", current_property["id"])
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
            "start": str(r["check_in"])[:10],
            "end": str(r["check_out"])[:10],
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


@router.get("/export.ics")
async def export_calendar_ics(request: Request):
    _, current_property = _get_user_property(request)
    if not current_property:
        raise HTTPException(status_code=401, detail="Non autenticato")

    res = (
        supabase_admin.table("bookings")
        .select("id, guest_name, channel, check_in, check_out")
        .eq("property_id", current_property["id"])
        .execute()
    )
    rows = res.data or []

    cal = Calendar()
    cal.add('prodid', '-//HostOps Calendar//hostops.local//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', f"HostOps - {current_property.get('name', 'Calendario')}")

    for r in rows:
        event = Event()
        channel = r.get("channel") or "Diretto"
        summary = "Non disponibile" if channel == "BLOCKED" else f"Occupato ({channel})"

        event.add('summary', summary)
        event.add('dtstart', datetime.strptime(str(r["check_in"])[:10], "%Y-%m-%d").date())
        event.add('dtend', datetime.strptime(str(r["check_out"])[:10], "%Y-%m-%d").date())
        event.add('dtstamp', datetime.utcnow())
        event.add('uid', f"booking-{r['id']}@hostops.local")
        cal.add_component(event)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="hostops_calendar.ics"'}
    )