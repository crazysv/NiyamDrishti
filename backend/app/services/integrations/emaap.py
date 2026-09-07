"""Adapter service for the National Legal Metrology eMaap Portal (E4-05, ADR-020).

Supports dual-mode operation:
1. Live REST API integration when EMAAP_API_URL and EMAAP_API_KEY are configured.
2. High-fidelity Sandbox / Mock environment providing realistic LMPC registration lookups
   and statutory enforcement docket creation when unconfigured or in development/offline mode.
"""

from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.models.base import Inspection, User
from app.schemas.emaap import (
    EMaapAdapterStatusResponse,
    EMaapDocketSubmissionResponse,
    EMaapRegistrationResponse,
)
from app.schemas.evidence_verification import EvidenceVerificationResult

# Seeded sandbox database representing official LMPC registrations
SANDBOX_REGISTRATIONS: dict[str, dict[str, Any]] = {
    "REG-LMPC-2023-DL-0012": {
        "status": "ACTIVE",
        "entity_name": "Hindustan Unilever Limited",
        "entity_type": "Manufacturer / Packer",
        "registered_address": "B.D. Sawant Marg, Chakala, Andheri (East), Mumbai 400099",
        "valid_until": "2028-12-31",
        "categories": ["packaged_food", "cosmetics", "household_goods"],
    },
    "REG-LMPC-2024-MH-0841": {
        "status": "ACTIVE",
        "entity_name": "ITC Limited - Foods Division",
        "entity_type": "Manufacturer / Packer",
        "registered_address": "Virginia House, 37 J.L. Nehru Road, Kolkata 700071",
        "valid_until": "2029-06-30",
        "categories": ["packaged_food", "commodities"],
    },
    "REG-LMPC-2022-KA-0319": {
        "status": "ACTIVE",
        "entity_name": "Parle Products Private Limited",
        "entity_type": "Manufacturer / Packer",
        "registered_address": "North Level Crossing, Vile Parle (East), Mumbai 400057",
        "valid_until": "2027-04-15",
        "categories": ["packaged_food", "confectionery"],
    },
    "REG-LMPC-2020-DL-9941": {
        "status": "EXPIRED",
        "entity_name": "Old Mill Spices Private Limited",
        "entity_type": "Packer",
        "registered_address": "Plot 14, Okhla Industrial Area Phase III, New Delhi 110020",
        "valid_until": "2024-01-01",
        "categories": ["packaged_food"],
    },
    "REG-LMPC-2021-GJ-4412": {
        "status": "SUSPENDED",
        "entity_name": "Sunrise Electricals & Appliances LLP",
        "entity_type": "Importer",
        "registered_address": "GIDC Estate, Makarpura, Vadodara, Gujarat 390010",
        "valid_until": "2026-11-30",
        "categories": ["electronics"],
    },
}


