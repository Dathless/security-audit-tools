from __future__ import annotations

import hashlib
import json

IDENTITY_VERSION = 2
ASSESSMENT_VERSION = 2


def endpoint_key(detail: dict) -> str:
    return json.dumps(["endpoint-v2", detail["protocol"], detail["family"], detail["listener"], detail["port"]], separators=(",", ":"), ensure_ascii=False)


def complete_identity(detail: dict) -> bool:
    owners = detail.get("owners", [])
    return bool(owners) and all(owner.get("exe") and owner.get("username") for owner in owners)


def review_fingerprint(detail: dict, severity: str) -> str:
    owners = sorted({(owner.get("exe") or "", owner.get("username") or "") for owner in detail.get("owners", [])})
    evidence = [endpoint_key(detail), owners, detail.get("assessment_version"), severity, sorted(detail.get("reasons", []))]
    return hashlib.sha256(json.dumps(evidence, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def observation_signature(detail: dict, severity: str) -> str:
    # Metadata recovery is a visible change, while process restarts are not.
    owners = sorted({(owner.get("name") or "", owner.get("exe") or "", owner.get("username") or "") for owner in detail.get("owners", [])})
    return json.dumps([owners, severity, sorted(detail.get("reasons", []))], ensure_ascii=False)
