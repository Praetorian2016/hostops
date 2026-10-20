from pathlib import Path
from datetime import date
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from app.models import get_db_connection
from app.services.alloggiati_web import export_booking_to_txt
from app.services.tourist_tax import calculate_tourist_tax

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

BASE_DIR = Path(__file__).resolve().parent.parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@router.get("", response_class=HTMLResponse)
async def view_dashboard(request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()

    bookings_query = """
        SELECT 
            b.id,
            b.guest_name,
            b.channel,
            b.check_in,
            b.check_out,
            b.nights,
            b.guests_count,
            COALESCE(b.gross_revenue, 0.0) AS gross_revenue,
            COALESCE(b.ota_commission, 0.0) AS ota_commission,
            COALESCE(b.cleaning_cost, 0.0) AS cleaning_cost,
            COALESCE(b.linen_kit_cost, 0.0) AS linen_kit_cost,
            COALESCE(b.utilities_est, 0.0) AS utilities_est,
            (COALESCE(b.gross_revenue, 0.0) - COALESCE(b.ota_commission, 0.0) - COALESCE(b.cleaning_cost, 0.0) - COALESCE(b.linen_kit_cost, 0.0) - COALESCE(b.utilities_est, 0.0)) AS calculated_net_profit,
            COUNT(g.id) AS registered_guests_count
        FROM bookings b
        LEFT JOIN guests g ON b.id = g.booking_id
        GROUP BY b.id
        ORDER BY b.check_in DESC
    """
    cursor.execute(bookings_query)
    raw_bookings = [dict(row) for row in cursor.fetchall()]

    # Calcolo della Tourist Tax per ciascuna prenotazione
    bookings = []
    total_tourist_tax = 0.0

    for b in raw_bookings:
        tax_info = calculate_tourist_tax(b["nights"], b["guests_count"])
        b["tourist_tax"] = tax_info["total_tax"]
        total_tourist_tax += tax_info["total_tax"]
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

    guests_query = """
        SELECT 
            g.*, 
            b.guest_name AS booking_guest_name
        FROM guests g
        JOIN bookings b ON g.booking_id = b.id
        ORDER BY g.id DESC
    """
    cursor.execute(guests_query)
    guests = [dict(row) for row in cursor.fetchall()]
    conn.close()

    context = {
        "request": request,
        "bookings": bookings,
        "totals": totals,
        "guests": guests,
    }

    return templates.TemplateResponse(request, "dashboard.html", context)


@router.get("/download-alloggiati/{booking_id}")
async def download_alloggiati(booking_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    booking_row = cursor.fetchone()
    if not booking_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Prenotazione non trovata.")

    cursor.execute("SELECT * FROM guests WHERE booking_id = ? ORDER BY guest_type ASC", (booking_id,))
    guest_rows = cursor.fetchall()

    if not guest_rows:
        conn.close()
        raise HTTPException(status_code=400, detail="Nessun ospite registrato per questa prenotazione.")

    booking_dict = dict(booking_row)
    guests_list = [dict(g) for g in guest_rows]

    txt_content = export_booking_to_txt(booking_dict, guests_list)

    cursor.execute("UPDATE guests SET alloggiati_status = 'GENERATED' WHERE booking_id = ?", (booking_id,))
    conn.commit()
    conn.close()

    filename = f"alloggiati_booking_{booking_id}.txt"
    return Response(
        content=txt_content,
        media_type="text/plain; charset=windows-1252",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/receipt/tourist-tax/{booking_id}")
async def generate_tourist_tax_receipt(booking_id: int, request: Request):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM bookings WHERE id = ?", (booking_id,))
    booking = cursor.fetchone()
    conn.close()

    if not booking:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata")

# Conversione da sqlite3.Row a dizionario nativo
    booking = dict(booking)

    # Calcolo imposta (Roma: 6€ per ospite a notte, max 10 notti)
    effective_nights = min(booking["nights"], 10)
    tax_total = booking["guests_count"] * effective_nights * 6.0

    today_str = date.today().strftime("%d/%m/%Y")
    receipt_year = str(booking["check_in"])[:4]

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