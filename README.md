# ID Screening — Vercel Build

A Vercel-deployable version of the ID screening prototype: OCR field
extraction, Error-Level-Analysis tamper detection, and a lightweight
ID-photo-vs-selfie face similarity check, behind a Flask app.

**This is a demo/hackathon build, not a production KYC system.** See
"Known limitations" below.

## Deploying — no vercel.json needed

Vercel detects Flask apps with **zero configuration**: it finds the
`app` instance in `api/index.py` (a supported entrypoint location) and
routes every request to it automatically. There is no `vercel.json` in
this repo — don't add one unless you need to override something
specific; an unnecessary legacy `builds`/`routes` config can conflict
with the current auto-detection.

1. Push this repo to GitHub.
2. In Vercel, "Add New Project" → import the repo. Vercel will detect
   the Python/Flask setup from `requirements.txt` automatically.
3. Add an environment variable before or after the first deploy:
   ```
   OCR_SPACE_API_KEY = <your key from https://ocr.space/ocrapi>
   ```
   Without it, the app falls back to OCR.space's public demo key
   (`helloworld`), which is rate-limited — fine only for quick testing.
4. Deploy. Vercel gives you a live URL when it finishes.

### Local test before deploying

```bash
pip install -r requirements.txt
python api/index.py
open http://127.0.0.1:5000
```

## Why this stack differs from a typical local build

| Concern | Local-friendly choice | Why it's swapped here |
|---|---|---|
| OCR | pytesseract (system Tesseract binary) | Vercel's Python runtime has no system Tesseract binary — swapped for the [OCR.space](https://ocr.space/ocrapi) cloud API |
| Face matching | `face_recognition`/dlib | Needs a C++ compiler to build; often fails or exceeds size limits on the serverless image — swapped for OpenCV Haar Cascade + histogram comparison |
| Framework | FastAPI (ASGI) | Vercel's Python runtime runs Flask/WSGI natively, and zero-config detection is built specifically around Flask/FastAPI/Django |
| Tamper image | saved to disk, served via static route | Serverless functions don't reliably persist files between requests — returned as a base64 JPEG data URI in the JSON response instead |

## Handling Vercel's 4.5 MB request/response limit

Vercel Functions cap **both** request and response bodies at 4.5 MB.
A couple of real photos (an ID + a selfie) can exceed that on their
own, so this build takes two precautions:

- **Client-side resize before upload** (`api/templates/index.html`):
  both images are downscaled to a max dimension of 1600px and
  re-encoded as JPEG in the browser via `<canvas>` before being sent,
  so the upload reliably fits under the limit.
- **Downscaled tamper-preview image** (`lib/tamper.py`): the ELA diff
  image returned in the response is a 600px-max JPEG thumbnail, not a
  full-resolution PNG, so the response stays small regardless of the
  original photo size.
- **Server-side size guard** (`api/index.py`): `MAX_CONTENT_LENGTH` is
  set to 4 MB combined as a backstop, returning a clean error instead
  of a raw 413 if something bypasses the client-side resize (e.g. a
  direct API call).

## Project layout

```
id_screening_vercel/
├── api/
│   ├── index.py            # Flask app — Vercel's entrypoint
│   └── templates/
│       └── index.html      # Frontend (resizes images before upload)
├── lib/
│   ├── __init__.py
│   ├── ocr.py               # OCR.space call + heuristic field parsing
│   ├── tamper.py             # ELA tamper scoring, in-memory
│   ├── face_match.py         # Haar cascade + histogram face similarity
│   └── verdict.py            # Combines signals into a decision
├── requirements.txt
└── README.md
```

## API

`POST /api/screen` — multipart form with `id_document` and `selfie`
file fields. Returns extracted fields, a tamper score, a face
similarity result, and an overall verdict (`PASS` /
`FLAG_FOR_REVIEW` / `REJECT`).

## Known limitations

- **Face matching is a rough approximation** (grayscale histogram
  correlation on a Haar-cascade face crop), not true face-embedding
  matching. It's sensitive to lighting, angle, and compression in ways
  a real face-recognition model isn't — treat `similarity`/`match` as
  a demo-grade signal, not biometric verification.
- **ELA tamper detection is a weak, noisy signal** — many legitimate
  images (anything re-saved/re-compressed, e.g. sent through
  messaging apps) will trigger a false positive.
- **OCR field extraction is heuristic** (regex + "all-caps line =
  name"), not a real document parser — always show `raw_ocr_text`
  alongside extracted fields for a human reviewer.
- **No authentication or rate limiting** on `/api/screen` — anyone
  with the URL can call it (and burn through your OCR.space quota).
- **ID and selfie images are sent to a third-party OCR API**
  (OCR.space) — review their data-retention policy before sending any
  real user documents through this.
- The client-side resize keeps typical uploads under Vercel's limit
  but isn't a hard guarantee for every possible image (e.g. extremely
  large source dimensions) — the server-side 413 handler exists so
  that failure mode is at least clean rather than a raw error.
- No audit log of decisions — add one before handling real user data.
