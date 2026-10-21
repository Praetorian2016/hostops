import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import UploadFile, File, HTTPException
from app.services.document_scanner import extract_guest_data_from_image

from app.supabase_client import supabase_admin

router = APIRouter(prefix="/checkin", tags=["checkin"])

# Risoluzione template multi-path
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


async def _upload_to_supabase(file: UploadFile, folder: str, booking_id: str) -> Optional[str]:
    """Upload su Supabase Storage nel bucket 'documents'."""
    if not file or not file.filename:
        return None
    try:
        content = await file.read()
        if not content:
            return None
        
        file_ext = Path(file.filename).suffix or ".jpg"
        file_name = f"{folder}/b_{booking_id}_{uuid.uuid4().hex[:8]}{file_ext}"

        supabase_admin.storage.from_("documents").upload(
            file_name,
            content,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )
        return file_name
    except Exception:
        return None


@router.get("/{booking_id}", response_class=HTMLResponse)
async def checkin_form(request: Request, booking_id: str):
    """Renderizza il form di check-in per l'ospite."""
    b_res = (
        supabase_admin.table("bookings")
        .select("*, properties(name, city)")
        .eq("id", booking_id)
        .execute()
    )
    if not b_res.data:
        raise HTTPException(status_code=404, detail="Prenotazione non trovata.")

    booking = b_res.data[0]
    current_property = booking.get("properties")

    return templates.TemplateResponse(
        request=request,
        name="guest_checkin.html",
        context={
            "request": request,
            "booking": booking,
            "property": current_property,
            "booking_id": booking_id
        }
    )


@router.post("/{booking_id}", response_class=HTMLResponse)
@router.post("/{booking_id}/submit", response_class=HTMLResponse)
async def checkin_submit(
    booking_id: str,
    last_name: str = Form(...),
    first_name: str = Form(...),
    gender: str = Form("1"),
    birth_date: str = Form(...),
    birth_place_code: str = Form(""),
    birth_province: str = Form(""),
    citizenship_code: str = Form("100000100"),
    document_type: str = Form(None),
    doc_type: str = Form(None),
    document_number: str = Form(None),
    doc_number: str = Form(None),
    document_issue_place_code: str = Form(None),
    doc_issuer_place: str = Form(None),
    doc_file: UploadFile = File(None),
    selfie_file: UploadFile = File(None)
):
    """Salva i dati dell'ospite nella tabella guests su Supabase."""
    # Gestione fallback per i nomi dei campi input provenienti dal form HTML
    final_doc_type = (document_type or doc_type or "IDENT").strip()
    final_doc_number = (document_number or doc_number or "").strip().upper()
    final_doc_issuer = (document_issue_place_code or doc_issuer_place or "").strip().upper()

    # Upload facoltativo documenti
    doc_url = await _upload_to_supabase(doc_file, "documents", booking_id)
    selfie_url = await _upload_to_supabase(selfie_file, "selfies", booking_id)

    # Payload strettamente conforme allo schema reale di Supabase
    guest_payload = {
        "booking_id": booking_id,
        "tipo_alloggiato": 16,
        "first_name": first_name.strip().upper(),
        "last_name": last_name.strip().upper(),
        "gender": str(gender).strip(),
        "birth_date": birth_date.strip() if birth_date else None,
        "birth_place_code": birth_place_code.strip().upper() if birth_place_code else None,
        "birth_province": birth_province.strip()[:2].upper() if birth_province else None,
        "citizenship_code": citizenship_code.strip().upper() if citizenship_code else "100000100",
        "document_type": final_doc_type if final_doc_number else None,
        "document_number": final_doc_number if final_doc_number else None,
        "document_issue_place_code": final_doc_issuer if final_doc_issuer else None,
        "document_front_url": doc_url,
        "document_back_url": selfie_url
    }

    # Esecuzione insert su Supabase
    supabase_admin.table("guests").insert(guest_payload).execute()

    return HTMLResponse("""
    <!DOCTYPE html>
    <html lang="it">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Check-in Confermato - HostOps</title>
      <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@500;700;800&display=swap" rel="stylesheet">
      <style>
        body { background-color: #0b0f19; color: #f9fafb; font-family: 'Plus Jakarta Sans', sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; margin: 0; padding: 16px; }
        .success-box { background-color: #111827; border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 36px 28px; text-align: center; max-width: 420px; width: 100%; }
        .icon { width: 56px; height: 56px; background: rgba(16, 185, 129, 0.12); color: #10b981; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin: 0 auto 18px; font-size: 26px; font-weight: 800; }
        h2 { font-size: 1.4rem; margin-bottom: 8px; color: #fff; }
        p { font-size: 0.9rem; color: #9ca3af; line-height: 1.5; }
      </style>
    </head>
    <body>
      <div class="success-box">
        <div class="icon">&#10003;</div>
        <h2>Registrazione Ricevuta!</h2>
        <p>I tuoi dati identificativi sono stati acquisiti con successo. Ti auguriamo un piacevole soggiorno!</p>
      </div>
    </body>
    </html>
    """)

@router.post("/api/scan-document")
async def scan_document(file: UploadFile = File(...)):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Il file caricato deve essere un'immagine.")
    
    contents = await file.read()
    try:
        data = extract_guest_data_from_image(contents, file.content_type)
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore scansione documento: {str(e)}")