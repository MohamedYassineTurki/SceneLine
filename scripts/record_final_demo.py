"""Enregistre la démonstration du parcours complet de SceneLine, version finale, comme un utilisateur.

Étape 1 : import de l'épisode, contexte, autorisations, analyse réelle (Gemini), lecture des résultats.
Étape 2 : deux produits ajoutés à la main, planche d'angles, appariement réel, acceptation de Boga Cidre sur
la table basse (00:31). Étape 3 (version finale) : un accord, « Générer et intégrer » : kit média, image de
référence, vidéo ; lecture de la vidéo générée, puis « Intégrer dans l'épisode ». Étape 4 : comparaison.

Usage :
  .venv/Scripts/python scripts/record_final_demo.py --video <épisode.mp4> --stop-after-analysis --out output/demo-final
  .venv/Scripts/python scripts/record_final_demo.py --project <id> --sheet <planche.png> --out output/demo-final-2
  .venv/Scripts/python scripts/build_demo_video.py output/demo-final docs/media/demo-final.mp4 --extra output/demo-final-2
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from record_demo import CURSOR_JS, H, W, Human, Recorder, add_product  # noqa: E402


async def wait_for(page, script, minutes=40):
    await page.wait_for_function(script, timeout=minutes * 60_000, polling=2000)


async def step1_new(h, page, rec, a):
    rec.mark("intro"); await h.pause(2.0)
    async with page.expect_file_chooser() as fc:
        await h.click(page.locator("label.dropzone[for=video]"), after=0.1)
    await (await fc.value).set_files(a.video); await h.pause(1.0)
    await h.click(page.locator("#work_type"), after=0.2)
    await page.locator("#work_type").select_option("Série"); await h.pause(0.4)
    await h.type(page.locator("#languages"), "Darija tunisienne, français")
    await h.click(page.locator("#transcription"), after=0.2)
    await page.locator("#transcription").select_option("darija"); await h.pause(0.6)
    await h.click(page.locator("details.disclosure summary").first, after=0.9)
    await h.type(page.locator("#location"), "Tunis")
    await h.click(page.locator("input[name=consent_processing]"), after=0.5)
    await h.click(page.locator("input[name=consent_provider]"), after=0.7)
    rec.mark("analysis-start")
    await h.click(page.locator("#submit"), after=2.0)
    rec.slow = True
    await h.move(page.locator("#progress-card"))
    for _ in range(240):
        if await page.locator("#results").is_visible():
            break
        if await page.locator("#resume").is_visible():
            await h.click(page.locator("#resume"), after=1.0)
        await asyncio.sleep(10)
    rec.slow = False
    rec.mark("analysis-done"); await h.pause(1.0)
    await page.evaluate("scrollTo({top: 0, behavior: 'smooth'})"); await h.pause(1.2)
    await h.move(page.locator("#videomap")); await h.pause(2.0)
    await h.scroll(420); await h.pause(1.5)
    await h.scroll(420); await h.pause(1.5)
    rec.mark("cut")


async def step1_resume(h, page, rec, a):
    """Résultats de l'étape 1 d'un projet déjà analysé (même épisode)."""
    await page.goto(f"{a.url}/?analyse={a.project}", wait_until="networkidle")
    await page.locator("#results").wait_for(state="visible", timeout=120_000)
    await page.evaluate("scrollTo({top: 700})"); await h.pause(0.5)
    rec.mark("resume"); await h.pause(1.0)
    rows = page.locator("[class*=row], article, li").filter(has_text="00:31").filter(has_text="able basse")
    if await rows.count():
        await h.show(rows.first); await h.move(rows.first); await h.pause(3.0)
    await page.evaluate("scrollTo({top: 0, behavior: 'smooth'})"); await h.pause(1.0)


async def step2(h, page, rec, a, products):
    rec.mark("to-step2")
    await h.click(page.locator("#stage-1 [data-go='2']"), after=1.5)
    try:
        await page.locator("#matching").wait_for(state="visible", timeout=20_000)
    except Exception:   # le projet n'était pas encore rechargé : on rouvre l'étape 2
        await page.goto(page.url.split("#")[0] + "#etape-2", wait_until="networkidle")
        await page.locator("#matching").wait_for(state="visible", timeout=60_000)
    await h.move(page.locator("#context-text")); await h.pause(1.5)
    rec.mark("add-products")
    for p in products:
        await add_product(h, page, p)
    if a.sheet:
        card = page.locator("article.product").filter(has_text="Boga Cidre").first
        await h.click(card.locator("details.views summary"), after=0.8)
        async with page.expect_file_chooser() as fc:
            await h.click(card.locator("button", has_text="Importer la photo"), after=0.1)
        await (await fc.value).set_files(a.sheet); await h.pause(2.0)
    await h.pause(1.0)
    rec.mark("match-start")
    await h.click(page.locator("#run-match"), after=1.5)
    rec.slow = True
    await wait_for(page, "() => /terminé/.test(document.getElementById('match-status').textContent)", 30)
    rec.slow = False
    rec.mark("match-done"); await h.pause(1.0)
    await h.show(page.locator("#proposals-card")); await h.pause(1.0)
    await h.type(page.locator("#reviewer"), a.reviewer); await page.locator("#reviewer").dispatch_event("change")
    blocked = page.locator(".blocked-cmp").first
    if await blocked.count():
        await h.show(blocked); await h.move(blocked); await h.pause(3.0)
    card = page.locator("#proposals > *").filter(has_text="00:31").filter(has_text="Boga Cidre").first
    await h.show(card); await h.pause(1.8)
    rec.mark("accept")
    await h.click(card.locator("button", has_text="Accepter").first, after=2.5)


async def step3_and_4(h, page, rec, click=True):
    rec.mark("to-step3")
    if click:
        await page.evaluate("scrollTo({top: 0, behavior: 'smooth'})"); await h.pause(0.8)
        await h.click(page.locator("#stage-2 [data-go='3']"), after=2.0)
    panel = page.locator("#stage-3 .final-panel").filter(has=page.locator("button", has_text="Générer et intégrer")).first
    try:
        await panel.wait_for(state="visible", timeout=15_000)
    except Exception:   # l'acceptation n'était pas encore prise en compte : on rouvre l'étape 3
        await page.goto(page.url.split("#")[0] + "#etape-3", wait_until="networkidle")
        await panel.wait_for(state="visible", timeout=60_000)
    await h.show(panel); await h.pause(1.5)
    await h.click(panel.locator("input[type=checkbox]"), after=0.6)
    rec.mark("gen-start")
    await h.click(panel.locator("button", has_text="Générer et intégrer"), after=1.0)
    await h.move(page.locator(".final-panel .run-steps").first)
    rec.slow = True
    await wait_for(page, "() => /Image de référence/.test([...document.querySelectorAll('.final-panel .run-step.current b')].map(b => b.textContent).join(''))", 20)
    rec.slow = False
    rec.mark("gen-reference"); await h.pause(0.5)
    await wait_for(page, "() => [...document.querySelectorAll('.final-panel button')].some(b => /Intégrer dans/.test(b.textContent))", 20)
    rec.mark("gen-ready")
    video = page.locator(".final-panel .run-video").first
    await h.show(page.locator(".final-panel .run-media").first); await h.pause(1.0)
    await video.evaluate("v => { v.muted = true; v.currentTime = 0; return v.play(); }")
    await h.move(video); await h.pause(6.0)
    rec.mark("integrate")
    await h.click(page.locator(".final-panel button", has_text="Intégrer dans"), after=1.0)

    await page.locator("#stage-4").wait_for(state="visible", timeout=300_000)
    rec.mark("step4"); await h.pause(2.0)
    await h.click(page.locator("#integrate-list button", has_text="Voir la comparaison").first, after=2.0)
    cmp = page.locator("#cmp-video")
    await h.show(cmp); await h.pause(0.8)
    await cmp.evaluate("v => { v.muted = true; v.currentTime = 0; return v.play(); }")
    await h.move(page.locator("#cmp-track")); await h.pause(5.0)
    await h.click(page.locator(".segmented label", has_text="Version éditée"), after=0.4)
    await cmp.evaluate("v => { v.muted = true; v.currentTime = 0; return v.play(); }")
    await h.pause(7.0)
    await h.click(page.locator(".segmented label", has_text="Original"), after=0.4)
    await cmp.evaluate("v => { v.currentTime = 0.8; return v.play(); }"); await h.pause(3.5)
    await h.click(page.locator(".segmented label", has_text="Version éditée"), after=0.4)
    await cmp.evaluate("v => { v.currentTime = 0.8; return v.play(); }"); await h.pause(4.0)
    await cmp.evaluate("v => v.pause()")
    await h.show(page.locator("#cmp-fiche")); await h.pause(3.5)
    rec.mark("end"); await h.pause(1.0)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8002")
    ap.add_argument("--video", help="épisode à importer (nouveau projet)")
    ap.add_argument("--project", help="projet déjà analysé : l'enregistrement reprend aux résultats de l'étape 1")
    ap.add_argument("--stop-after-analysis", action="store_true")
    ap.add_argument("--from-step3", action="store_true", help="avec --project : commence à l'étape 3")
    ap.add_argument("--sheet", help="planche d'angles du produit (facultative)")
    ap.add_argument("--out", default="output/demo-final")
    ap.add_argument("--reviewer", default="Yassine")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("f*.jpg"):
        f.unlink()
    root = Path(__file__).resolve().parent.parent
    real = {p["id"]: p for p in json.loads((root / "demo_products/real_products.json").read_text(encoding="utf-8"))}
    products = []
    for pid in ("boga-cidre", "badoit"):
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
        try:
            if a.project and a.from_step3:
                await page.goto(f"{a.url}/?analyse={a.project}#etape-3", wait_until="networkidle")
                rec.mark("resume")
                await step3_and_4(h, page, rec, click=False)
                return
            if a.project:
                await step1_resume(h, page, rec, a)
            else:
                await step1_new(h, page, rec, a)
                if a.stop_after_analysis:
                    return
            await step2(h, page, rec, a, products)
            await step3_and_4(h, page, rec)
        finally:
            rec.save()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
