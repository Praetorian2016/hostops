from datetime import datetime

# Parametri standard (es. tariffa per notte a persona e tetto massimo notti imponibili)
DEFAULT_TAX_RATE = 6.0  # € a notte a persona
MAX_TAXABLE_NIGHTS = 10  # Massimo notti imponibili da regolamento locale

def calculate_tourist_tax(nights: int, guests_count: int, rate_per_person: float = DEFAULT_TAX_RATE, max_nights: int = MAX_TAXABLE_NIGHTS) -> dict:
    """
    Calcola l'imposta di soggiorno in base al numero di ospiti paganti e alle notti effettive (rispettando il cap massimo).
    """
    billable_nights = min(nights, max_nights)
    total_tax = billable_nights * guests_count * rate_per_person

    return {
        "rate_per_person": rate_per_person,
        "billable_nights": billable_nights,
        "exempt_nights": max(0, nights - max_nights),
        "total_tax": round(total_tax, 2)
    }