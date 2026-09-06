"""
Tamper detection via Error Level Analysis (ELA) — operates entirely
in-memory (BytesIO), since serverless functions don't reliably persist
files between requests.

NOTE: ELA is a weak, easily-confounded signal. Images that have simply
been re-saved/re-compressed at some point (very common for phone
photos sent through messaging apps) will show elevated ELA with no
actual tampering. Treat this as one weak signal among several.

The returned ELA image is downscaled and re-encoded as JPEG before
being base64-encoded — it's only a visual aid for a human reviewer,
and Vercel Functions cap total response size at 4.5 MB, so a
full-resolution PNG diff of a large ID photo could push a response
over that limit on its own.
"""
import base64
import io

import numpy as np
from PIL import Image, ImageChops

ELA_THUMBNAIL_MAX_DIM = 600
ELA_THUMBNAIL_QUALITY = 80


def compute_ela(image_bytes: bytes, quality: int = 90, scale: int = 15) -> Image.Image:
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer)

    diff = ImageChops.difference(original, resaved)
    diff_array = np.array(diff).astype(np.float32)

    max_diff = diff_array.max() if diff_array.max() > 0 else 1
    scale_factor = min(255.0 / max_diff, scale)
    diff_array = (diff_array * scale_factor).clip(0, 255).astype(np.uint8)

    return Image.fromarray(diff_array)


def _encode_thumbnail(ela_img: Image.Image) -> str:
    thumb = ela_img.convert("RGB")
    thumb.thumbnail((ELA_THUMBNAIL_MAX_DIM, ELA_THUMBNAIL_MAX_DIM))

    out_buffer = io.BytesIO()
    thumb.save(out_buffer, format="JPEG", quality=ELA_THUMBNAIL_QUALITY)
    encoded = base64.b64encode(out_buffer.getvalue()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded}"


def tamper_score(image_bytes: bytes) -> dict:
    # Full-resolution ELA is computed for scoring accuracy; only the
    # returned preview image is downscaled.
    ela_img = compute_ela(image_bytes)
    ela_array = np.array(ela_img.convert("L"))

    bright_pixels = np.sum(ela_array > 60)
    total_pixels = ela_array.size
    bright_ratio = bright_pixels / total_pixels

    score = min(round(bright_ratio * 500), 100)
    # Labeled conservatively: this is a recompression-artifact signal,
    # not a confirmed tamper finding.
    verdict = "possible_recompression_artifact" if score > 35 else "no_strong_signal"

    return {
        "tamper_score": int(score),
        "verdict": verdict,
        "ela_image_data_uri": _encode_thumbnail(ela_img),
    }
