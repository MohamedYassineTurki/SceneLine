"""SceneLine · media kit PDF du Rapport d'opportunités.

Un document à montrer à un annonceur potentiel : les mêmes données que l'écran
(`opportunity_finder.report.build`), jamais recalculées différemment. Une page de garde avec les
quatre indicateurs, une page par emplacement retenu (image de référence déjà enregistrée par
l'analyse, avec l'emplacement encadré, la durée exacte, la visibilité, le type de plan, le contexte
de la scène et l'avis du Cultural Integrity Guard), puis les conseils de monétisation et
l'avertissement.
"""

import json
import unicodedata

from fpdf import FPDF
from PIL import Image

from opportunity_finder import report
from product_matcher.catalog import MODES

PAGE_MARGIN = 15
CONTENT_W = 210 - 2 * PAGE_MARGIN
INK = (29, 29, 31)
MUTED = (91, 91, 97)
MARKER = (255, 204, 0)
RISK_COLORS = {"faible": (25, 115, 47), "moyen": (138, 81, 0), "eleve": (184, 29, 34)}


PDF_ENCODING = "cp1252"  # polices de base du PDF : couvre le français (œ, €, « »), pas l'arabe


def pdf_safe(text):
    """Texte que les polices de base savent écrire, sans jamais faire échouer le PDF.

    Les formes typographiques (espace fine insécable, ligatures…) deviennent leur équivalent simple ;
    un passage que la police ne sait pas écrire (arabe, emoji, caractère illisible) devient « … »."""
    text = unicodedata.normalize("NFKC", str(text))
    out, spaces, missing = [], "", False
    for char in text:
        if char.isspace():
            spaces += char  # gardés en attente : un passage illisible peut contenir des espaces
            continue
        try:
            char.encode(PDF_ENCODING)
        except UnicodeEncodeError:
            if not missing:  # un seul « … » pour tout le passage illisible
                out.append(spaces + "…")
                missing = True
            spaces = ""
            continue
        out.append(spaces + char)
        spaces, missing = "", False
    return "".join(out) + spaces


class _PDF(FPDF):
    def normalize_text(self, text):
        return super().normalize_text(pdf_safe(text))


def clock(ms):
    seconds = int(ms // 1000)
    return f"{seconds // 60:02}:{seconds % 60:02}"


def _heading(pdf, text):
    pdf.set_font("Helvetica", "B", 15)
    pdf.set_text_color(*INK)
    pdf.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")


def _label_value(pdf, label, value):
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(55, 7, label)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.cell(0, 7, value, new_x="LMARGIN", new_y="NEXT")


def _cover(pdf, sceneline, data):
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(*INK)
    pdf.cell(0, 12, "Rapport d'opportunités SceneLine", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 6, sceneline.get("producer_description") or "Œuvre analysée par SceneLine.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    ind = data["indicators"]
    rows = [
        ("Emplacements potentiels", str(ind["potential_locations"])),
        ("Catégories compatibles", str(ind["compatible_categories"])),
        ("Durée totale à l'écran", ind["total_screen_time_text"]),
        ("Déconseillés par le Guard", str(ind["guard_discouraged"])),
    ]
    for label, value in rows:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*INK)
        pdf.cell(95, 9, label, border=1)
        pdf.cell(0, 9, value, border=1, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, data["disclaimer"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5, data["directory_notice"], new_x="LMARGIN", new_y="NEXT")


def _draw_region(pdf, x, y, w, h, region):
    if not region:
        return
    rx = x + region["x"] * w
    ry = y + region["y"] * h
    rw = region["width"] * w
    rh = region["height"] * h
    pdf.set_draw_color(*INK)
    pdf.set_line_width(0.9)
    pdf.rect(rx, ry, rw, rh)
    pdf.set_draw_color(*MARKER)
    pdf.set_line_width(0.5)
    pdf.rect(rx + 0.4, ry + 0.4, max(rw - 0.8, 0), max(rh - 0.8, 0))


def _opportunity_page(pdf, folder, item):
    pdf.add_page()
    _heading(pdf, f"N° {item['rank']} · {item['surface'][:60]}")
    frame = folder / item["reference_frame"]
    y = pdf.get_y()
    if frame.is_file():
        with Image.open(frame) as image:
            px_w, px_h = image.size
        height = CONTENT_W * px_h / px_w
        pdf.image(str(frame), x=PAGE_MARGIN, y=y, w=CONTENT_W, h=height)
        _draw_region(pdf, PAGE_MARGIN, y, CONTENT_W, height, item.get("region"))
        pdf.set_y(y + height + 4)
    duration_s = round((item["end_ms"] - item["start_ms"]) / 1000, 1)
    visible = {"oui": "Oui, sur tout l'intervalle", "partiel": "Partielle", "non": "Non"}.get(item["visible_throughout"], "—")
    _label_value(pdf, "Intervalle", f"{clock(item['start_ms'])}–{clock(item['end_ms'])} ({duration_s} s exactes)")
    _label_value(pdf, "Visibilité", visible)
    _label_value(pdf, "Type de plan", MODES.get(item["placement_mode"], item["placement_mode"]))
    _label_value(pdf, "Score mesuré", f"{item['overall_score']}/10")
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Contexte de la scène", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, f"{item['scene_summary']} — Lieu : {item['scene_location']} · Époque : "
                         f"{item['scene_period']} · Ton : {item['scene_tone']}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    guard = item["guard"]
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*RISK_COLORS.get(guard["level"], INK))
    pdf.cell(0, 6, "Cultural Integrity Guard · " + guard["label"], new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    pdf.multi_cell(0, 6, guard["summary"], new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Annonceurs inscrits compatibles", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    if item["advertiser_matches"]:
        for match in item["advertiser_matches"]:
            pdf.multi_cell(0, 6, f"- {match['name']} ({match['provenance']}) · {match['why']}",
                          new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.multi_cell(0, 6, "- Aucun annonceur inscrit ne correspond pour l'instant.",
                       new_x="LMARGIN", new_y="NEXT")

    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(*MUTED)
    pdf.cell(0, 6, "Types de partenaires à démarcher", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    if item["advertiser_fallback"]:
        for text in item["advertiser_fallback"]:
            pdf.multi_cell(0, 6, f"- {text}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.multi_cell(0, 6, "- Aucune catégorie compatible relevée pour cet emplacement.",
                       new_x="LMARGIN", new_y="NEXT")


def _closing(pdf, data):
    pdf.add_page()
    _heading(pdf, "Conseils de monétisation")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*INK)
    for tip in data["monetization_tips"]:
        pdf.multi_cell(0, 6, "- " + tip, new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)
    pdf.ln(4)
    pdf.set_font("Helvetica", "I", 10)
    pdf.multi_cell(0, 6, data["disclaimer"], new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.multi_cell(0, 5, data["directory_notice"], new_x="LMARGIN", new_y="NEXT")


def build_pdf(folder):
    data = report.build(folder)
    sceneline = json.loads((folder / "sceneline.json").read_text(encoding="utf-8"))
    pdf = _PDF(orientation="P", unit="mm", format="A4")
    pdf.core_fonts_encoding = PDF_ENCODING
    pdf.set_margins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
    pdf.set_auto_page_break(auto=True, margin=PAGE_MARGIN)
    _cover(pdf, sceneline, data)
    for item in data["opportunities"]:
        _opportunity_page(pdf, folder, item)
    _closing(pdf, data)
    return bytes(pdf.output())
