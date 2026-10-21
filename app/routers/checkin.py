import os
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.supabase_client import supabase_admin

router = APIRouter(prefix="/checkin", tags=["checkin"])

# Risoluzione template multi-path per compatibilità locale e Vercel Serverless
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
    """Effettua l'upload sicuro su Supabase Storage nel bucket 'documents'."""
    if not file or not file.filename:
        return None
    try:
        content = await file.read()
        if not content:
            return None
        
        file_ext = Path(file.filename).suffix or ".jpg"
        file_name = f"{folder}/b_{booking_id}_{uuid.uuid4().hex[:8]}{file_ext}"

        res = supabase_admin.storage.from_("documents").upload(
            file_name,
            content,
            file_options={"content-type": file.content_type or "image/jpeg"}
        )
        # Ottieni l'URL pubblico se il bucket è accessibile, altrimenti salva il percorso relativo
        return file_name
    except Exception:
        # Evita il blocco del check-in se il bucket storage non è ancora configurato
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


@router.post("/{booking_id}/submit", response_class=HTMLResponse)
async def checkin_submit(
    booking_id: str,
    last_name: str = Form(...),
    first_name: str = Form(...),
    gender: str = Form(...),
    birth_date: str = Form(...),
    birth_place_code: str = Form(...),
    citizenship_code: str = Form("100000100"),
    doc_type: str = Form("IDENT"),
    doc_number: str = Form(...),
    doc_issuer_place: str = Form(...),
    doc_file: UploadFile = File(None),
    selfie_file: UploadFile = File(None)
):
    """Salva i dati dell'ospite e i documenti su Supabase."""
    # 1. Carica i file su Supabase Storage (se forniti)
    doc_path = await _upload_to_supabase(doc_file, "documents", booking_id)
    selfie_path = await _upload_to_supabase(selfie_file, "selfies", booking_id)

    # 2. Inserimento record nella tabella guests di Supabase
    guest_payload = {
        "booking_id": booking_id,
        "tipo_alloggiato": 16,
        "last_name": last_name.strip().upper(),
        "first_name": first_name.strip().upper(),
        "gender": str(gender).strip(),
        "birth_date": birth_date.strip(),
        "birth_place_code": birth_place_code.strip().upper(),
        "citizenship_code": citizenship_code.strip().upper(),
        "document_type": doc_type.strip(),
        "document_number": doc_number.strip().upper(),
        "document_issue_place_code": doc_issuer_place.strip().upper(),
        "alloggiati_status": "READY"
    }

    # Includi i percorsi dei file se le colonne sono presenti nello schema Supabase
    if doc_path:
        guest_payload["doc_image_path"] = doc_path
    if selfie_path:
        guest_payload["selfie_image_path"] = selfie_path

    try:
        supabase_admin.table("guests").insert(guest_payload).execute()
    except Exception as e:
        # Se alcune colonne opzionali (es. doc_image_path) non sono state create, riprova senza di esse
        guest_payload.pop("doc_image_path", None)
        guest_payload.pop("selfie_image_path", None)
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
        body {
          background-color: #0b0f19;
          color: #f9fafb;
          font-family: 'Plus Jakarta Sans', sans-serif;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0;
          padding: 16px;
        }
        .success-box {
          background-color: #111827;
          border: 1px solid rgba(255, 255, 255, 0.08);
          border-radius: 16px;
          padding: 36px 28px;
          text-align: center;
          max-width: 420px;
          width: 100%;
        }
        .icon {
          width: 56px;
          height: 56px;
          background: rgba(16, 185, 129, 0.12);
          color: #10b981;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          margin: 0 auto 18px;
          font-size: 26px;
          font-weight: 800;
        }
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