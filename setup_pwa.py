import os
import base64
from pathlib import Path

# 1. Creazione cartelle
static_dir = Path("app/static")
icons_dir = static_dir / "icons"
icons_dir.mkdir(parents=True, exist_ok=True)

# 2. Creazione manifest.json
manifest_content = '''{
  "name": "HostOps - Property Management",
  "short_name": "HostOps",
  "description": "Gestionale per Host: Alloggiati Web, ROSS 1000 e Imposta di Soggiorno",
  "start_url": "/dashboard",
  "display": "standalone",
  "background_color": "#0b0f19",
  "theme_color": "#0b0f19",
  "orientation": "portrait-primary",
  "icons": [
    {
      "src": "/static/icons/icon-192.png",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any maskable"
    },
    {
      "src": "/static/icons/icon-512.png",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any maskable"
    }
  ]
}'''

with open(static_dir / "manifest.json", "w", encoding="utf-8") as f:
    f.write(manifest_content.strip())
print(" -> manifest.json creato")

# 3. Creazione service-worker.js
sw_content = '''const CACHE_NAME = 'hostops-pwa-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(clients.claim());
});

self.addEventListener('fetch', (event) => {
  // Strategia network-first per avere sempre i dati aggiornati
  event.respondWith(
    fetch(event.request).catch(() => caches.match(event.request))
  );
});
'''

with open(static_dir / "service-worker.js", "w", encoding="utf-8") as f:
    f.write(sw_content.strip())
print(" -> service-worker.js creato")

# 4. Generazione icone di default PNG (SVG convertito o PNG binario minimale con tema HostOps)
# Creiamo un file SVG scalabile che funge da logo brand
svg_icon = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="100%" height="100%">
  <rect width="512" height="512" rx="100" fill="#0b0f19"/>
  <rect x="20" y="20" width="472" height="472" rx="90" fill="none" stroke="#3b82f6" stroke-width="12" stroke-opacity="0.4"/>
  <text x="50%" y="42%" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-weight="900" font-size="140">HOST</text>
  <text x="50%" y="68%" text-anchor="middle" fill="#3b82f6" font-family="Arial, sans-serif" font-weight="900" font-size="120">OPS</text>
</svg>'''

with open(icons_dir / "icon.svg", "w", encoding="utf-8") as f:
    f.write(svg_icon)

# Proviamo a usare Pillow se presente per generare PNG reali 192 e 512, altrimenti creiamo PNG minimali
try:
    from PIL import Image, ImageDraw, ImageFont
    for size in [192, 512]:
        img = Image.new("RGBA", (size, size), "#0b0f19")
        draw = ImageDraw.Draw(img)
        # Bordo blu arrotondato
        draw.rounded_rectangle([8, 8, size-8, size-8], radius=int(size*0.18), outline="#3b82f6", width=int(size*0.03))
        # Testo centrato HO
        font_size = int(size * 0.42)
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except Exception:
            font = ImageFont.load_default()
        draw.text((size // 2, size // 2), "HO", fill="#3b82f6", anchor="mm", font=font)
        img.save(icons_dir / f"icon-{size}.png")
    print(" -> Icone PNG 192x192 e 512x512 create con Pillow")
except ImportError:
    # PNG binario 1x1 fallback trasparente per non bloccare
    fallback_png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")
    for size in [192, 512]:
        with open(icons_dir / f"icon-{size}.png", "wb") as f:
            f.write(fallback_png)
    print(" -> Icone PNG di fallback create (Pillow non installato)")

# 5. Inietta meta tag e script PWA in app/templates/dashboard.html se non ancora presenti
dash_path = Path("app/templates/dashboard.html")
if dash_path.exists():
    content = dash_path.read_text(encoding="utf-8")
    pwa_tags = '''    <!-- PWA Settings -->
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#0b0f19">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HostOps">
    <link rel="apple-touch-icon" href="/static/icons/icon-192.png">
'''
    sw_script = '''    <!-- PWA Service Worker Registration -->
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/service-worker.js')
                    .then(reg => console.log('HostOps PWA registrata'))
                    .catch(err => console.error('Errore SW:', err));
            });
        }
    </script>
</body>'''

    if '<link rel="manifest"' not in content:
        content = content.replace("</head>", pwa_tags + "</head>")
        content = content.replace("</body>", sw_script)
        dash_path.write_text(content, encoding="utf-8")
        print(" -> PWA registrata dentro app/templates/dashboard.html")
    else:
        print(" -> dashboard.html contiene già i tag PWA")

print("\nSETUP PWA COMPLETATO!")