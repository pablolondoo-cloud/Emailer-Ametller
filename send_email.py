"""
send_email.py — Envía los 4 Excel (2 tiendas x 2 días) por Gmail
"""

import os
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime, timezone, timedelta

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
EMAIL_TO_RAW   = os.environ["EMAIL_TO"]

recipients = [e.strip() for e in EMAIL_TO_RAW.split(",") if e.strip()]

madrid   = timezone(timedelta(hours=1))
today    = datetime.now(madrid).date()
tomorrow = today + timedelta(days=1)

STORES = ["ElPrat", "Garraf"]

# ── Buscar todos los Excel generados ─────────────────────────
files_to_attach = []
summary_lines   = []

for store in STORES:
    for date_obj, label in [(today, "HOY"), (tomorrow, "MAÑANA")]:
        filename = f"rutas_{store}_{date_obj.strftime('%Y-%m-%d')}.xlsx"
        if os.path.exists(filename):
            files_to_attach.append(filename)
            summary_lines.append(
                f"  📎 [{store}] {label} ({date_obj.strftime('%d/%m/%Y')}): {filename}"
            )
            print(f"📎 Adjuntando: {filename}")
        else:
            summary_lines.append(
                f"  ⚠️  [{store}] {label} ({date_obj.strftime('%d/%m/%Y')}): sin rutas"
            )
            print(f"⚠️  No encontrado: {filename}")

if not files_to_attach:
    print("⚠️  No hay archivos para adjuntar. Abortando envío.")
    exit(0)

# ── Construir email ──────────────────────────────────────────
msg = MIMEMultipart()
msg["From"]    = GMAIL_USER
msg["To"]      = ", ".join(recipients)
msg["Subject"] = f"📦 Rutas de entrega - Ametller Origen ({today.strftime('%d/%m/%Y')})"

body = f"""Hola,

Adjunto encontraréis los Excel con las rutas de entrega de hoy y mañana para ambas tiendas:

{chr(10).join(summary_lines)}

Cada archivo incluye:
  • Número de ruta
  • Número de pedido (job_number)
  • Posición en la ruta (stop)
  • Ventana de entrega (desde / hasta)

Este email es generado automáticamente cada día a las 20:00h.

Saludos,
Sistema de automatización - Ametller Origen
"""

msg.attach(MIMEText(body, "plain"))

# ── Adjuntar Excel ───────────────────────────────────────────
for filepath in files_to_attach:
    with open(filepath, "rb") as f:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(filepath)}"')
    msg.attach(part)

# ── Enviar ────────────────────────────────────────────────────
print(f"📧 Enviando email a: {', '.join(recipients)}")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_APP_PASS)
    server.sendmail(GMAIL_USER, recipients, msg.as_string())

print(f"✅ Email enviado con {len(files_to_attach)} adjunto(s)")
