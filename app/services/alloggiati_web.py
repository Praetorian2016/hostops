from datetime import datetime
from typing import List, Dict, Any

def pad_field(val: Any, length: int, align_left: bool = True) -> str:
    """Formatta un campo a lunghezza fissa troncando o riempiendo con spazi."""
    s = str(val if val is not None else "")
    if len(s) > length:
        return s[:length]
    return s.ljust(length) if align_left else s.rjust(length)

def format_date_alloggiati(date_val: Any) -> str:
    """Formatta la data nel formato GG/MM/AAAA richiesto dalla Polizia."""
    if not date_val:
        return " " * 10
    if isinstance(date_val, str):
        # Supporta sia formati YYYY-MM-DD che ISO
        try:
            d = datetime.strptime(date_val[:10], "%Y-%m-%d")
            return d.strftime("%d/%m/%Y")
        except ValueError:
            return pad_field(date_val, 10)
    elif hasattr(date_val, "strftime"):
        return date_val.strftime("%d/%m/%Y")
    return " " * 10

def generate_alloggiati_row(guest: Dict[str, Any], booking: Dict[str, Any]) -> str:
    """
    Genera un singolo record a larghezza fissa (tracciato standard Alloggiati Web).
    I campi principali includono:
    - Tipo alloggiato (2 car.)
    - Data arrivo (10 car. GG/MM/AAAA)
    - Numero giorni permanenza (2 car.)
    - Cognome (50 car.)
    - Nome (30 car.)
    - Sesso (1 car.: 1 Maschio, 2 Femmina)
    - Data nascita (10 car. GG/MM/AAAA)
    - Comune/Stato nascita (9 car. codice ISTAT/Belfiore)
    - Cittadinanza (9 car. codice ISTAT)
    - Tipo documento (5 car. es. IDENT, PASSP)
    - Numero documento (20 car.)
    - Luogo rilascio documento (9 car.)
    """
    row = ""
    # 1. Tipo alloggiato (16: Singolo, 17: Capofamiglia, 18: Capogruppo, 19: Membro)
    row += pad_field(guest.get("guest_type", 16), 2, align_left=False)
    
    # 2. Data di arrivo
    row += format_date_alloggiati(booking.get("check_in"))
    
    # 3. Permanenza in notti (2 cifre numeriche)
    nights = min(int(booking.get("nights", 1)), 30)
    row += str(nights).zfill(2)
    
    # 4. Cognome e Nome
    row += pad_field(guest.get("last_name", "").upper(), 50)
    row += pad_field(guest.get("first_name", "").upper(), 30)
    
    # 5. Sesso (1 o 2)
    gender = "1" if str(guest.get("gender")) in ["1", "M", "m"] else "2"
    row += gender
    
    # 6. Data di nascita
    row += format_date_alloggiati(guest.get("birth_date"))
    
    # 7. Comune o Stato estero di nascita (Codice ISTAT/Belfiore a 9 caratteri)
    row += pad_field(guest.get("birth_place_code", ""), 9)
    
    # 8. Cittadinanza (Codice ISTAT a 9 caratteri)
    row += pad_field(guest.get("citizenship_code", "100000100"), 9)
    
    # 9. Dati documento (obbligatori per Capofamiglia, Singolo, Capogruppo)
    is_principal = int(guest.get("guest_type", 16)) in [16, 17, 18]
    if is_principal:
        row += pad_field(guest.get("doc_type", "IDENT"), 5)
        row += pad_field(guest.get("doc_number", ""), 20)
        row += pad_field(guest.get("doc_issuer_place", ""), 9)
    else:
        row += " " * (5 + 20 + 9)
        
    return row

def export_booking_to_txt(booking: Dict[str, Any], guests: List[Dict[str, Any]]) -> str:
    """Esporta tutti gli ospiti collegati a una prenotazione in blocco .txt."""
    lines = []
    for g in guests:
        lines.append(generate_alloggiati_row(g, booking))
    return "\r\n".join(lines) + "\r\n"