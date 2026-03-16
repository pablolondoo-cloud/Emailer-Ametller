"""
RPA - Ametller Origen: Extracción de rutas diarias → Excel
Hace login con Playwright e intercepta la RESPUESTA de la llamada que
el propio portal hace a /nebula/routing al cargar la página de rutas.
"""

import os
import json
import asyncio
from datetime import datetime, timezone, timedelta
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from playwright.async_api import async_playwright, Route

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
# 1. LOGIN + INTERCEPTAR RESPUESTA DE LA API
# ─────────────────────────────────────────────
async def fetch_routes_from_browser() -> list:
    print("🔐 Iniciando login con Playwright...")
    all_routes   = []
    captured     = asyncio.Event()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # ── Interceptar la RESPUESTA de /nebula/routing ──
        async def handle_response(response):
            if "nebula/routing" in response.url and response.status == 200:
                try:
                    data   = await response.json()
                    routes = data.get("routes", [])
                    all_routes.extend(routes)
                    print(f"✅ Interceptada respuesta: {len(routes)} rutas (total_pages={data.get('total_pages',1)})")
                    captured.set()
                except Exception as e:
                    print(f"⚠️  Error parseando respuesta: {e}")

        page.on("response", handle_response)

        # ── Cargar portal ──
        await page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)
        print("📄 Portal cargado")
        await page.wait_for_timeout(2000)

        # ── Email ──
        await page.wait_for_selector('#email', timeout=15000)
        await page.fill('#email', PORTAL_EMAIL)
        print("✉️  Email introducido")
        await page.click('button:has-text("Continue")')
        print("▶️  Continue pulsado")

        # ── Password ──
        await page.wait_for_selector('input[type="password"]', timeout=15000)
        await page.fill('input[type="password"]', PORTAL_PASSWORD)
        print("🔑 Contraseña introducida")
        await page.click('button[type="submit"], button:has-text("Log in"), button:has-text("Continue"), button:has-text("Sign in")')
        print("▶️  Submit pulsado")

        # ── Esperar dashboard ──
        await page.wait_for_url("**/routes**", timeout=30000)
        print("✅ Login exitoso, dashboard cargado")
        await page.wait_for_timeout(4000)

        # ── Si no se capturó aún, navegar a la URL de rutas del día ──
        if not captured.is_set():
            print("🔄 Navegando a rutas para forzar llamada a la API...")
            madrid     = timezone(timedelta(hours=1))
            today      = datetime.now(madrid).date()
            routes_url = (
                f"{PORTAL_URL}/routes"
                f"?storeId={STORE_ID}"
                f"&date={today}"
                f"&status=CREATED,ON_BOARDING,PROCESSING"
            )
            await page.goto(routes_url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(5000)

        # ── Esperar captura (máximo 15s) ──
        try:
            await asyncio.wait_for(captured.wait(), timeout=15)
        except asyncio.TimeoutError:
            print("⚠️  Timeout esperando respuesta de la API")

        await browser.close()

    print(f"✅ Total rutas capturadas: {len(all_routes)}")
    return all_routes


# ─────────────────────────────────────────────
# 2. GENERAR EXCEL
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

    col_headers = ["Route Number", "Job Number", "Stop", "Delivery From", "Delivery To"]
    col_widths  = [28, 28, 8, 22, 22]

    for col, (h, w) in enumerate(zip(col_headers, col_widths), 1):
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

    routes = await fetch_routes_from_browser()

    if not routes:
        print("⚠️  No hay rutas para hoy. No se genera Excel.")
    else:
        generate_excel(routes, output)
        print(f"📊 Archivo listo: {output}")


if __name__ == "__main__":
    asyncio.run(main())
