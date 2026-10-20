import os
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_client, Client

# Trova la cartella principale HostProject a partire dalla posizione di questo file
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError(f"Credenziali Supabase non trovate. Controllato percorso: {BASE_DIR / '.env'}")

# Client standard (rispetta le policy RLS)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Client amministrativo (per bypassare RLS e operazioni di backend)
supabase_admin: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)