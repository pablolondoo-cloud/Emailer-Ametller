"""
send_email.py — Envía los Excel de MAÑANA (2 tiendas) por Gmail
"""

import os
import time
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime, timezone, timedelta

GMAIL_USER     = os.environ["GMAIL_USER"]
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]
EMAIL_TO_RAW   = os.environ["EMAIL_TO"]

# ── Múltiples destinatarios separados por coma ───────────────
recipients = [e.strip() for e in EMAIL_TO_RAW.split(",") if e.strip()]

madrid   = timezone(timedelta(hours=1))
tomorrow = (datetime.now(madrid) + timedelta(days=1)).date()
tomorrow_display = tomorrow.strftime("%d/%m/%Y")
tomorrow_file    = tomorrow.strftime("%Y-%m-%d")

STORES = ["ElPrat", "Garraf"]

# ── Buscar los Excel de mañana ───────────────────────────────
files_to_attach = []
summary_lines   = []

for store in STORES:
    filename = f"rutas_{store}_{tomorrow_file}.xlsx"
    if os.path.exists(filename):
        files_to_attach.append(filename)
        summary_lines.append(f"  * [{store}] MAÑANA ({tomorrow_display}): {filename}")
        print(f"📎 Adjuntando: {filename}")
    else:
        summary_lines.append(f"  * [{store}] MAÑANA ({tomorrow_display}): sin rutas")
        print(f"⚠️  No encontrado: {filename}")

if not files_to_attach:
    print("⚠️  No hay archivos para adjuntar. Abortando envío.")
    exit(0)

# ── Construir email ──────────────────────────────────────────
msg = MIMEMultipart()
msg["From"]    = GMAIL_USER
msg["To"]      = ", ".join(recipients)

# ✅ Message-ID único con timestamp para evitar que se agrupe como respuesta
unique_id = f"{int(time.time())}.ametller@automatizacion"
msg["Message-ID"] = f"<{unique_id}>"

msg["Subject"] = f"📦 Rutas de entrega {tomorrow_display} - Ametller Origen"

body = f"""Hola,

Adjunto encontraréis los Excel con las rutas de entrega de mañana para ambas tiendas. Es importante que imprimamos esto para dejarlo en las cajas azules en el piso y que el picker sepa donde va cada posición, además que el picker lo enganche a la bolsa al parquear el pedido, para facilidad del consolidador y del driver.

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
