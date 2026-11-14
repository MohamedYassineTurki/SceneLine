"""Enregistre une démonstration réelle de SceneLine dans Chrome (aucune donnée simulée).

Le script pilote l'interface comme un utilisateur : il choisit l'épisode, remplit le contexte,
donne les deux autorisations, lance l'analyse réelle (Gemini), ajoute deux produits au catalogue
à la main, lance l'appariement et accepte un placement. Les images viennent du flux
« screencast » de Chrome ; `scripts/build_demo_video.py` les assemble ensuite en MP4 et GIF.

Usage : .venv/Scripts/python scripts/record_demo.py --url http://127.0.0.1:8002 --video "Assets/BALTRINGUE #1 - LE PATRON_1080p.mp4"
"""
import argparse
import asyncio
import base64
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright

W, H = 1440, 900
CURSOR_JS = """
(() => {
  const make = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.innerHTML = '<svg width="26" height="26" viewBox="0 0 24 24"><path d="M4 2l15 11-6.5 1.2L16 21l-3 1.4-3.4-6.6L4 20z" fill="#1d1d1f" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(c.style, {position:'fixed', left:'0', top:'0', zIndex:2147483647, pointerEvents:'none', transform:'translate(-200px,-200px)', filter:'drop-shadow(0 2px 3px rgba(0,0,0,.25))'});
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.transform = `translate(${e.clientX - 3}px, ${e.clientY - 2}px)`; }, true);
    addEventListener('mousedown', e => {
      const r = document.createElement('div');
      Object.assign(r.style, {position:'fixed', left:(e.clientX-18)+'px', top:(e.clientY-18)+'px', width:'36px', height:'36px', borderRadius:'50%', background:'rgba(0,102,204,.28)', zIndex:2147483646, pointerEvents:'none', transition:'transform .45s ease-out, opacity .45s ease-out'});
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 500);
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', make); else make();
})();
"""


class Recorder:
    def __init__(self, out: Path):
        self.out = out
        self.frames = []          # (timestamp, file)
        self.markers = []         # (timestamp, label)
        self.slow = False         # pendant les longues attentes, 2 images/s suffisent
        self.last = 0.0

    def mark(self, label):
        self.markers.append((time.time(), label))
        print(f"[{time.strftime('%H:%M:%S')}] {label}", flush=True)

    async def attach(self, page):
        self.cdp = await page.context.new_cdp_session(page)
        self.cdp.on("Page.screencastFrame", lambda e: asyncio.ensure_future(self._frame(e)))
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})

    async def _frame(self, e):
        ts = e["metadata"]["timestamp"]
        await self.cdp.send("Page.screencastFrameAck", {"sessionId": e["sessionId"]})
        if ts - self.last < (0.5 if self.slow else 1 / 30):
            return
        self.last = ts
        path = self.out / f"f{len(self.frames):06d}.jpg"
        path.write_bytes(base64.b64decode(e["data"]))
        self.frames.append((ts, path.name))

    def save(self):
        (self.out / "timeline.json").write_text(json.dumps({"frames": self.frames, "markers": self.markers}, ensure_ascii=False), encoding="utf-8")


