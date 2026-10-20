import os
from app.supabase_client import supabase_admin

def seed_supabase():
    email = "armando@test.it"
    password = "PasswordSicura123!"

    print("1. Creazione utente su Supabase Auth...")
    try:
        user_res = supabase_admin.auth.admin.create_user({
            "email": email,
            "password": password,
            "email_confirm": True
        })
        user_id = user_res.user.id
        print(f"Utente creato con ID: {user_id}")
    except Exception as e:
        print(f"Nota utente (potrebbe già esistere): {e}")
        users = supabase_admin.auth.admin.list_users()
        user_id = next((u.id for u in users if u.email == email), None)

    if not user_id:
        print("Errore: impossibile trovare o creare l'utente.")
        return

    print("2. Registrazione struttura 'Praetorian Apartment'...")
    prop_data = {
        "user_id": user_id,
        "name": "Praetorian Apartment",
        "manager_name": "Armando Puccilli",
        "city": "Roma",
        "province": "RM",
        "tax_rate": 6.00,
        "max_taxable_nights": 10
    }
    prop_res = supabase_admin.table("properties").insert(prop_data).execute()
    property_id = prop_res.data[0]["id"]
    print(f"Struttura inserita con ID: {property_id}")

    print("3. Registrazione prenotazione di prova (Marc Dupont)...")
    booking_data = {
        "property_id": property_id,
        "channel": "Booking.com",
        "channel_booking_id": "5",
        "guest_name": "Marc Dupont",
        "check_in": "2026-11-20",
        "check_out": "2026-11-24",
        "adults_count": 1,
        "exempt_count": 0
    }
    booking_res = supabase_admin.table("bookings").insert(booking_data).execute()
    print("Prenotazione inserita con ID:", booking_res.data[0]["id"])
    print("\nDati caricati su Supabase con successo!")

if __name__ == "__main__":
    seed_supabase()