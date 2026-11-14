"""Génère le catalogue fictif de démonstration (visuels dessinés pour SceneLine, aucun produit réel)."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).parent
FONT = "C:/Windows/Fonts/bahnschrift.ttf"
SIZE = 640


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def canvas(bg):
    image = Image.new("RGB", (SIZE, SIZE), bg)
    return image, ImageDraw.Draw(image)


def label(draw, text, y, color, size=54):
    box = draw.textbbox((0, 0), text, font=font(size))
    draw.text(((SIZE - (box[2] - box[0])) / 2, y), text, fill=color, font=font(size))


def boreal():
    image, d = canvas("#f1efe9")
    d.ellipse((180, 150, 460, 430), outline="#1d1d1f", width=14)           # logo monochrome : casserole
    d.rounded_rectangle((440, 270, 600, 300), 14, fill="#1d1d1f")
    d.rectangle((200, 300, 440, 340), fill="#1d1d1f")
    label(d, "ATELIER BORÉAL", 480, "#1d1d1f", 56)
    label(d, "matériel de cuisine", 550, "#55555a", 30)
    return image


def minuit():
    image, d = canvas("#14162b")
    d.rounded_rectangle((270, 90, 370, 150), 18, fill="#c9a24a")             # bouteille
    d.rounded_rectangle((250, 150, 390, 470), 40, fill="#222752", outline="#c9a24a", width=5)
    d.ellipse((318, 300, 322, 304), fill="#c9a24a")
    label(d, "MINUIT", 500, "#c9a24a", 66)
    label(d, "liqueur · 18 % vol.", 580, "#9aa0c8", 28)
    return image


def zephyr():
    image, d = canvas("#dff1f6")
    d.rounded_rectangle((285, 70, 355, 130), 14, fill="#2a6f8f")             # bouteille d'eau
    d.rounded_rectangle((235, 130, 405, 470), 50, fill="#bfe6f2", outline="#2a6f8f", width=6)
    d.rectangle((237, 260, 403, 350), fill="#2a6f8f")
    label(d, "SOURCE ZÉPHYR", 495, "#1d5a75", 52)
    label(d, "eau minérale naturelle", 565, "#2a6f8f", 28)
    return image


def clairnet():
    image, d = canvas("#fff4d6")
    d.rounded_rectangle((250, 170, 390, 450), 30, fill="#3fae5c")            # flacon spray
    d.rectangle((300, 110, 340, 175), fill="#2c7d42")
    d.polygon([(340, 110), (430, 135), (430, 155), (340, 150)], fill="#2c7d42")
    d.rectangle((262, 270, 378, 370), fill="#ffffff")
    label(d, "CLAIR & NET", 490, "#2c7d42", 58)
    label(d, "nettoyant multi-surfaces", 560, "#5b6b3a", 28)
    return image


def harissa():
    image, d = canvas("#f3e2cf")
    d.rounded_rectangle((200, 190, 440, 440), 40, fill="#b3261e")            # pot de harissa
    d.rectangle((190, 160, 450, 205), fill="#7d1812")
    d.ellipse((290, 280, 350, 340), fill="#f3e2cf")
    label(d, "HARISSA EL KASBA", 480, "#7d1812", 46)
    label(d, "piment · recette familiale", 548, "#8a5a3a", 28)
    return image


def orbyt():
    image, d = canvas("#0f1a2e")
    d.arc((170, 120, 470, 420), 180, 360, fill="#38d6ff", width=22)           # casque audio
    d.rounded_rectangle((150, 270, 225, 420), 28, fill="#38d6ff")
    d.rounded_rectangle((415, 270, 490, 420), 28, fill="#38d6ff")
    label(d, "ORBYT", 480, "#38d6ff", 72)
    label(d, "casque sans fil", 570, "#8fb4c8", 28)
    return image


PRODUCTS = [
    dict(id="atelier-boreal", name="Atelier Boréal", file="atelier-boreal.png", draw=boreal,
         description="Marque fictive de matériel de cuisine professionnel. Visuel : petit logo monochrome, sans texte promotionnel.",
         category="cuisine_ustensiles", modes=["affiche_murale", "signaletique", "objet_pose"], size_class="petit", exclusions=""),
    dict(id="minuit", name="Minuit", file="minuit.png", draw=minuit,
         description="Marque fictive de liqueur. Boisson alcoolisée (18 % vol.).",
         category="boisson_alcoolisee", modes=["objet_pose"], size_class="moyen",
         exclusions="Ne pas associer à une scène de travail ni de conflit."),
    dict(id="clair-et-net", name="Clair & Net", file="clair-et-net.png", draw=clairnet,
         description="Marque fictive de nettoyant ménager multi-surfaces, flacon spray vert.",
         category="entretien_menager", modes=["objet_pose"], size_class="moyen", exclusions=""),
    dict(id="orbyt", name="Orbyt", file="orbyt.png", draw=orbyt,
         description="Marque fictive de casque audio sans fil. Produit électronique contemporain.",
         category="technologie", modes=["objet_pose"], size_class="moyen",
         exclusions="Ne pas utiliser dans une œuvre dont l'époque est antérieure aux années 2000."),
]

if __name__ == "__main__":
    catalog = json.loads((OUT / "real_products.json").read_text(encoding="utf-8"))
    for product in PRODUCTS:
        product["draw"]().save(OUT / product["file"])
        catalog.append({k: v for k, v in product.items() if k != "draw"}
                       | {"provenance": "FICTIF : visuel dessiné pour la démonstration SceneLine ; aucune marque réelle."})
    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    print(len(catalog), "produits générés")
