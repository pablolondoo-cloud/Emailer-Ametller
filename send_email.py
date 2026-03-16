"""
send_email.py — Envía el Excel generado por fetch_routes.py por Gmail
"""

import os
import glob
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from datetime import datetime, timezone, timedelta

GMAIL_USER     = os.environ["GMAIL_USER"]       # tu_cuenta@gmail.com
GMAIL_APP_PASS = os.environ["GMAIL_APP_PASS"]   # App Password de 16 caracteres
EMAIL_TO_RAW   = os.environ["EMAIL_TO"]         # "a@x.com,b@x.com,c@x.com"

recipients = [e.strip() for e in EMAIL_TO_RAW.split(",") if e.strip()]

today_str = datetime.now(timezone(timedelta(hours=1))).strftime("%d/%m/%Y")
today_file = datetime.now(timezone(timedelta(hours=1))).strftime("%Y-%m-%d")

# Busca el Excel generado por fetch_routes.py
files = glob.glob(f"rutas_{today_file}.xlsx")
if not files:
    print("⚠️  No se encontró ningún Excel para adjuntar. Abortando envío.")
    exit(0)

excel_path = files[0]
excel_name = os.path.basename(excel_path)

# ── Construir el email ──────────────────────────────────────────────────────
msg = MIMEMultipart()
msg["From"]    = GMAIL_USER
msg["To"]      = ", ".join(recipients)
msg["Subject"] = f"📦 Rutas del día - Ametller Origen ({today_str})"

body = f"""Hola,

Adjunto encontraréis el Excel con las rutas de entrega del día {today_str}.

El archivo incluye:
  • Número de ruta
  • Número de pedido (job_number)
  • Posición en la ruta (stop)
  • Ventana de entrega (desde / hasta)

Este email es generado automáticamente cada día a las 20:00h.

Saludos,
Sistema de automatización - Ametller Origen
"""

msg.attach(MIMEText(body, "plain"))

# ── Adjuntar el Excel ───────────────────────────────────────────────────────
with open(excel_path, "rb") as f:
    part = MIMEBase("application", "octet-stream")
    part.set_payload(f.read())

encoders.encode_base64(part)
part.add_header("Content-Disposition", f'attachment; filename="{excel_name}"')
msg.attach(part)

# ── Enviar via Gmail SMTP ───────────────────────────────────────────────────
print(f"📧 Enviando email a: {', '.join(recipients)}")
with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
    server.login(GMAIL_USER, GMAIL_APP_PASS)
    server.sendmail(GMAIL_USER, recipients, msg.as_string())

print("✅ Email enviado correctamente")
