"""
AI-Based Fake Identity & Document Screening System — Vercel-compatible
Flask entrypoint.

Why this stack (vs. a local FastAPI/pytesseract/face_recognition
version):
  - OCR: OCR.space cloud API instead of pytesseract, since Vercel's
    Python runtime has no system Tesseract binary available.
  - Face matching: OpenCV Haar Cascade + histogram comparison instead
    of `face_recognition`/dlib, which needs a C++ compiler to build
    and often fails or exceeds size limits on the serverless image.
    This is a rougher similarity signal, not true face-embedding
    matching — fine for a demo, not for production identity
    verification.
  - Framework: Flask (WSGI) instead of FastAPI, since Vercel's Python
    runtime runs WSGI apps natively.
  - No local disk serving: the ELA tamper-detection image is returned
    as a small base64 JPEG data URI in the JSON response, since
    serverless functions don't reliably persist/serve files between
    requests, and Vercel Functions cap total request/response size at
    4.5 MB.

Deployment:
  Vercel auto-detects this Flask app with zero configuration — no
  vercel.json is needed. It looks for a Flask instance named `app` at
  a supported entrypoint (this file, api/index.py, qualifies) and
  routes every request to it.

Setup:
  1. Get a free OCR.space API key: https://ocr.space/ocrapi
  2. In Vercel project settings, add env var OCR_SPACE_API_KEY=<key>
     (without it, falls back to OCR.space's public demo key, which is
     rate-limited — fine only for quick testing).
  3. Push to GitHub and import the repo in Vercel, or run `vercel`
     from the repo root with the CLI.

Local test:
  pip install -r requirements.txt
  python api/index.py
  open http://127.0.0.1:5000
"""
import os
import sys

# Make the sibling `lib/` package importable both locally and on Vercel.
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, jsonify, render_template, request

from lib.face_match import compare_faces
from lib.ocr import extract_text_via_ocr_api, parse_fields
from lib.tamper import tamper_score
from lib.verdict import overall_verdict

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__, template_folder="templates")

# Backstop against oversized uploads. The frontend already resizes
# images before sending them, but Vercel's own 4.5 MB request-body
# limit applies regardless of what the client does, so this just gives
# a clean error instead of letting a huge request hit that wall.
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB combined


@app.errorhandler(413)
def too_large(_e):
    return jsonify({"error": "Uploads are too large. Please use smaller images (under ~4 MB combined)."}), 413


@app.route("/api/screen", methods=["POST"])
def screen_identity():
    if "id_document" not in request.files or "selfie" not in request.files:
        return jsonify({"error": "Both id_document and selfie files are required"}), 400

    id_bytes = request.files["id_document"].read()
    selfie_bytes = request.files["selfie"].read()

    if not id_bytes or not selfie_bytes:
        return jsonify({"error": "One of the uploaded files was empty"}), 400

    try:
        raw_text = extract_text_via_ocr_api(id_bytes)
        fields = parse_fields(raw_text)
        tamper_result = tamper_score(id_bytes)
        face_result = compare_faces(id_bytes, selfie_bytes)
        verdict = overall_verdict(tamper_result, face_result)
    except Exception as e:  # noqa: BLE001 — surface a clean error to the frontend
        return jsonify({"error": f"Screening failed: {e}"}), 502

    return jsonify({
        "extracted_fields": fields,
        "raw_ocr_text": raw_text.strip(),
        "tamper_check": tamper_result,
        "face_match": face_result,
        "verdict": verdict,
    })


@app.route("/", methods=["GET"])
def homepage():
    return render_template("index.html")


# Local dev entrypoint — Vercel itself imports `app` directly and never
# runs this block.
if __name__ == "__main__":
    app.run(debug=True)
