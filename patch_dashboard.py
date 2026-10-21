import re

path = "app/templates/dashboard.html"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Pulsante ROSS 1000 da inserire
btn_ross_header = '''                <!-- Export ROSS 1000 Lazio (ISTAT) -->
                <a href="/dashboard/export/ross1000?property_id={{ property.id }}" 
                   class="btn btn-ross1000"
                   title="Scarica il file .csv per ROSS 1000 Lazio / ISTAT">
                    &#128202; Scarica ROSS 1000 (.csv)
                </a>\n'''

btn_ross_panel = '''                    <a href="/dashboard/export/ross1000?property_id={{ property.id }}" class="btn btn-ross1000" style="padding: 6px 12px; font-size: 0.8rem;">
                        &#128202; Scarica ROSS 1000 (ISTAT)
                    </a>\n'''

# Inserimento nel blocco header se non presente
if "export/ross1000" not in content:
    content = content.replace(
        '<a href="/dashboard/export/alloggiati-web',
        btn_ross_panel + '<a href="/dashboard/export/alloggiati-web'
    )
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("FILE AGGIORNATO CON SUCCESSO!")
else:
    print("IL FILE ERA GIA STATO AGGIORNATO!")