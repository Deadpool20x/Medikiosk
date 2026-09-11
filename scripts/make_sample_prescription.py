"""Generate the synthetic, de-identified prescription fixture used by OCR demos/tests.

Pure synthetic content: no real patient, clinician, or clinic data. Only the
fields in the current extraction schema (MedicineExtraction: medicine,
strength, dose, frequency) are rendered — nothing invented.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTS = [ROOT / "frontend" / "sample-prescription.png", ROOT / "sample-prescription.png"]

FIELDS = [
    ("Rx:", "Metformin"),
    ("Strength:", "500 mg"),
    ("Dose:", "One tablet"),
    ("Frequency:", "Twice daily"),
]

WIDTH, HEIGHT = 640, 480
BG = (255, 255, 255)
INK = (20, 20, 20)
GREY = (90, 90, 90)


def _draw() -> Image.Image:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    d = ImageDraw.Draw(img)
    title = ImageFont.load_default(size=36)
    label = ImageFont.load_default(size=28)

    d.text((40, 28), "Prescription", font=title, fill=INK)
    d.line((40, 78, WIDTH - 40, 78), fill=GREY, width=2)

    y = 130
    for name, value in FIELDS:
        d.text((40, y), name, font=label, fill=GREY)
        d.text((220, y), value, font=label, fill=INK)
        y += 64
    return img


def main() -> None:
    img = _draw()
    for out in OUTS:
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out, format="PNG")
    img.save(ROOT / "frontend" / "sample-prescription.jpg", format="JPEG", quality=85)
    print(f"wrote {len(OUTS) + 1} fixture(s), {WIDTH}x{HEIGHT}")


if __name__ == "__main__":
    main()