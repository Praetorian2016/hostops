import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

from app.models import init_db
from app.routers import checkin, dashboard, calendar_view, receipts, auth
from app.routers.auth import templates
from app.services.calendar_sync import sync_external_ical_feeds

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

# Percorso base assoluto del progetto
BASE_DIR = Path(__file__).resolve().parent.parent

# Monta 'static' se la cartella esiste
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Gestione directory 'uploads' (read-only filesystem bypass per Vercel)
if os.getenv("VERCEL"):
    uploads_dir = Path("/tmp/uploads")
else:
    uploads_dir = BASE_DIR / "uploads"

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

# Endpoint manuale/cron per la sincronizzazione calendari
@app.get("/api/sync-ical")
async def trigger_ical_sync():
    imported = await sync_external_ical_feeds()
    return {"status": "success", "imported": imported}

# O "/dashboard", a seconda del tuo flusso
@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})