class Human:
    def __init__(self, page):
        self.page, self.x, self.y = page, W / 2, H / 2

    async def pause(self, s=0.6):
        await asyncio.sleep(s)

    async def show(self, loc):
        await loc.evaluate("el => el.scrollIntoView({behavior: 'smooth', block: 'center'})")
        await asyncio.sleep(0.9)

    async def move(self, loc, dx=0.5, dy=0.5):
        await loc.wait_for(state="visible", timeout=60_000)
        box = await loc.bounding_box()
        if not box or box["y"] < 60 or box["y"] + box["height"] > H - 40:
            await self.show(loc)
            box = await loc.bounding_box()
        tx, ty = box["x"] + box["width"] * dx, box["y"] + box["height"] * dy
        steps = 28
        for i in range(1, steps + 1):
            t = i / steps
            e = t * t * (3 - 2 * t)  # ease in-out
            await self.page.mouse.move(self.x + (tx - self.x) * e, self.y + (ty - self.y) * e)
            await asyncio.sleep(0.012)
        self.x, self.y = tx, ty

    async def click(self, loc, after=0.5, **kw):
        await self.move(loc, **kw)
        await asyncio.sleep(0.15)
        await self.page.mouse.down(); await asyncio.sleep(0.06); await self.page.mouse.up()
        await asyncio.sleep(after)

    async def type(self, loc, text, after=0.35):
        await self.click(loc, after=0.15)
        await self.page.keyboard.type(text, delay=38)
        await asyncio.sleep(after)

    async def scroll(self, pixels, step=60, wait=0.016):
        for _ in range(abs(pixels) // step):
            await self.page.mouse.wheel(0, step if pixels > 0 else -step)
            await asyncio.sleep(wait)
        await asyncio.sleep(0.4)


async def add_product(h, page, p):
    await h.click(page.locator("#toggle-add"), after=0.8)
    form = page.locator("#product-form")
    await h.type(form.locator("input[name=name]"), p["name"])
    await h.click(form.locator("#pf-category"), after=0.2)
    await form.locator("#pf-category").select_option(p["category"]); await h.pause(0.3)
    await h.type(form.locator("textarea[name=description]"), p["description"])
    await h.click(form.locator("select[name=size_class]"), after=0.2)
    await form.locator("select[name=size_class]").select_option(p["size_class"]); await h.pause(0.3)
    await h.type(form.locator("input[name=origin]"), p["origin"])
    await h.type(form.locator("input[name=markets]"), ", ".join(p["markets"]))
    await h.type(form.locator("input[name=provenance]"), p["provenance"])
    async with page.expect_file_chooser() as fc:
        await h.click(form.locator("label.dropzone"), after=0.1)
    await (await fc.value).set_files(p["image"]); await h.pause(0.8)
    await h.click(form.locator("button.primary"), after=2.5)


async def project_tour(h, page, rec, url, project):
    """Étapes 3 et 4 d'un projet déjà mené jusqu'au bout (plan généré par Kling AI, puis intégré)."""
    await page.goto(f"{url}/?analyse={project}#etape-3", wait_until="networkidle")
    await page.evaluate("document.fonts.ready")
    await page.locator("#kit-list .step-card").first.wait_for(state="visible", timeout=60_000)
    rec.mark("step3"); await h.pause(1.8)
    await h.scroll(520, wait=0.025); await h.pause(2.2)
    await h.scroll(520, wait=0.025); await h.pause(2.2)
    rec.mark("step4")
    await h.click(page.locator("#go-integration"), after=2.0)
    await h.click(page.locator("#integrate-list button", has_text="Voir la comparaison").first, after=2.0)
    video = page.locator("#cmp-video")
    await h.show(video); await h.pause(0.8)
    await video.evaluate("v => { v.muted = true; v.currentTime = 0; return v.play(); }")
    await h.move(page.locator("#cmp-track")); await h.pause(4.5)
    await h.click(page.locator(".segmented label", has_text="Version éditée"), after=0.4)
    await video.evaluate("v => { v.muted = true; return v.play(); }")
    await h.pause(6.5)
    await h.click(page.locator(".segmented label", has_text="Original"), after=0.4)
    await video.evaluate("v => v.play()"); await h.pause(3.0)
    await h.click(page.locator(".segmented label", has_text="Version éditée"), after=0.4)
    await video.evaluate("v => v.play()"); await h.pause(3.0)
    await video.evaluate("v => v.pause()")
    await h.show(page.locator("#cmp-fiche")); await h.pause(3.5)
    rec.mark("end"); await h.pause(1.0)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8002")
    ap.add_argument("--video")
    ap.add_argument("--out", default="output/demo-recording")
    ap.add_argument("--reviewer", default="Équipe SceneLine")
    ap.add_argument("--dry", action="store_true", help="s'arrête avant de lancer l'analyse")
    ap.add_argument("--project", help="identifiant d'un projet terminé : enregistre ses étapes 3 et 4")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.jpg"): f.unlink()
    root = Path(__file__).resolve().parent.parent
    real = {p["id"]: p for p in json.loads((root / "demo_products/real_products.json").read_text(encoding="utf-8"))}
    products = []
    for pid in ("badoit", "boga-cidre"):
        p = dict(real[pid]); p["image"] = str(root / "demo_products" / p["file"]); products.append(p)

    rec = Recorder(out)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(channel="chrome", headless=False, args=[f"--window-size={W},{H + 140}"])
        ctx = await browser.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, locale="fr-FR")
        await ctx.add_init_script(CURSOR_JS)
        page = await ctx.new_page()
        await page.goto(a.url + "/", wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        await rec.attach(page)
        h = Human(page)
        if a.project:
            try:
                await project_tour(h, page, rec, a.url, a.project)
            finally:
                rec.save(); await browser.close()
            return
        try:
            # ---------------- Étape 1 · Analyse
            rec.mark("intro"); await h.pause(1.8)
            async with page.expect_file_chooser() as fc:
                await h.click(page.locator("label.dropzone[for=video]"), after=0.1)
            await (await fc.value).set_files(a.video); await h.pause(1.0)
            await h.type(page.locator("#languages"), "français")
            await h.click(page.locator("details.disclosure summary").first, after=0.9)
            await h.type(page.locator("#location"), "Paris, France")
            await h.type(page.locator("#period"), "contemporaine")
            await h.type(page.locator("#intention"), "comédie en cuisine de restaurant")
            await h.click(page.locator("input[name=consent_processing]"), after=0.5)
            await h.click(page.locator("input[name=consent_provider]"), after=0.7)
            if a.dry:
                return
            rec.mark("analysis-start")
            await h.click(page.locator("#submit"), after=2.0)
            rec.slow = True
            await h.move(page.locator("#progress-card"))
            for _ in range(240):  # jusqu'à 40 minutes
                if await page.locator("#results").is_visible():
                    break
                if await page.locator("#resume").is_visible():
                    rec.mark("resume"); rec.slow = False
                    await h.click(page.locator("#resume"), after=1.0); rec.slow = True
                await asyncio.sleep(10)
            rec.slow = False
            rec.mark("analysis-done"); await h.pause(1.0)
            await page.evaluate("scrollTo({top: 0, behavior: 'smooth'})"); await h.pause(1.2)
            await h.move(page.locator("#videomap")); await h.pause(1.5)
            await h.scroll(420); await h.pause(1.2)
            first = page.locator("#candidates details.more summary").first
            if await first.count():
                await h.click(first, after=2.2)
                await h.scroll(380); await h.pause(1.8)
            if await page.locator("#guard-section").is_visible():
                await h.show(page.locator("#guard-section")); await h.pause(2.5)
            rec.mark("to-step2")
            await h.click(page.locator("#stage-1 [data-go='2']"), after=1.5)

            # ---------------- Étape 2 · Catalogue et appariement
            await page.locator("#matching").wait_for(state="visible")
            await h.move(page.locator("#context-text")); await h.pause(1.6)
            rec.mark("add-products")
            for p in products:
                await add_product(h, page, p)
            await h.pause(1.0)
            rec.mark("match-start")
            await h.click(page.locator("#run-match"), after=1.5)
            rec.slow = True
            await page.wait_for_function("() => /terminé/.test(document.getElementById('match-status').textContent)", timeout=1_800_000, polling=2000)
            rec.slow = False
            rec.mark("match-done"); await h.pause(1.0)
            await h.show(page.locator("#proposals-card")); await h.pause(1.2)
            await h.type(page.locator("#reviewer"), a.reviewer); await page.locator("#reviewer").dispatch_event("change")
            blocked = page.locator(".blocked-cmp").first
            if await blocked.count():
                await h.show(blocked); await h.move(blocked); await h.pause(3.0)
            badoit = page.locator("#proposals > *").filter(has_text="Badoit").first
            card = badoit if await badoit.count() else page.locator("#proposals > *").first
            await h.show(card); await h.pause(1.5)
            rec.mark("accept")
            await h.click(card.locator("button", has_text="Accepter").first, after=2.5)
            await h.pause(1.5)

            # ---------------- Étape 3 · Génération (aperçu) et Éthique 360
            rec.mark("to-step3")
            await h.click(page.locator("#stage-2 [data-go='3']"), after=2.0)
            await h.scroll(420); await h.pause(2.5)
            rec.mark("ethics")
            await page.evaluate("scrollTo({top: 0, behavior: 'smooth'})"); await h.pause(0.8)
            await h.click(page.locator("#lk-eth"), after=2.0)
            await h.scroll(900, wait=0.03); await h.pause(2.0)
            rec.mark("end"); await h.pause(1.0)
        finally:
            rec.save()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
