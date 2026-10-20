import sqlite3
from datetime import datetime, date
from icalendar import Calendar, Event
from fastapi import Response
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from app.models import get_db_connection
from app.services.calendar_sync import sync_external_ical_feeds

router = APIRouter(prefix="/calendar", tags=["Calendar"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# Colori per i canali nel calendario
CHANNEL_COLORS = {
    "Airbnb": "#FF5A5F",
    "Booking.com": "#003580",
    "Diretto": "#16a34a",
    "BLOCKED": "#64748b"
}

@router.get("", response_class=HTMLResponse)
async def calendar_page(request: Request):
    """Renderizza la pagina con il calendario interattivo."""
    return templates.TemplateResponse(request, "calendar.html", {"request": request})

@router.get("/events")
async def get_calendar_events():
    """Restituisce le prenotazioni e i blocchi formattati per FullCalendar."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, guest_name, channel, check_in, check_out, guests_count, gross_revenue
        FROM bookings
    """)
    rows = cursor.fetchall()
    conn.close()

    events = []
    for r in rows:
        channel = r["channel"] or "Diretto"
        color = CHANNEL_COLORS.get(channel, "#2563eb")
        is_blocked = (channel == "BLOCKED")

        events.append({
            "id": r["id"],
            "title": f"⛔ Blocco: {r['guest_name']}" if is_blocked else f"{r['guest_name']} ({channel})",
            "start": r["check_in"],
            "end": r["check_out"],  # In FullCalendar la data end è esclusiva, perfetta per il check-out
            "backgroundColor": color,
            "borderColor": color,
            "allDay": True,
            "extendedProps": {
                "channel": channel,
                "guests_count": r["guests_count"],
                "gross_revenue": r["gross_revenue"],
                "is_blocked": is_blocked
            }
        })
    return JSONResponse(content=events)

@router.post("/block-dates")
async def block_dates(
    reason: str = Form("Manutenzione / Uso Proprietario"),
    check_in: str = Form(...),
    check_out: str = Form(...)
):
    """Crea un blocco manuale date nel database."""
    from datetime import datetime
    try:
        d1 = datetime.strptime(check_in, "%Y-%m-%d")
        d2 = datetime.strptime(check_out, "%Y-%m-%d")
        nights = (d2 - d1).days
        if nights <= 0:
            raise HTTPException(status_code=400, detail="La data di fine blocco deve essere successiva all'inizio.")
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato date non valido (richiesto YYYY-MM-DD).")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO bookings (
            guest_name, channel, check_in, check_out, nights, guests_count,
            gross_revenue, ota_commission, cleaning_cost, linen_kit_cost, utilities_est, net_profit
        ) VALUES (?, 'BLOCKED', ?, ?, ?, 0, 0, 0, 0, 0, 0, 0)
    """, (reason, check_in, check_out, nights))
    conn.commit()
    conn.close()

    return {"status": "ok", "message": "Date bloccate con successo"}

@router.post("/delete-entry/{entry_id}")
async def delete_entry(entry_id: int):
    """Elimina una prenotazione o sblocca un periodo."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tourist_tax WHERE booking_id = ?", (entry_id,))
    cursor.execute("DELETE FROM guests WHERE booking_id = ?", (entry_id,))
    cursor.execute("DELETE FROM bookings WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Elemento rimosso"}

@router.post("/update-dates/{entry_id}")
async def update_dates(
    entry_id: int,
    check_in: str = Form(...),
    check_out: str = Form(...)
):
    """Aggiorna le date di una prenotazione o di un blocco."""
    from datetime import datetime
    d1 = datetime.strptime(check_in, "%Y-%m-%d")
    d2 = datetime.strptime(check_out, "%Y-%m-%d")
    nights = (d2 - d1).days
    if nights <= 0:
        raise HTTPException(status_code=400, detail="Intervallo date non valido.")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE bookings
        SET check_in = ?, check_out = ?, nights = ?
        WHERE id = ?
    """, (check_in, check_out, nights, entry_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Date aggiornate"}
@router.get("/export.ics")
async def export_calendar_ics():
    """Genera ed esporta il feed iCal conforme a RFC 5545 per le OTA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, guest_name, channel, check_in, check_out
        FROM bookings
    """)
    rows = cursor.fetchall()
    conn.close()

    cal = Calendar()
    cal.add('prodid', '-//HostOps Calendar//hostops.local//IT')
    cal.add('version', '2.0')
    cal.add('x-wr-calname', 'HostOps Disponibilita')

    for r in rows:
        event = Event()

        channel = r["channel"] or "Diretto"
        summary = "Non disponibile" if channel == "BLOCKED" else f"Occupato ({channel})"

        event.add('summary', summary)

        start_date = datetime.strptime(r["check_in"], "%Y-%m-%d").date()
        end_date = datetime.strptime(r["check_out"], "%Y-%m-%d").date()

        event.add('dtstart', start_date)
        event.add('dtend', end_date)
        event.add('dtstamp', datetime.utcnow())
        event.add('uid', f"booking-{r['id']}@hostops.local")

        cal.add_component(event)

    ics_content = cal.to_ical()

    return Response(
        content=ics_content,
        media_type="text/calendar; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="hostops_calendar.ics"'}
    )

@router.post("/sync-now")
async def trigger_sync():
    """Lancia la sincronizzazione immediata di tutti i calendari esterni."""
    imported_count = await sync_external_ical_feeds()
    return {"status": "ok", "imported": imported_count}

@router.post("/add-feed")
async def add_feed(
    channel_name: str = Form(...),
    feed_url: str = Form(...)
):
    """Salva l'URL iCal esportato da un portale OTA."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO ical_feeds (channel_name, feed_url)
        VALUES (?, ?)
    """, (channel_name, feed_url))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "Feed salvato con successo"}

@router.get("/mock-ota.ics")
async def mock_ota_calendar():
    """Genera un finto feed iCal OTA per testare la sincronizzazione in locale."""
    cal = Calendar()
    cal.add('prodid', '-//Mock OTA Feed//Booking//IT')
    cal.add('version', '2.0')

    # Prenotazione test 1
    ev1 = Event()
    ev1.add('summary', 'Laura Bianchi (Booking.com Mock)')
    ev1.add('dtstart', date(2026, 11, 3))
    ev1.add('dtend', date(2026, 11, 7))
    ev1.add('dtstamp', datetime.utcnow())
    ev1.add('uid', 'mock-booking-101@booking.mock')
    cal.add_component(ev1)

    # Prenotazione test 2
    ev2 = Event()
    ev2.add('summary', 'Marc Dupont (Booking.com Mock)')
    ev2.add('dtstart', date(2026, 11, 20))
    ev2.add('dtend', date(2026, 11, 24))
    ev2.add('dtstamp', datetime.utcnow())
    ev2.add('uid', 'mock-booking-102@booking.mock')
    cal.add_component(ev2)

    return Response(
        content=cal.to_ical(),
        media_type="text/calendar; charset=utf-8"
    )