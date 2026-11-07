import asyncio, sys
from playwright.async_api import async_playwright
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/usr/bin/google-chrome", headless=True,
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        pg = await b.new_page(viewport={"width": 1440, "height": 860})
        logs = []
        pg.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        pg.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        await pg.goto("http://localhost:8766/index.html")
        await asyncio.sleep(25)
        await pg.screenshot(path="/tmp/g_start.png")
        await pg.mouse.move(720, 330); await asyncio.sleep(1.5)
        await pg.screenshot(path="/tmp/g_hover.png")
        await pg.mouse.click(860, 470); await asyncio.sleep(4)
        await pg.screenshot(path="/tmp/g_moved.png")
        print("\n".join(l for l in logs if "GPU stall" not in l)[-3000:])
        pg2 = await b.new_page(viewport={"width": 1440, "height": 860})
        logs2 = []
        pg2.on("console", lambda m: logs2.append(f"{m.text}"))
        await pg2.goto("http://localhost:8766/autotest.html")
        shots = 0
        for t in range(60):
            await asyncio.sleep(5)
            txt = "\n".join(logs2)
            if ("now on L3" in txt and shots == 0) or ("stop chewing" in txt and shots == 1) or ("round 2" in txt and shots == 2) or ("pipe fixed" in txt and shots == 3):
                await pg2.screenshot(path=f"/tmp/g_auto{shots}.png"); shots += 1
            if "AUTOTEST end" in txt: break
        print("---- autotest log")
        print("\n".join(l for l in logs2 if "GPU stall" not in l)[-2500:])
        await b.close()
asyncio.run(main())
