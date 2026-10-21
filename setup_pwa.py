from pathlib import Path

dash_path = Path("app/templates/dashboard.html")

if dash_path.exists():
    content = dash_path.read_text(encoding="utf-8")

    pwa_tags = """    <!-- PWA Settings -->
    <link rel="manifest" href="/static/manifest.json">
    <meta name="theme-color" content="#0b0f19">
    <meta name="mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
    <meta name="apple-mobile-web-app-title" content="HostOps">
    <link rel="apple-touch-icon" href="/static/icons/icon-192.png">
"""

    sw_script = """    <!-- PWA Service Worker Registration -->
    <script>
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/static/service-worker.js')
                    .then(reg => console.log('HostOps PWA registrata'))
                    .catch(err => console.error('Errore SW:', err));
            });
        }
    </script>
</body>"""

    if "manifest.json" not in content:
        content = content.replace("</head>", pwa_tags + "</head>")
        content = content.replace("</body>", sw_script)
        dash_path.write_text(content, encoding="utf-8")
        print("PWA registrata con successo dentro app/templates/dashboard.html")
    else:
        print("dashboard.html contiene già i riferimenti PWA")
else:
    print("Percorso app/templates/dashboard.html non trovato")