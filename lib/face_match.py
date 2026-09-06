"""
Face comparison via OpenCV Haar Cascade detection + grayscale
histogram correlation — chosen because it ships inside
opencv-python-headless with no dlib/C++ compilation step, which is
what makes `face_recognition` unreliable to build on Vercel.

IMPORTANT: this is a rough similarity heuristic, not true face
embedding matching. Histogram correlation is sensitive to lighting,
angle, and image compression in ways a real face-embedding model is
not. Treat `match`/`similarity` here as a weak signal for a demo, not
a biometric verification result.
"""
import cv2
import numpy as np

FACE_CASCADE = cv2.CascadeClassifier(
    cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
)


def _decode_image(image_bytes: bytes):
    arr = np.frombuffer(image_bytes, np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)


def _largest_face(img):
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return gray[y:y + h, x:x + w]


def compare_faces(id_bytes: bytes, selfie_bytes: bytes) -> dict:
    id_img = _decode_image(id_bytes)
    selfie_img = _decode_image(selfie_bytes)

    id_face = _largest_face(id_img)
    selfie_face = _largest_face(selfie_img)

    if id_face is None:
        return {"match": False, "reason": "no_face_detected_on_id", "similarity": 0.0}
    if selfie_face is None:
        return {"match": False, "reason": "no_face_detected_in_selfie", "similarity": 0.0}

    size = (150, 150)
    id_resized = cv2.resize(id_face, size)
    selfie_resized = cv2.resize(selfie_face, size)

    id_hist = cv2.calcHist([id_resized], [0], None, [256], [0, 256])
    selfie_hist = cv2.calcHist([selfie_resized], [0], None, [256], [0, 256])
    cv2.normalize(id_hist, id_hist)
    cv2.normalize(selfie_hist, selfie_hist)

    correlation = cv2.compareHist(id_hist, selfie_hist, cv2.HISTCMP_CORREL)  # -1..1
    similarity = round(max(correlation, 0) * 100, 1)
    is_match = similarity > 55  # heuristic threshold — tune against real samples

    return {
        "match": bool(is_match),
        "similarity": similarity,
        "note": "Histogram-based approximation, not true face-embedding matching",
    }
