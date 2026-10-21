import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, FileResponse, Response

from app.models import init_db
from app.routers import checkin, dashboard, calendar_view, receipts, auth
from app.routers.auth import templates
from app.services.calendar_sync import sync_external_ical_feeds
from app.services.document_scanner import extract_guest_data_from_image

# Intervallo in secondi per eventuale worker standalone
SYNC_INTERVAL_SECONDS = 60

async def periodic_calendar_sync():
    """Esegue il sync iCal in background a intervalli ravvicinati."""
    while True:
        try:
            imported = await sync_external_ical_feeds()
            if imported > 0:
                print(f"[iCal Sync] Importate {imported} nuove prenotazioni da canali esterni.")
        except Exception as e:
            print(f"[iCal Sync Errore] {e}")
        
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Inizializzazione db se necessaria
    try:
        init_db()
    except Exception as e:
        print(f"[Init DB] Nota: {e}")
    
    yield
    # Nessun loop bloccante all'avvio in modalità serverless

app = FastAPI(title="HostOps", lifespan=lifespan)

# Percorso base assoluto del file corrente e della root di progetto
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent if CURRENT_DIR.name == "app" else CURRENT_DIR

# Individuazione cartella 'static' (priorità su app/static dove risiedono i file PWA)
static_dir = PROJECT_ROOT / "app" / "static"
if not static_dir.exists():
    static_dir = CURRENT_DIR / "static"
if not static_dir.exists():
    static_dir = PROJECT_ROOT / "static"

if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Gestione directory 'uploads' (read-only filesystem bypass per Vercel)
if os.getenv("VERCEL"):
    uploads_dir = Path("/tmp/uploads")
else:
    uploads_dir = PROJECT_ROOT / "uploads"

try:
    uploads_dir.mkdir(parents=True, exist_ok=True)
except OSError:
    pass

if uploads_dir.exists():
    app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Inclusione router
app.include_router(checkin.router)
app.include_router(dashboard.router)
app.include_router(calendar_view.router)
app.include_router(receipts.router)
app.include_router(auth.router)

# Rotte esplicite per la scansione documenti (sia con prefisso /checkin/api sia diretto /api)
@app.post("/checkin/api/scan-document")
@app.post("/api/scan-document")
async def global_scan_document(file: UploadFile = File(...)):
    try:
        image_bytes = await file.read()
        mime_type = file.content_type or "image/jpeg"
        data = extract_guest_data_from_image(image_bytes, mime_type)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore scansione documento: {str(e)}")

# Gestore Favicon per eliminare l'errore 404 nei log DevTools
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    favicon_path = static_dir / "favicon.ico"
    if favicon_path.exists():
        return FileResponse(favicon_path)
    return Response(status_code=204)

# Endpoint manuale/cron per la sincronizzazione calendari
@app.get("/api/sync-ical")
async def trigger_ical_sync():
    imported = await sync_external_ical_feeds()
    return {"status": "success", "imported": imported}

# Root endpoint
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )