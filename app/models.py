import sqlite3
from pathlib import Path

# Percorso assoluto al database SQLite nella cartella /data
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "hostops.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Tabella Prenotazioni e Controllo Margini (P&L)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        guest_name TEXT NOT NULL,
        channel TEXT NOT NULL,               -- Airbnb, Booking, Diretto
        check_in DATE NOT NULL,
        check_out DATE NOT NULL,
        nights INTEGER NOT NULL,
        guests_count INTEGER NOT NULL,
        gross_revenue REAL NOT NULL,         -- Incasso lordo totale
        ota_commission REAL DEFAULT 0.0,     -- Commissione portale
        cleaning_cost REAL DEFAULT 0.0,      -- Costo pulizia/lavanderia
        linen_kit_cost REAL DEFAULT 0.0,     -- Noleggio/cambio kit biancheria
        utilities_est REAL DEFAULT 0.0,      -- Quota forfettaria utenze
        net_profit REAL DEFAULT 0.0,         -- Utile netto effettivo
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Tabella Ospiti (Dati Alloggiati Web, Selfie e Documenti)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS guests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        guest_type INTEGER NOT NULL,         -- 16: Singolo, 17: Capofamiglia, 18: Capogruppo, 19: Ospite aggregato
        last_name TEXT NOT NULL,
        first_name TEXT NOT NULL,
        gender TEXT NOT NULL,                -- 1: Maschio, 2: Femmina
        birth_date DATE NOT NULL,            -- Formato YYYY-MM-DD
        birth_place_code TEXT NOT NULL,      -- Codice comune ISTAT o stato estero
        citizenship_code TEXT NOT NULL,      -- Codice ISTAT cittadinanza
        doc_type TEXT,                       -- IDENT, PASSP, PATEN
        doc_number TEXT,
        doc_issuer_place TEXT,
        doc_image_path TEXT,
        selfie_image_path TEXT,
        alloggiati_status TEXT DEFAULT 'PENDING', -- PENDING, GENERATED, SENT
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    );
    """)

    # Tabella Tassa di Soggiorno
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tourist_tax (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id INTEGER NOT NULL,
        chargeable_nights INTEGER NOT NULL,  -- Notti soggette a imposta (fino al massimale)
        rate_per_night REAL NOT NULL,        -- Tariffa per notte a persona
        total_tax REAL NOT NULL,             -- Totale imposta dovuta
        is_paid BOOLEAN DEFAULT 0,
        FOREIGN KEY (booking_id) REFERENCES bookings(id) ON DELETE CASCADE
    );
    """)

    # Tabella Feed iCal Remoti (Airbnb, Booking, ecc.)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ical_feeds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_name TEXT NOT NULL,
            feed_url TEXT NOT NULL,
            last_synced TEXT
        )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
    print("Database inizializzato con successo in:", DB_PATH)