class EMaapAdapter:
    """Adapter for interacting with the National Legal Metrology eMaap system."""

    @property
    def is_live(self) -> bool:
        """Indicates whether live eMaap API credentials and endpoint are provisioned."""
        return bool(settings.EMAAP_API_URL and settings.EMAAP_API_KEY)

    def get_status(self) -> EMaapAdapterStatusResponse:
        """Returns the operational mode and configuration of the eMaap adapter."""
        return EMaapAdapterStatusResponse(
            is_enabled=True,
            is_sandbox=not self.is_live,
            api_endpoint=settings.EMAAP_API_URL if self.is_live else None,
            version="1.0.0",
        )

    async def verify_packer_registration(
        self,
        registration_number: str,
        company_name: str | None = None,
    ) -> EMaapRegistrationResponse:
        """
        Validates manufacturer/packer/importer registration under Rule 27 of LMPC Rules.
        Queries live eMaap API when configured; otherwise resolves against local sandbox registry.
        """
        reg_key = registration_number.strip().upper()

        if self.is_live:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.EMAAP_API_KEY}",
                    "Accept": "application/json",
                }
                async with httpx.AsyncClient(timeout=settings.EMAAP_TIMEOUT_SECONDS) as client:
                    resp = await client.get(
                        f"{settings.EMAAP_API_URL.rstrip('/')}/v1/registrations/{reg_key}",
                        headers=headers,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return EMaapRegistrationResponse(
                            is_registered=data.get("is_registered", True),
                            registration_number=reg_key,
                            status=data.get("status", "ACTIVE"),
                            entity_name=data.get("entity_name"),
                            entity_type=data.get("entity_type"),
                            registered_address=data.get("registered_address"),
                            valid_until=data.get("valid_until"),
                            authorized_commodity_categories=data.get("authorized_commodity_categories", []),
                            is_sandbox=False,
                            verified_at=datetime.now(timezone.utc),
                        )
                    elif resp.status_code == 404:
                        return EMaapRegistrationResponse(
                            is_registered=False,
                            registration_number=reg_key,
                            status="NOT_FOUND",
                            is_sandbox=False,
                            verified_at=datetime.now(timezone.utc),
                        )
            except Exception:
                # If network fail on live endpoint, fall through to sandbox fallback
                pass

        # Sandbox resolution
        record = SANDBOX_REGISTRATIONS.get(reg_key)
        if record:
            return EMaapRegistrationResponse(
                is_registered=record["status"] in ("ACTIVE", "EXPIRED", "SUSPENDED"),
                registration_number=reg_key,
                status=record["status"],
                entity_name=record["entity_name"],
                entity_type=record["entity_type"],
                registered_address=record["registered_address"],
                valid_until=record["valid_until"],
                authorized_commodity_categories=record["categories"],
                is_sandbox=True,
                verified_at=datetime.now(timezone.utc),
            )

        # Company name fallback search in sandbox
        if company_name:
            query = company_name.lower().strip()
            for k, rec in SANDBOX_REGISTRATIONS.items():
                if query in rec["entity_name"].lower():
                    return EMaapRegistrationResponse(
                        is_registered=rec["status"] in ("ACTIVE", "EXPIRED", "SUSPENDED"),
                        registration_number=k,
                        status=rec["status"],
                        entity_name=rec["entity_name"],
                        entity_type=rec["entity_type"],
                        registered_address=rec["registered_address"],
                        valid_until=rec["valid_until"],
                        authorized_commodity_categories=rec["categories"],
                        is_sandbox=True,
                        verified_at=datetime.now(timezone.utc),
                    )

        # Not found in registry
        return EMaapRegistrationResponse(
            is_registered=False,
            registration_number=reg_key,
            status="NOT_FOUND",
            is_sandbox=True,
            verified_at=datetime.now(timezone.utc),
        )

    async def submit_enforcement_docket(
        self,
        inspection: Inspection,
        officer: User,
        verification_result: EvidenceVerificationResult,
        officer_notes: str | None = None,
        priority: str = "ROUTINE",
    ) -> EMaapDocketSubmissionResponse:
        """
        Compiles and submits a statutory enforcement dossier to eMaap containing:
        - Digital inspection certificate
        - SHA-256 cryptographic evidence fingerprints
        - Rule-by-rule violation citations under Legal Metrology Act, 2009 Section 36
        """
        region_code = inspection.region[:3].upper() if inspection.region else "DEL"
        date_stamp = datetime.now(timezone.utc).strftime("%Y%m")
        docket_id = f"EMAAP-ENF-{region_code}-{date_stamp}-{str(inspection.id)[:6].upper()}"

        docket_payload = {
            "docket_id": docket_id,
            "inspection_id": str(inspection.id),
            "priority": priority,
            "officer": {
                "id": str(officer.id),
                "name": officer.full_name,
                "role": officer.role,
                "region": officer.region,
                "email": officer.email,
            },
            "commodity_category": inspection.commodity_category,
            "rule_pack_version": inspection.rule_pack_version,
            "evidence_chain_hash": verification_result.evidence_chain_hash,
            "audit_chain_intact": verification_result.audit_chain_intact,
            "photographic_evidence": [
                {
                    "image_id": str(rec.image_id),
                    "role": rec.image_role,
                    "sha256": rec.sha256_hash,
                    "integrity": rec.file_integrity,
                }
                for rec in verification_result.image_records
            ],
            "violations": [
                {
                    "rule_id": v.rule_id,
                    "severity": v.severity,
                    "description": v.description,
                    "penalty_clause": "Legal Metrology Act, 2009 Section 36",
                }
                for v in inspection.violations
            ],
            "officer_notes": officer_notes,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }

        if self.is_live:
            try:
                headers = {
                    "Authorization": f"Bearer {settings.EMAAP_API_KEY}",
                    "Content-Type": "application/json",
                }
                async with httpx.AsyncClient(timeout=settings.EMAAP_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        f"{settings.EMAAP_API_URL.rstrip('/')}/v1/enforcement/dockets",
                        json=docket_payload,
                        headers=headers,
                    )
                    if resp.status_code in (200, 201):
                        data = resp.json()
                        return EMaapDocketSubmissionResponse(
                            docket_id=data.get("docket_id", docket_id),
                            inspection_id=inspection.id,
                            status="SUBMITTED",
                            submitted_at=datetime.now(timezone.utc),
                            evidence_chain_hash=verification_result.evidence_chain_hash,
                            violations_count=len(inspection.violations),
                            photographs_count=len(verification_result.image_records),
                            portal_tracking_url=data.get(
                                "portal_tracking_url",
                                f"https://emaap.gov.in/enforcement/dockets/{docket_id}",
                            ),
                            is_sandbox=False,
                            message="Enforcement docket successfully filed into National eMaap Portal.",
                        )
            except Exception:
                # Network or endpoint unavailable, fall through to acknowledged sandbox response
                pass

        # Sandbox / Fallback acknowledged response
        return EMaapDocketSubmissionResponse(
            docket_id=docket_id,
            inspection_id=inspection.id,
            status="ACKNOWLEDGED",
            submitted_at=datetime.now(timezone.utc),
            evidence_chain_hash=verification_result.evidence_chain_hash,
            violations_count=len(inspection.violations),
            photographs_count=len(verification_result.image_records),
            portal_tracking_url=f"https://emaap.gov.in/enforcement/dockets/{docket_id}",
            is_sandbox=True,
            message="Enforcement dossier registered in eMaap adapter sandbox queue.",
        )
