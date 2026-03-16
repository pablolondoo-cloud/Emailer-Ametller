"""
RPA - Ametller Origen: Extracción de rutas diarias → Excel
Usa Playwright para hacer login y luego intercepta la llamada real a la API
para capturar los headers exactos que usa el navegador.
"""

import os
import json
import asyncio
import requests
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from playwright.async_api import async_playwright

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
PORTAL_EMAIL    = os.environ["PORTAL_EMAIL"]
PORTAL_PASSWORD = os.environ["PORTAL_PASSWORD"]

PORTAL_URL = "https://control.instaleap.io"
STORE_ID   = "70fcffac-e7de-44ca-845b-f316fd5b874e"
CLIENT_ID  = "AMETLLER_ORIGEN"
STATES     = ["CREATED", "ON_BOARDING", "PROCESSING"]
API_BASE   = "https://avt-backend.instaleap.io/nebula/routing"


# ─────────────────────────────────────────────
# 1. LOGIN + CAPTURAR HEADERS REALES de la API
# ─────────────────────────────────────────────
async def get_auth_headers() -> dict:
    print("🔐 Iniciando login con Playwright...")
    captured_headers = {}

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Interceptar requests a avt-backend para capturar los headers
        async def intercept_request(request):
            if "avt-backend.instaleap.io" in request.url and not captured_headers:
                hdrs = request.headers
                # Guardar todos los headers relevantes
                for key in ["authorization", "cookie", "x-session-token", "x-auth-token", "x-token"]:
                    if key in hdrs:
                        captured_headers[key] = hdrs[key]
                        print(f"✅ Header capturado: {key} = {hdrs[key][:60]}...")
                # Guardar también headers genéricos útiles
                captured_headers["_all"] = dict(hdrs)
                print(f"📋 Todos los headers de avt-backend capturados ({len(hdrs)} headers)")

        page.on("request", intercept_request)

        # Ir al portal
        await page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)
        print("📄 Portal cargado")

        # Esperar campo email
        await page.wait_for_selector('input[type="email"], input[name="email"]', timeout=15000)
        await page.fill('input[type="email"], input[name="email"]', PORTAL_EMAIL)
        print("✉️  Email introducido")
        await page.keyboard.press("Enter")

        # Esperar campo password
        await page.wait_for_selector('input[type="password"]', timeout=15000)
        await page.fill('input[type="password"]', PORTAL_PASSWORD)
        print("🔑 Contraseña introducida")
        await page.keyboard.press("Enter")

        # Esperar dashboard
        await page.wait_for_url("**/routes**", timeout=30000)
        print("✅ Login exitoso")

        # Esperar a que se haga la llamada a nebula/routing automáticamente
        # (el dashboard la hace al cargar)
        await page.wait_for_timeout(5000)

        # Si no se capturó todavía, navegar a la URL de rutas para forzar la llamada
        if not captured_headers:
            print("🔄 Navegando a rutas para forzar llamada a la API...")
            madrid = timezone(timedelta(hours=1))
            today  = datetime.now(madrid).date()
            routes_url = (
                f"{PORTAL_URL}/routes"
                f"?storeId={STORE_ID}"
                f"&date={today}"
                f"&status=CREATED,ON_BOARDING,PROCESSING"
            )
            await page.goto(routes_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

        await browser.close()

    if not captured_headers:
        raise Exception("❌ No se pudieron capturar los headers de autenticación")

    return captured_headers


# ─────────────────────────────────────────────
# 2. LLAMADA A LA API con los headers capturados
# ─────────────────────────────────────────────
def get_routes(auth_headers: dict) -> list:
    madrid   = timezone(timedelta(hours=1))
    today    = datetime.now(madrid).date()
    from_dt  = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=madrid)
    to_dt    = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=madrid)
    from_str = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    to_str   = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.999Z")

    # Usar los headers reales capturados del navegador
    headers = auth_headers.get("_all", {})
    # Asegurar headers mínimos necesarios
    headers.update({
        "accept":       "application/json",
        "content-type": "application/json",
        "origin":       "https://control.instaleap.io",
        "referer":      "https://control.instaleap.io/",
    })
    # Eliminar headers que pueden causar problemas en requests
    for h in [":authority", ":method", ":path", ":scheme",
              "content-length", "if-none-match"]:
        headers.pop(h, None)

    all_routes = []
    limit  = 50
    offset = 0

    while True:
        params = (
            f"store_id={STORE_ID}"
            f"&client_id={CLIENT_ID}"
            f"&limit={limit}"
            f"&offset={offset}"
            f"&from={from_str}"
            f"&to={to_str}"
        )
        for s in STATES:
            params += f"&states[]={s}"

        url = f"{API_BASE}?{params}"
        print(f"📡 Obteniendo rutas offset={offset}...")

        r = requests.get(url, headers=headers, timeout=30)

        if r.status_code == 401:
            print(f"❌ 401 Unauthorized. Headers enviados: {list(headers.keys())}")
            print(f"   Response: {r.text[:300]}")
            raise Exception("Autenticación fallida - 401")

        r.raise_for_status()
        data = r.json()

        routes = data.get("routes", [])
        all_routes.extend(routes)

        total_pages  = data.get("total_pages", 1)
        current_page = (offset // limit) + 1
        if current_page >= total_pages or not routes:
            break
        offset += limit

    print(f"✅ Total rutas: {len(all_routes)}")
    return all_routes


# ─────────────────────────────────────────────
# 3. GENERAR EXCEL
# ─────────────────────────────────────────────
def parse_dt(s: str) -> str:
    dt = datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone(timedelta(hours=1))).strftime("%d/%m/%Y %H:%M")


def generate_excel(routes: list, output_path: str):
    wb = Workbook()
    ws = wb.active
    ws.title = "Routes"

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
        cell.font      = header_font
        cell.fill      = header_fill
        cell.alignment = header_align
        cell.border    = border
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
                cell.font      = Font(name="Arial", size=10)
                cell.fill      = fill
                cell.border    = border
                cell.alignment = Alignment(
                    horizontal="center" if col == 3 else "left",
                    vertical="center"
                )
            row += 1

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:E{row - 1}"
    wb.save(output_path)
    print(f"✅ Excel generado: {output_path} ({row - 2} filas)")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────
async def main():
    madrid    = timezone(timedelta(hours=1))
    today_str = datetime.now(madrid).strftime("%Y-%m-%d")
    output    = f"rutas_{today_str}.xlsx"

    auth_headers = await get_auth_headers()
    routes       = get_routes(auth_headers)

    if not routes:
        print("⚠️  No hay rutas para hoy. No se genera Excel.")
    else:
        generate_excel(routes, output)
        print(f"📊 Archivo listo: {output}")


if __name__ == "__main__":
    asyncio.run(main())
