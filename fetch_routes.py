"""
RPA - Ametller Origen: Extracción de rutas diarias → Excel
Hace login con Playwright y ejecuta la llamada a la API DESDE el propio
navegador (via page.evaluate) para evitar problemas de autenticación.
"""

import os
import json
import asyncio
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
# 1. LOGIN + LLAMAR API DESDE EL NAVEGADOR
# ─────────────────────────────────────────────
async def fetch_routes_from_browser() -> list:
    print("🔐 Iniciando login con Playwright...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Cargar portal
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
        print("✅ Login exitoso")
        await page.wait_for_timeout(4000)

        # ── Construir URL de la API para hoy ──
        madrid   = timezone(timedelta(hours=1))
        today    = datetime.now(madrid).date()
        from_dt  = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=madrid)
        to_dt    = datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=madrid)
        from_str = from_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
        to_str   = to_dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.999Z")

        states_qs = "&".join([f"states[]={s}" for s in STATES])
        api_url = (
            f"{API_BASE}"
            f"?store_id={STORE_ID}"
            f"&client_id={CLIENT_ID}"
            f"&limit=100"
            f"&offset=0"
            f"&from={from_str}"
            f"&to={to_str}"
            f"&{states_qs}"
        )

        print(f"📡 Llamando API desde el navegador...")
        print(f"   URL: {api_url[:100]}...")

        # ── Ejecutar fetch() DESDE el navegador (mismas cookies/auth) ──
        result = await page.evaluate(f"""
            async () => {{
                const response = await fetch("{api_url}", {{
                    method: "GET",
                    headers: {{
                        "accept": "application/json",
                        "content-type": "application/json"
                    }},
                    credentials: "include"
                }});
                const status = response.status;
                const text = await response.text();
                return {{ status, text }};
            }}
        """)

        print(f"   Status: {result['status']}")

        if result['status'] != 200:
            print(f"   Response: {result['text'][:300]}")
            raise Exception(f"API devolvió {result['status']}: {result['text'][:200]}")

        data = json.loads(result['text'])
        routes = data.get("routes", [])
        total_pages = data.get("total_pages", 1)
        print(f"✅ Página 1: {len(routes)} rutas (total_pages={total_pages})")

        # Paginar si hay más páginas
        all_routes = list(routes)
        for page_num in range(1, total_pages):
            offset = page_num * 100
            api_url_page = api_url.replace("offset=0", f"offset={offset}")
            result = await page.evaluate(f"""
                async () => {{
                    const response = await fetch("{api_url_page}", {{
                        method: "GET",
                        headers: {{
                            "accept": "application/json",
                            "content-type": "application/json"
                        }},
                        credentials: "include"
                    }});
                    return {{ status: response.status, text: await response.text() }};
                }}
            """)
            if result['status'] == 200:
                page_data = json.loads(result['text'])
                all_routes.extend(page_data.get("routes", []))
                print(f"✅ Página {page_num+1}: {len(page_data.get('routes',[]))} rutas")

        await browser.close()
        print(f"✅ Total rutas obtenidas: {len(all_routes)}")
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

    routes = await fetch_routes_from_browser()

    if not routes:
        print("⚠️  No hay rutas para hoy. No se genera Excel.")
    else:
        generate_excel(routes, output)
        print(f"📊 Archivo listo: {output}")


if __name__ == "__main__":
    asyncio.run(main())
