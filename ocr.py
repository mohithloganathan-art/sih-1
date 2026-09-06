"""
OCR via the OCR.space cloud API (no system Tesseract binary needed —
required since Vercel's serverless Python image can't install one).
"""
import os
import re

import requests

OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "helloworld")  # demo key = rate-limited


def extract_text_via_ocr_api(image_bytes: bytes) -> str:
    response = requests.post(
        "https://api.ocr.space/parse/image",
        files={"filename": ("image.jpg", image_bytes)},
        data={"apikey": OCR_SPACE_API_KEY, "language": "eng", "OCREngine": 2},
        timeout=30,
    )
    result = response.json()
    if result.get("IsErroredOnProcessing"):
        return ""
    parsed = result.get("ParsedResults") or []
    if not parsed:
        return ""
    return parsed[0].get("ParsedText", "")


def parse_fields(raw_text: str) -> dict:
    """
    Low-confidence heuristic extraction — always pair with raw_ocr_text
    so a human reviewer can correct mistakes.
    """
    fields = {"name": None, "dob": None, "id_number": None}

    dob_match = re.search(r"\b(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\b", raw_text)
    if dob_match:
        fields["dob"] = dob_match.group(1)

    id_match = re.search(r"\b\d{6,12}\b", raw_text)
    if id_match:
        fields["id_number"] = id_match.group(0)

    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.isupper() and 4 <= len(stripped) <= 40 and any(c.isalpha() for c in stripped):
            fields["name"] = stripped
            break

    return fields
