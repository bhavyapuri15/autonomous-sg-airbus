"""Answer-level gating and conversion to schema objects."""
from __future__ import annotations

from backend.api.schemas import Claim, RejectedClaim, VerificationInfo
from .citations import (DraftClaim, VerifiedClaim, contains_injection_markers, verify_claim)
from .normalize import normalize

WARN_DROPPED = "Some generated statements could not be verified and were removed."
WARN_INJECTION = "Source text contains instruction-like content; it was treated strictly as data."


def verify_answer(claims, retrieved, model_index=None, judge=None, mode="llm"):
    seen, uniq = set(), []
    for c in claims:
        key = (normalize(c.text), c.chunk_id, normalize(c.quote), tuple(c.quotes or ()))
        tkey = normalize(c.text)
        if key in seen or tkey in {k[0] for k in seen}:
            continue
        seen.add(key)
        uniq.append(c)
    verified: list[Claim] = []
    rejected: list[RejectedClaim] = []
    for c in uniq:
        r = verify_claim(c, retrieved, model_index, judge)
        if isinstance(r, VerifiedClaim):
            verified.append(r.claim)
        else:
            rejected.append(r)
    warnings: list[str] = []
    if uniq and len(rejected) * 2 > len(uniq):
        warnings.append(WARN_DROPPED)
    if any(contains_injection_markers(ch.text) for ch in retrieved.values()):
        warnings.append(WARN_INJECTION)
    info = VerificationInfo(mode=mode, claims_generated=len(claims),
                            claims_verified=len(verified), claims_rejected=rejected)
    return verified, info, warnings
