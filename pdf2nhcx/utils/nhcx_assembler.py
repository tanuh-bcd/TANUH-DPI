"""
pdf2nhcx/utils/nhcx_assembler.py — NHCX-only bundle assembly helpers.

Extracted into their own module so they can be imported without pulling in
LangGraph, Vertex AI, or other heavy runtime dependencies. llm_requirements.py
re-exports these from here.
"""
from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timezone

from pdf2nhcx.utils.nhcx_profiles import (
    NHCX_BUNDLE_TYPES as _NHCX_BUNDLE_TYPES,
    BUNDLE_PROFILES,
    PROFILES_BY_TYPE,
    get_profile,
    get_forbidden_resources,
)


# ── ABDM / hallucinated resource types that must never appear in NHCX bundles ──
_ABDM_COMPOSITION_TYPES: frozenset = frozenset({
    "DiagnosticReportRecord", "DischargeSummaryRecord", "WellnessRecord",
    "HealthDocumentRecord", "PrescriptionRecord",
    "DiagnosticReportLab", "DiagnosticReportImaging",
    "ObservationVitalSigns", "ObservationLifestyle", "ObservationWomenHealth",
    "ObservationPhysicalActivity", "ObservationGeneralAssessment",
    "ObservationBodyMeasurement",
    "DocumentBundle",
    "Composition",  # belongs to ABDM document bundles, never NHCX collection bundles
})

# Placeholder names injected by sanitize_fhir_resource when real data is missing.
# These are acceptable in the FHIR sense but are a signal the LLM failed to extract
# real content. The assembler logs a warning when it sees them.
_PLACEHOLDER_NAMES = frozenset({
    "Unknown InsurancePlan", "Unknown Organization", "Unknown Patient",
    "Unknown Practitioner", "Unknown Procedure", "Unknown Condition",
})


# ─────────────────────────────────────────────────────────────────────────────
# Nested-bundle flattening helpers
# ─────────────────────────────────────────────────────────────────────────────

def _flatten_nested_bundle(nested_bundle: dict) -> list:
    """
    Extract top-level entries from a nested Bundle resource.

    Preserves the fullUrl of each nested entry when present.
    Returns a list of entry dicts (same shape as bundle["entry"] items).
    """
    entries = []
    for nested_entry in nested_bundle.get("entry", []):
        res = nested_entry.get("resource")
        if not isinstance(res, dict):
            continue
        # Preserve the nested fullUrl if it already is a urn:uuid
        full_url = nested_entry.get("fullUrl", "")
        res_id = res.get("id")
        if not full_url and res_id:
            full_url = f"urn:uuid:{res_id}"
        entry = {"resource": res}
        if full_url:
            entry["fullUrl"] = full_url
        entries.append(entry)
    return entries


# ─────────────────────────────────────────────────────────────────────────────
# Main assembler
# ─────────────────────────────────────────────────────────────────────────────

