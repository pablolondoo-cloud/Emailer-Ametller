"""
Script de debug - toma screenshot y HTML de la página de login
para identificar los selectores correctos
"""

import os
import asyncio
import base64
from playwright.async_api import async_playwright

PORTAL_EMAIL    = os.environ["PORTAL_EMAIL"]
PORTAL_PASSWORD = os.environ["PORTAL_PASSWORD"]
PORTAL_URL      = "https://control.instaleap.io"

async def debug_login():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        print("📄 Cargando portal...")
        await page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)

        # Screenshot 1 - página inicial
        await page.screenshot(path="screenshot_01_inicio.png", full_page=True)
        print("📸 Screenshot 1 guardado")

        # Dump HTML
        html = await page.content()
        with open("page_01_inicio.html", "w") as f:
            f.write(html)
        print("📝 HTML 1 guardado")

        # Mostrar todos los inputs visibles
        inputs = await page.query_selector_all("input")
        print(f"\n🔍 Inputs encontrados: {len(inputs)}")
        for i, inp in enumerate(inputs):
            inp_type  = await inp.get_attribute("type") or "?"
            inp_name  = await inp.get_attribute("name") or "?"
            inp_placeholder = await inp.get_attribute("placeholder") or "?"
            inp_id    = await inp.get_attribute("id") or "?"
            inp_class = await inp.get_attribute("class") or "?"
            print(f"  [{i}] type={inp_type} name={inp_name} id={inp_id} placeholder={inp_placeholder}")

        # Mostrar todos los botones
        buttons = await page.query_selector_all("button")
        print(f"\n🔍 Botones encontrados: {len(buttons)}")
        for i, btn in enumerate(buttons):
            text = await btn.inner_text()
            btn_type = await btn.get_attribute("type") or "?"
            print(f"  [{i}] type={btn_type} text='{text[:50]}'")

        # URL actual
        print(f"\n🌐 URL actual: {page.url}")

        await browser.close()
        print("\n✅ Debug completado")

if __name__ == "__main__":
    asyncio.run(debug_login())
