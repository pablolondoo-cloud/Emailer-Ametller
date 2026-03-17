"""
Debug script - identifica el contenedor scrolleable de la lista de rutas
y toma screenshots en cada paso
"""

import os
import asyncio
from playwright.async_api import async_playwright

PORTAL_EMAIL    = os.environ["PORTAL_EMAIL"]
PORTAL_PASSWORD = os.environ["PORTAL_PASSWORD"]
PORTAL_URL      = "https://control.instaleap.io"
STORE_ID        = "70fcffac-e7de-44ca-845b-f316fd5b874e"

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900}
        )
        page = await context.new_page()

        # Interceptar para ver cuántas llamadas a routing se hacen
        routing_calls = []
        async def on_response(response):
            if "nebula/routing" in response.url and response.status == 200:
                data = await response.json()
                routing_calls.append({
                    "url": response.url,
                    "routes": len(data.get("routes", [])),
                    "total_pages": data.get("total_pages", 1)
                })
                print(f"  🔔 routing call: {len(data.get('routes',[]))} rutas, total_pages={data.get('total_pages',1)}, url={response.url[-60:]}")
        page.on("response", on_response)

        # Login
        await page.goto(PORTAL_URL, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(2000)
        await page.wait_for_selector('#email', timeout=15000)
        await page.fill('#email', PORTAL_EMAIL)
        await page.click('button:has-text("Continue")')
        await page.wait_for_selector('input[type="password"]', timeout=15000)
        await page.fill('input[type="password"]', PORTAL_PASSWORD)
        await page.click('button[type="submit"], button:has-text("Log in"), button:has-text("Continue")')
        await page.wait_for_url("**/routes**", timeout=30000)
        print("✅ Login OK")
        await page.wait_for_timeout(3000)

        # Navegar a rutas
        from datetime import datetime, timezone, timedelta
        madrid = timezone(timedelta(hours=1))
        today = datetime.now(madrid).date()
        target_url = f"{PORTAL_URL}/routes?storeId={STORE_ID}&date={today}&status=CREATED,ON_BOARDING,PROCESSING"
        await page.goto(target_url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path="scroll_01_initial.png")
        print(f"📸 Screenshot inicial. Routing calls hasta ahora: {len(routing_calls)}")

        # Encontrar todos los elementos scrolleables
        scroll_info = await page.evaluate("""
            () => {
                const elements = document.querySelectorAll('*');
                const scrollables = [];
                for (let el of elements) {
                    const style = window.getComputedStyle(el);
                    const overflow = style.overflow + style.overflowY;
                    if ((overflow.includes('auto') || overflow.includes('scroll')) 
                        && el.scrollHeight > el.clientHeight + 10) {
                        scrollables.push({
                            tag: el.tagName,
                            class: el.className.toString().substring(0, 80),
                            scrollHeight: el.scrollHeight,
                            clientHeight: el.clientHeight,
                            scrollTop: el.scrollTop,
                            id: el.id || ''
                        });
                    }
                }
                return scrollables;
            }
        """)
        print(f"\n📋 Elementos scrolleables encontrados: {len(scroll_info)}")
        for s in scroll_info:
            print(f"  {s['tag']} id='{s['id']}' class='{s['class'][:60]}' scrollH={s['scrollHeight']} clientH={s['clientHeight']}")

        # Intentar scroll en cada elemento scrolleable
        print(f"\n📜 Intentando scroll en cada elemento...")
        for i, s in enumerate(scroll_info):
            prev_calls = len(routing_calls)
            await page.evaluate(f"""
                () => {{
                    const elements = document.querySelectorAll('*');
                    let idx = 0;
                    for (let el of elements) {{
                        const style = window.getComputedStyle(el);
                        const overflow = style.overflow + style.overflowY;
                        if ((overflow.includes('auto') || overflow.includes('scroll')) 
                            && el.scrollHeight > el.clientHeight + 10) {{
                            if (idx === {i}) {{
                                el.scrollTop = el.scrollHeight;
                                return;
                            }}
                            idx++;
                        }}
                    }}
                }}
            """)
            await page.wait_for_timeout(2000)
            new_calls = len(routing_calls) - prev_calls
            if new_calls > 0:
                print(f"  ✅ Elemento {i} ({s['tag']} '{s['class'][:40]}') → TRIGGEREÓ {new_calls} nueva(s) llamada(s) a routing!")
            
        await page.wait_for_timeout(3000)
        await page.screenshot(path="scroll_02_after.png")
        print(f"\n📊 Total routing calls: {len(routing_calls)}")
        for c in routing_calls:
            print(f"  {c['url'][-80:]}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(debug())