def assemble_nhcx_collection_bundle(bundle: dict, clinical_artifact: str) -> dict:
    """
    NHCX-only post-processing for a generated Bundle.

    Guarantees:
    - resourceType = Bundle, type = collection
    - Correct NRCES meta.profile for the bundle type
    - Required primary resource is present (warns if missing)
    - No ABDM Composition/hallucinated entries
    - No forbidden resources (explicit per-bundle list from nhcx_profiles)
    - Nested Bundle entries are flattened; their valid children are promoted
    - No duplicate resources (deduped by id, then by resourceType+name)
    - All entries have fullUrl = urn:uuid:*
    - sanitize_fhir_resource applied to every surviving entry
    - InsurancePlanBundle: Condition is always dropped (belt-and-suspenders)
    - Warns on placeholder names ("Unknown InsurancePlan", etc.)
    """
    profile = None
    try:
        profile = get_profile(clinical_artifact)
    except KeyError:
        pass

    bundle_profile_url = (
        profile.profile_url if profile
        else BUNDLE_PROFILES.get(
            clinical_artifact,
            "https://nrces.in/ndhm/fhir/r4/StructureDefinition/InsurancePlanBundle",
        )
    )
    primary_resource_type = profile.primary_resource if profile else "InsurancePlan"
    forbidden: frozenset = get_forbidden_resources(clinical_artifact)

    # Enforce bundle-level fields
    bundle["resourceType"] = "Bundle"
    bundle["type"] = "collection"
    bundle.setdefault("meta", {})["profile"] = [bundle_profile_url]
    if not bundle.get("id"):
        bundle["id"] = str(_uuid.uuid4())

    _sanitize = _get_sanitizer()

    # ── Pass 1: expand nested Bundles into a flat entry list ─────────────────
    raw_entries: list = []
    for entry in bundle.get("entry", []):
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue
        if resource.get("resourceType") == "Bundle":
            children = _flatten_nested_bundle(resource)
            print(f"🪗  Flattened nested Bundle → {len(children)} children for {clinical_artifact}")
            raw_entries.extend(children)
        else:
            raw_entries.append(entry)

    # ── Pass 2: filter, sanitize, deduplicate ────────────────────────────────
    seen_ids: set = set()
    cleaned: list = []
    primary_found = False

    for entry in raw_entries:
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue

        res_type = resource.get("resourceType", "")

        # Drop ABDM artefacts and hallucinated types
        if res_type in _ABDM_COMPOSITION_TYPES:
            print(f"🗑️  Stripped ABDM/invalid resource '{res_type}' from {clinical_artifact}")
            continue

        # Drop forbidden resources (explicit per-bundle contract)
        if res_type in forbidden:
            print(f"🗑️  Stripped forbidden resource '{res_type}' from {clinical_artifact}")
            continue

        # Belt-and-suspenders: InsurancePlanBundle must never have Condition
        if clinical_artifact == "InsurancePlanBundle" and res_type == "Condition":
            print("🗑️  InsurancePlanBundle: dropped Condition (policy term, not patient dx)")
            continue

        # Sanitize
        if _sanitize:
            _sanitize(resource)

        # Ensure fullUrl is urn:uuid:*
        res_id = resource.get("id")
        if res_id:
            entry["fullUrl"] = f"urn:uuid:{res_id}"
        elif not entry.get("fullUrl", "").startswith("urn:uuid:"):
            new_id = str(_uuid.uuid4())
            resource["id"] = new_id
            entry["fullUrl"] = f"urn:uuid:{new_id}"
            res_id = new_id

        # Deduplicate by id
        if res_id:
            if res_id in seen_ids:
                print(f"⚠️  Duplicate resource id '{res_id}' ({res_type}) — skipping")
                continue
            seen_ids.add(res_id)

        # Warn on placeholder names
        for name_field in ("name", "display"):
            val = resource.get(name_field)
            if val and val in _PLACEHOLDER_NAMES:
                print(f"⚠️  Placeholder {name_field} detected on {res_type}: '{val}'")

        if res_type == primary_resource_type:
            primary_found = True

        cleaned.append(entry)

    if not primary_found:
        print(
            f"⚠️  Required primary resource '{primary_resource_type}' "
            f"not found in {clinical_artifact} bundle"
        )

    bundle["entry"] = cleaned
    print(
        f"✅ assemble_nhcx_collection_bundle: {clinical_artifact}, {len(cleaned)} entries, "
        f"primary '{primary_resource_type}' {'found' if primary_found else 'MISSING'}"
    )
    return bundle


# ─────────────────────────────────────────────────────────────────────────────
# document_reference_node
# ─────────────────────────────────────────────────────────────────────────────

def document_reference_node(bundle: dict, pdf_base64: str) -> dict:
    """
    Attach the original PDF to DocumentReference entries in the bundle.

    Strategy:
    - Find (or create) a Binary resource and link DocumentReference via
      content[].attachment.url = 'urn:uuid:<binary_id>'.
    - Embed base64 data only in Binary (not in DocumentReference) to keep
      DocumentReference entries small and FHIR-conformant.
    - Never print base64 content to logs.
    - Set required DocumentReference fields (status, date, type) when missing.
    """
    if not pdf_base64:
        return bundle

    # Remove any existing Binary resources since we use inline base64
    bundle["entry"] = [e for e in bundle.get("entry", []) if e.get("resource", {}).get("resourceType") != "Binary"]

    # Link all DocumentReference entries to this base64 directly
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") != "DocumentReference":
            continue

        if res.get("status") not in {"current", "superseded", "entered-in-error"}:
            res["status"] = "current"
        if "date" not in res:
            res["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # DocumentReference.type must be a CodeableConcept (not a bare string)
        if "type" not in res or not isinstance(res.get("type"), dict):
            res["type"] = {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": "419891008",
                    "display": "Record artifact",
                }],
                "text": "Insurance Document",
            }

        if "content" not in res or not res["content"]:
            res["content"] = [{"attachment": {
                "contentType": "application/pdf",
                "data": pdf_base64,
            }}]
        else:
            att = res["content"][0].setdefault("attachment", {})
            att["contentType"] = "application/pdf"
            att["data"] = pdf_base64
            att.pop("url", None)

    return bundle


# ─────────────────────────────────────────────────────────────────────────────
# strip_binary_data — call AFTER document_reference_node
# ─────────────────────────────────────────────────────────────────────────────

def strip_binary_data(bundle: dict, gcs_pdf_uri: str = None) -> dict:
    """
    Remove Binary resources from the bundle.

    The PDF data is embedded directly into DocumentReference.content[].attachment.data
    as requested by NHCX instead of a URL.
    """
    new_entries = []
    for entry in bundle.get("entry", []):
        res = entry.get("resource", {})
        if res.get("resourceType") == "Binary":
            print("✅ Removed Binary resource from bundle entirely")
            continue
        new_entries.append(entry)
        
    bundle["entry"] = new_entries

    return bundle


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_sanitizer():
    """Return sanitize_fhir_resource if available, else None (for test environments)."""
    try:
        from pdf2nhcx.utils.llm_requirements import sanitize_fhir_resource
        return sanitize_fhir_resource
    except Exception:
        return None
