"""
Combine tamper-check and face-match signals into an overall decision.
"""


def overall_verdict(tamper: dict, face: dict) -> dict:
    reasons = []
    risk_points = 0

    if tamper["verdict"] == "possible_recompression_artifact":
        # Weighted by the underlying score rather than a flat penalty,
        # since ELA is a weak/noisy signal on its own.
        risk_points += min(tamper["tamper_score"], 100) * 0.4
        reasons.append("Document shows possible recompression artifacts (ELA)")

    if not face.get("match"):
        risk_points += 50
        reasons.append(f"Face check issue: {face.get('reason', 'faces do not match closely enough')}")
    elif face.get("similarity", 0) < 70:
        risk_points += 15
        reasons.append("Face similarity is low even though it cleared the threshold; consider manual review")

    risk_points = min(round(risk_points), 100)
    decision = "PASS" if risk_points == 0 else ("FLAG_FOR_REVIEW" if risk_points < 100 else "REJECT")

    return {"decision": decision, "risk_score": risk_points, "reasons": reasons}
