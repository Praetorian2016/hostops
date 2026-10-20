import httpx
from icalendar import Calendar
from datetime import datetime
from app.models import get_db_connection

async def sync_external_ical_feeds():
    """Scarica i calendari remoti e sincronizza le prenotazioni nel DB."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, channel_name, feed_url FROM ical_feeds")
    feeds = cursor.fetchall()

    total_imported = 0

    async with httpx.AsyncClient(timeout=15.0) as client:
        for feed in feeds:
            feed_id = feed["id"]
            channel = feed["channel_name"]
            url = feed["feed_url"]

            try:
                response = await client.get(url)
                if response.status_code != 200:
                    continue

                cal = Calendar.from_ical(response.text)

                for component in cal.walk('VEVENT'):
                    start = component.get('dtstart')
                    end = component.get('dtend')
                    summary = str(component.get('summary', f'Prenotazione {channel}'))

                    if not start or not end:
                        continue

                    check_in_date = start.dt if hasattr(start.dt, 'strftime') else start.dt.date()
                    end_val = end.dt if hasattr(end.dt, 'strftime') else end.dt.date()
                    
                    if isinstance(check_in_date, datetime):
                        check_in_date = check_in_date.date()
                    if isinstance(end_val, datetime):
                        end_val = end_val.date()

                    check_in = check_in_date.strftime("%Y-%m-%d")
                    check_out = end_val.strftime("%Y-%m-%d")
                    nights = (end_val - check_in_date).days

                    if nights <= 0:
                        continue

                    # Controllo duplicati (stesso canale e stesse date)
                    cursor.execute("""
                        SELECT id FROM bookings 
                        WHERE channel = ? AND check_in = ? AND check_out = ?
                    """, (channel, check_in, check_out))
                    existing = cursor.fetchone()

                    if not existing:
                        cursor.execute("""
                            INSERT INTO bookings (
                                guest_name, channel, check_in, check_out, nights,
                                guests_count, gross_revenue, ota_commission, cleaning_cost,
                                linen_kit_cost, utilities_est, net_profit
                            ) VALUES (?, ?, ?, ?, ?, 1, 0, 0, 0, 0, 0, 0)
                        """, (summary, channel, check_in, check_out, nights))
                        total_imported += 1

                # Salva data/ora ultimo sync
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                cursor.execute("UPDATE ical_feeds SET last_synced = ? WHERE id = ?", (now_str, feed_id))

            except Exception as e:
                print(f"Errore sincronizzazione feed {channel}: {e}")

    conn.commit()
    conn.close()
    return total_imported