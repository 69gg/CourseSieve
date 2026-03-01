from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image


def ocr_image(image_path: Path, lang: str, tesseract_cmd: str | None = None) -> tuple[str, float | None]:
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    image = Image.open(image_path)
    text = pytesseract.image_to_string(image, lang=lang)
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    confs: list[float] = []
    for raw in data.get("conf", []):
        try:
            value = float(raw)
        except ValueError:
            continue
        if value >= 0:
            confs.append(value)
    conf = sum(confs) / len(confs) if confs else None
    return text.strip(), conf
