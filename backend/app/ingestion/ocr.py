"""Local OCR for menu PDFs and photos (open source, no external API).

PDF pages are rendered with pdfium (pypdfium2) and read with RapidOCR
(PaddleOCR's models on ONNX Runtime). Text boxes are regrouped into visual
lines so a dish and its price stay on one line, which is what the
structuring model needs.

Designed menus print the rupee sign in display fonts that OCR misreads as
F, ?, ¥, | or 1 ("1F369", "|379", "1369" for ₹369). When the PDF also has a
text layer, its numbers are exact, so a price token is corrected to the
text-layer number it matches once the misread prefix is dropped.
"""

from __future__ import annotations

import io
import logging
import re
import threading
from functools import lru_cache
from collections.abc import Iterator
from typing import Any

logger = logging.getLogger(__name__)

# Rendering scale for PDF pages (1.0 = 72 dpi). Higher barely helps accuracy
# and OCR time is dominated by recognition, not resolution.
PDF_SCALE = 1.4
# Photos are downscaled to this longest side before OCR (speed, memory).
MAX_SIDE = 2200

_lock = threading.Lock()


@lru_cache(maxsize=1)
def ocr_available() -> bool:
    """Whether the OCR packages are installed (photos and scans need them)."""
    try:
        import pypdfium2  # noqa: F401
        import rapidocr_onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


@lru_cache(maxsize=1)
def _engine() -> Any:
    from rapidocr_onnxruntime import RapidOCR

    return RapidOCR()


Box = tuple[float, float, float, float, str]  # (y-centre, height, x-left, x-right, text)


def _rows(boxes: list[Box]) -> list[str]:
    """Group boxes into lines by vertical position, each read left to right."""
    boxes = sorted(boxes, key=lambda b: (b[0], b[2]))
    lines: list[list[Box]] = []
    for b in boxes:
        if lines and abs(lines[-1][-1][0] - b[0]) < max(b[1], lines[-1][-1][1]) * 0.6:
            lines[-1].append(b)
        else:
            lines.append([b])
    return ["   ".join(t for *_, t in sorted(line, key=lambda b: b[2]) if t) for line in lines]


_PRICE_ONLY = re.compile(r"^\W{0,2}[F?¥|丨IZ1]{0,2}\d{2,5}(\.\d{1,2})?(\s*/-)?$")


def _splits_name_from_price(boxes: list[Box], x: float) -> int:
    """How many rows have text left of ``x`` and a bare price right of it (a name/price gap, not a gutter)."""
    count = 0
    for y, h, x0, _x1, t in boxes:
        if x0 < x or not _PRICE_ONLY.match(t.replace(" ", "")):
            continue
        # The nearest box to the price's left on the same row: if the gap between them is
        # where x is, x separates a dish from its price.
        same_row = [b for b in boxes if abs(y - b[0]) < max(h, b[1]) * 0.6 and b[3] <= x0]
        if same_row and max(b[3] for b in same_row) <= x:
            count += 1
    return count


def _gutter(boxes: list[Box], width: float) -> float | None:
    """x of an empty vertical band splitting the page into two columns, if there is one.

    Candidates are strips in the middle 30-70% of the page that almost no text
    box crosses (a few full-width titles/footers may). A strip with prices just
    to its right on dish-name rows is the gap between names and right-aligned
    prices inside one column, so it's skipped.
    """
    if width <= 0 or len(boxes) < 8:
        return None
    bins = 200
    step = width / bins
    crossings = [0] * bins
    for _y, _h, x0, x1, _t in boxes:
        for i in range(max(0, int(x0 / step)), min(bins, int(x1 / step) + 1)):
            crossings[i] += 1
    allowed = max(2, len(boxes) // 15)
    runs: list[tuple[int, float]] = []  # (width in bins, x-centre)
    run = 0
    for i in range(int(bins * 0.3), int(bins * 0.7) + 1):
        if i < bins and crossings[i] <= allowed:
            run += 1
        elif run:
            runs.append((run, (i - run / 2) * step))
            run = 0
    for size, x in sorted(runs, reverse=True):
        if size * step < width * 0.015:
            break
        left = sum(1 for b in boxes if b[3] <= x)
        right = sum(1 for b in boxes if b[2] >= x)
        if left >= 4 and right >= 4 and _splits_name_from_price(boxes, x) < 2:
            return x
    return None


def _lines(result: list | None, width: float = 0) -> list[str]:
    """OCR boxes to reading-order lines; a two-column page is read column by column."""
    boxes: list[Box] = []
    for box, text, _conf in result or []:
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        boxes.append(((min(ys) + max(ys)) / 2, max(ys) - min(ys), min(xs), max(xs), text.strip()))
    gutter = _gutter(boxes, width)
    if gutter is None:
        return _rows(boxes)
    spanning = [b for b in boxes if b[2] < gutter < b[3]]
    left = [b for b in boxes if b[3] <= gutter]
    right = [b for b in boxes if b[2] >= gutter]
    top = min((b[0] for b in left + right), default=0)
    head = [b for b in spanning if b[0] <= top]  # titles above the columns
    foot = [b for b in spanning if b[0] > top]
    return _rows(head) + _rows(left) + _rows(right) + _rows(foot)


def ocr_image(image: Any) -> list[str]:
    """OCR a PIL image into text lines."""
    if max(image.size) > MAX_SIDE:
        image = image.copy()
        image.thumbnail((MAX_SIDE, MAX_SIDE))
    import numpy as np

    with _lock:  # one OCR at a time: keeps memory flat on small servers
        # Menus are upright; skipping the rotation classifier saves ~30%.
        result, _ = _engine()(np.asarray(image.convert("RGB")), use_cls=False)
    return _lines(result, image.size[0])


def ocr_photo(data: bytes) -> list[str]:
    from PIL import Image, ImageOps

    image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
    return ocr_image(image)


# A price, optionally behind a misread rupee sign, possibly glued to the dish
# name ("PESHAWARIALOOIF379"). Group 1 is the misread sign, group 2 the digits.
_PRICE = re.compile(r"(I?F|[?¥|丨₹Z]|(?<![\w.])[Il1](?=F?\d))?F?(?<!\d)(\d{2,5})(?!\d)")


def fix_prices(line: str, known: set[str]) -> str:
    """Rewrite OCR price tokens to "₹<n>" using the exact numbers from the text layer."""
    if not known:
        return line

    def sub(m: re.Match[str]) -> str:
        prefix, digits = m.group(1) or "", m.group(2)
        if m.group(0) != prefix + digits:  # an "F" between sign and digits ("1F369")
            prefix = m.group(0)[: -len(digits)]
        if digits in known and prefix:
            return f"₹{digits}"
        # "1369" where the text layer only has 369: the 1 was the ₹ sign.
        if digits not in known and len(digits) > 2 and digits[0] in "17" and digits[1:] in known:
            return f"₹{digits[1:]}"
        return m.group(0)

    return re.sub(r"(\d)₹", r"\1 ₹", _PRICE.sub(sub, line))


def pdf_pages_ocr(data: bytes, text_layers: list[str] | None = None) -> Iterator[list[str]]:
    """OCR a PDF page by page (yielded as each finishes). ``text_layers`` supply exact numbers for price fixes."""
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(data)
    try:
        for n in range(len(pdf)):
            image = pdf[n].render(scale=PDF_SCALE).to_pil()
            lines = ocr_image(image)
            layer = text_layers[n] if text_layers and n < len(text_layers) else ""
            known = set(re.findall(r"\d{2,5}", layer))
            yield [fix_prices(line, known) for line in lines]
    finally:
        pdf.close()
