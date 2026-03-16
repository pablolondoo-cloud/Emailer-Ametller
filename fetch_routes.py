"""
RPA - Ametller Origen: Extracción de rutas diarias → Excel
Ejecutado por GitHub Actions cada día a las 20:00h (Europe/Madrid)
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─────────────────────────────────────────────
# CONFIG (variables de entorno / GitHub Secrets)
# ─────────────────────────────────────────────
PORTAL_EMAIL    = os.environ["PORTAL_EMAIL"]       # AutomatizacionemailsRutas@instaleap.com
PORTAL_PASSWORD = os.environ["PORTAL_PASSWORD"]    # AutomatizacionemailsRutas1?

STORE_ID  = "70fcffac-e7de-44ca-845b-f316fd5b874e"
CLIENT_ID = "AMETLLER_ORIGEN"
STATES    = ["CREATED", "ON_BOARDING", "PROCESSING"]

LOGIN_URL = "https://avt-backend.instaleap.io/users/login"
API_BASE  = "https://avt-backend.instaleap.io/nebula/routing"


# ─────────────────────────────────────────────
# 1. LOGIN → obtener token JWT
# ─────────────────────────────────────────────
def get_token() -> str:
    print("🔐 Haciendo login...")
    headers = {"Content-Type": "application/json"}
    payload = {"email": PORTAL_EMAIL, "password": PORTAL_PASSWORD}

    r = requests.post(LOGIN_URL, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()

    # Instaleap suele devolver el token en data.token o data.access_token
    token = (
        data.get("token")
        or data.get("access_token")
        or data.get("data", {}).get("token")
        or data.get("data", {}).get("access_token")
    )
    if not token:
        raise ValueError(f"Token no encontrado en la respuesta: {json.dumps(data)[:300]}")

    print("✅ Login correcto")
    return token


# ─────────────────────────────────────────────
# 2. LLAMADA A LA API → obtener todas las rutas del día
# ─────────────────────────────────────────────
def get_routes(token: str) -> list:
    # Rango del día: 23:00 UTC del día anterior → 22:59:59 UTC del día actual
    # (equivale a 00:00–23:59 hora España UTC+1)
    today_utc = datetime.now(timezone.utc).date()
    from_dt = datetime(today_utc.year, today_utc.month, today_utc.day, 0, 0, 0,
                       tzinfo=timezone(timedelta(hours=1)))  # 00:00 Madrid
    to_dt   = datetime(today_utc.year, today_utc.month, today_utc.day, 23, 59, 59,
                       tzinfo=timezone(timedelta(hours=1)))  # 23:59 Madrid

    from_str = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_str   = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.999Z")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    all_routes = []
    limit  = 50
    offset = 0

    while True:
        params = {
            "store_id":  STORE_ID,
            "client_id": CLIENT_ID,
            "limit":     limit,
            "offset":    offset,
            "from":      from_str,
            "to":        to_str,
        }
        for s in STATES:
            params.setdefault("states[]", [])
            if isinstance(params["states[]"], list):
                params["states[]"].append(s)

        print(f"📡 Obteniendo rutas offset={offset}...")
        r = requests.get(API_BASE, params=params, headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        routes = data.get("routes", [])
        all_routes.extend(routes)

        total_pages = data.get("total_pages", 1)
        current_page = (offset // limit) + 1
        if current_page >= total_pages or not routes:
            break
        offset += limit

    print(f"✅ Total rutas obtenidas: {len(all_routes)}")
    return all_routes


# ─────────────────────────────────────────────
# 3. GENERAR EXCEL
# ─────────────────────────────────────────────
def parse_dt(s: str) -> str:
    """Convierte ISO UTC → hora local España (UTC+1)"""
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    local = dt.astimezone(timezone(timedelta(hours=1)))
    return local.strftime("%d/%m/%Y %H:%M")


def generate_excel(routes: list, output_path: str) -> str:
    wb = Workbook()
    ws = wb.active
    ws.title = "Routes"

    # Estilos
    header_fill  = PatternFill("solid", start_color="1F3864", end_color="1F3864")
    header_font  = Font(name="Arial", bold=True, color="FFFFFF", size=11)
    header_align = Alignment(horizontal="center", vertical="center")
    thin         = Side(style="thin", color="CCCCCC")
    border       = Border(left=thin, right=thin, top=thin, bottom=thin)
    fill_light   = PatternFill("solid", start_color="EBF0FA", end_color="EBF0FA")
    fill_white   = PatternFill("solid", start_color="FFFFFF", end_color="FFFFFF")

    headers    = ["Route Number", "Job Number", "Stop", "Delivery From", "Delivery To"]
    col_widths = [28, 28, 8, 22, 22]

    for col, (h, w) in enumerate(zip(headers, col_widths), 1):
        cell = ws.cell(row=1, column=col, value=h)
        cell.font  = header_font
        cell.fill  = header_fill
        cell.alignment = header_align
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.row_dimensions[1].height = 22

    row = 2
    for route in routes:
        route_num = route.get("route_number", "")
        for stop_idx, task in enumerate(route.get("tasks", []), 1):
            fill = fill_light if row % 2 == 0 else fill_white
            values = [
                route_num,
                task.get("job_number", ""),
                stop_idx,
                parse_dt(task["from"]) if task.get("from") else "",
                parse_dt(task["to"])   if task.get("to")   else "",
            ]
            for col, val in enumerate(values, 1):
                cell = ws.cell(row=row, column=col, value=val)
                cell.font  = Font(name="Arial", size=10)
                cell.fill  = fill
                cell.border = border
                cell.alignment = Alignment(
                    horizontal="center" if col == 3 else "left",
                    vertical="center"
                )
            row += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{row - 1}"

    wb.save(output_path)
    print(f"✅ Excel generado: {output_path} ({row - 2} filas)")
    return output_path


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
if __name__ == "__main__":
    today_str = datetime.now(timezone(timedelta(hours=1))).strftime("%Y-%m-%d")
    output    = f"rutas_{today_str}.xlsx"

    token  = get_token()
    routes = get_routes(token)

    if not routes:
        print("⚠️  No se encontraron rutas para hoy. No se genera Excel.")
    else:
        generate_excel(routes, output)
        print(f"📊 Archivo listo: {output}")
