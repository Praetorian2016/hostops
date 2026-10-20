import shutil
from pathlib import Path
from fastapi import APIRouter, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.models import get_db_connection

router = APIRouter(prefix="/checkin", tags=["checkin"])
templates = Jinja2Templates(directory="templates")

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"

@router.get("/{booking_id}", response_class=HTMLResponse)
async def checkin_form(request: Request, booking_id: int):
    return templates.TemplateResponse(
        request=request,
        name="guest_checkin.html",
        context={"booking_id": booking_id}
    )

@router.post("/{booking_id}/submit")
async def checkin_submit(
    booking_id: int,
    last_name: str = Form(...),
    first_name: str = Form(...),
    gender: str = Form(...),
    birth_date: str = Form(...),
    birth_place_code: str = Form(...),
    citizenship_code: str = Form(...),
    doc_type: str = Form(...),
    doc_number: str = Form(...),
    doc_issuer_place: str = Form(...),
    doc_file: UploadFile = File(...),
    selfie_file: UploadFile = File(...)
):
    # Salva il file del documento
    doc_filename = f"booking_{booking_id}_doc_{doc_file.filename}"
    doc_path = UPLOAD_DIR / "documents" / doc_filename
    with open(doc_path, "wb") as buffer:
        shutil.copyfileobj(doc_file.file, buffer)

    # Salva il selfie
    selfie_filename = f"booking_{booking_id}_selfie_{selfie_file.filename}"
    selfie_path = UPLOAD_DIR / "selfies" / selfie_filename
    with open(selfie_path, "wb") as buffer:
        shutil.copyfileobj(selfie_file.file, buffer)

    # Percorsi web relativi per visualizzazione
    web_doc_path = f"/uploads/documents/{doc_filename}"
    web_selfie_path = f"/uploads/selfies/{selfie_filename}"

    # Inserimento nel database SQLite
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO guests (
            booking_id, guest_type, last_name, first_name, gender,
            birth_date, birth_place_code, citizenship_code,
            doc_type, doc_number, doc_issuer_place,
            doc_image_path, selfie_image_path, alloggiati_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
    """, (
        booking_id, 16, last_name.upper(), first_name.upper(), gender,
        birth_date, birth_place_code.upper(), citizenship_code.upper(),
        doc_type, doc_number.upper(), doc_issuer_place.upper(),
        web_doc_path, web_selfie_path
    ))
    conn.commit()
    conn.close()

    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="it">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <script src="https://cdn.tailwindcss.com"></script>
    </head>
    <body class="bg-slate-100 flex items-center justify-center min-h-screen p-4">
      <div class="bg-white p-8 rounded-2xl shadow-sm text-center max-w-sm w-full">
        <div class="w-14 h-14 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4 text-2xl font-bold">✓</div>
        <h2 class="text-xl font-bold text-slate-800 mb-2">Registrazione Ricevuta!</h2>
        <p class="text-sm text-slate-500">I tuoi dati e i documenti sono stati memorizzati con successo.</p>
      </div>
    </body>
    </html>
    """)