"""Deterministic rule-based documentation flag detector for JourneyBrief.

Identifies document-level evidence issues, missing results, and documentation inconsistencies:
- Missing results: investigations ordered or pending without a corresponding completed report in uploaded set
- Missing source provenance (defensive check)
- Conflicting documented values across records for the same explicit entity/date
- Medication documentation mismatches across transitions of care
- Date inconsistencies (e.g. order date recorded after result date)

STRICT SAFETY BOUNDARY:
- All flags are strictly framed as 'documentation/information issues'.
- No clinical interpretation (never declare 'medical risk', 'danger', 'high risk',
  'patient deterioration', or 'treatment failure').
- Purely deterministic; NO Gemini/LLM calls.
"""

from datetime import date as dt_date
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.source import SourceReference


class DocumentationFlag(BaseModel):
    """An informational documentation or information-gap flag."""

    model_config = ConfigDict(extra="forbid")

    flag_id: str = Field(..., description="Unique deterministic identifier for the flag")
    flag_type: str = Field(
        ...,
        description="Type: missing_result, missing_source, conflicting_documented_value, medication_documentation_mismatch, date_inconsistency",
    )
    severity: str = Field(default="informational", description="Severity framing (strictly 'informational')")
    title: str = Field(..., description="Concise non-clinical factual title")
    description: str = Field(..., description="Documented factual explanation of the documentation issue")
    category: str = Field(..., description="Domain category: investigations, laboratory, medications, dates, provenance")
    sources: List[SourceReference] = Field(
        default_factory=list,
        description="All source document references relevant to this flag",
    )
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Deterministic contextual attributes")


class PatientFlags(BaseModel):
    """Collection of detected documentation flags for a patient journey."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    total_flags: int
    flag_types_present: List[str]
    flags: List[DocumentationFlag]


def _normalize_str(text: Optional[str]) -> str:
    """Normalize string for robust identity matching."""
    if not text:
        return ""
    return " ".join(str(text).strip().lower().split())


class FlagDetector:
    """Deterministic rule-based detector for documentation gaps and inconsistencies."""

    def __init__(self, structured_dir: Path) -> None:
        self.structured_dir = Path(structured_dir)

    def load_documents(self) -> List[Dict[str, Any]]:
        """Load all structured document JSON files in deterministic order."""
        if not self.structured_dir.is_dir():
            return []

        docs: List[Dict[str, Any]] = []
        for file_path in sorted(self.structured_dir.glob("*.json")):
            if file_path.stem.endswith("-gemini") or file_path.name.startswith("patient_"):
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and ("document_id" in data or "facts" in data):
                    docs.append(data)
            except Exception:
                continue
        # Deterministically sort by document_id
        docs.sort(key=lambda d: str(d.get("document_id", "")))
        return docs

    def detect_flags(self, patient_id: str = "SYN-CANCER-001") -> PatientFlags:
        """Evaluate structured documents and detect all documented gaps/inconsistencies."""
        docs = self.load_documents()
        flags: List[DocumentationFlag] = []
        flag_counter = 0

        # Collect all facts across documents
        all_investigations: List[Dict[str, Any]] = []
        all_labs: List[Dict[str, Any]] = []
        all_meds: List[Dict[str, Any]] = []
        all_imaging: List[Dict[str, Any]] = []
        all_procedures: List[Dict[str, Any]] = []
        all_pathology: List[Dict[str, Any]] = []

        for d in docs:
            facts = d.get("facts", {})
            all_investigations.extend(facts.get("investigations", []))
            all_labs.extend(facts.get("laboratory_results", []))
            all_meds.extend(facts.get("medications", []))
            all_imaging.extend(facts.get("imaging_reports", []))
            all_procedures.extend(facts.get("procedures", []))
            all_pathology.extend(facts.get("pathology_findings", []))

            # B. Defensive Check: Missing Source Provenance
            for cat, items in facts.items():
                if isinstance(items, list):
                    for idx, item in enumerate(items):
                        if isinstance(item, dict):
                            src = item.get("source")
                            if not src or not isinstance(src, dict) or not src.get("document_id") or not src.get("file_name"):
                                flag_counter += 1
                                flags.append(
                                    DocumentationFlag(
                                        flag_id=f"flag-source-{flag_counter}",
                                        flag_type="missing_source",
                                        severity="informational",
                                        title=f"Missing Source Reference in {cat}",
                                        description=f"Structured item in {cat} at index {idx} in {d.get('document_id')} is missing complete source provenance.",
                                        category="provenance",
                                        sources=[],
                                    )
                                )

        # A. Missing Result: Investigations ordered/pending without corresponding completed result
        # Index all completed imaging, pathology, and lab modalities
        completed_imaging_keywords = [
            _normalize_str(img.get("modality")) for img in all_imaging if img.get("modality")
        ]
        completed_inv_names = [
            _normalize_str(inv.get("investigation_name"))
            for inv in all_investigations
            if inv.get("status") in ("completed", "result_available", "result_documented")
        ]
        has_lab_results = len(all_labs) > 0
        has_pathology_results = len(all_pathology) > 0

        for inv in all_investigations:
            status = _normalize_str(inv.get("status"))
            inv_name = inv.get("investigation_name", "Investigation")
            norm_name = _normalize_str(inv_name)

            if status in ("ordered", "pending"):
                # Check if a completed result exists for this investigation
                has_completed = False
                for c_name in completed_inv_names:
                    if norm_name in c_name or c_name in norm_name:
                        has_completed = True
                        break

                if not has_completed:
                    # Check imaging reports
                    for img_kw in completed_imaging_keywords:
                        if (
                            ("mammogram" in norm_name and "mammogram" in img_kw)
                            or ("ultrasound" in norm_name and "ultrasound" in img_kw)
                            or ("mri" in norm_name and "mri" in img_kw)
                            or ("ct" in norm_name and "ct" in img_kw)
                            or ("simulation" in norm_name and any(k in img_kw for k in ["ct", "scan", "simulation"]))
                        ):
                            has_completed = True
                            break

                if not has_completed and ("biopsy" in norm_name or "pathology" in norm_name):
                    if has_pathology_results:
                        has_completed = True

                if not has_completed and any(k in norm_name for k in ["laboratory", "lab", "blood", "cbc", "cmp"]):
                    if has_lab_results:
                        has_completed = True

                if not has_completed:
                    flag_counter += 1
                    src_ref = SourceReference.model_validate(inv["source"]) if "source" in inv else None
                    flags.append(
                        DocumentationFlag(
                            flag_id=f"flag-missing-result-{flag_counter}",
                            flag_type="missing_result",
                            severity="informational",
                            title=f"Documented Order Awaiting Result: {inv_name}",
                            description=(
                                f"Investigation '{inv_name}' is documented as {status}"
                                f"{' on ' + str(inv.get('ordered_date')) if inv.get('ordered_date') else ''}. "
                                "Result not found in currently processed records."
                            ),
                            category="investigations",
                            sources=[src_ref] if src_ref else [],
                            metadata={"investigation_name": inv_name, "documented_status": status},
                        )
                    )

        # C. Conflicting Documented Values: Same explicit test on the exact same date with different values
        labs_by_test_date: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
        for lab in all_labs:
            t_name = _normalize_str(lab.get("test_name"))
            d_str = str(lab.get("date") or "")
            if t_name and d_str:
                labs_by_test_date.setdefault((t_name, d_str), []).append(lab)

        for (norm_test, d_str), group in labs_by_test_date.items():
            if len(group) >= 2:
                values_seen = set()
                sources: List[SourceReference] = []
                for entry in group:
                    val_unit = f"{entry.get('value')} {entry.get('unit') or ''}".strip()
                    values_seen.add(val_unit)
                    if "source" in entry:
                        sources.append(SourceReference.model_validate(entry["source"]))

                if len(values_seen) > 1:
                    flag_counter += 1
                    flags.append(
                        DocumentationFlag(
                            flag_id=f"flag-conflict-value-{flag_counter}",
                            flag_type="conflicting_documented_value",
                            severity="informational",
                            title=f"Conflicting Documented Values for {norm_test.title()}",
                            description=(
                                f"Different documented values ({', '.join(sorted(values_seen))}) were recorded for "
                                f"'{norm_test.title()}' on the same date ({d_str}) across uploaded records."
                            ),
                            category="laboratory",
                            sources=sources,
                            metadata={"test_name": norm_test, "date": d_str, "values": list(values_seen)},
                        )
                    )

        # D. Medication Documentation Mismatch
        # Track medications started vs documented across transitions of care
        meds_by_name: Dict[str, List[Dict[str, Any]]] = {}
        for med in all_meds:
            m_name = _normalize_str(med.get("medicine_name"))
            if m_name:
                meds_by_name.setdefault(m_name, []).append(med)

        for norm_med, med_entries in meds_by_name.items():
            statuses_recorded = {m.get("status") for m in med_entries if m.get("status")}
            # If a medication has multiple differing documented statuses across documents
            if len(statuses_recorded) > 1:
                sources = [SourceReference.model_validate(m["source"]) for m in med_entries if "source" in m]
                flag_counter += 1
                flags.append(
                    DocumentationFlag(
                        flag_id=f"flag-med-mismatch-{flag_counter}",
                        flag_type="medication_documentation_mismatch",
                        severity="informational",
                        title=f"Medication Status Transition Documented: {norm_med.title()}",
                        description=(
                            f"Medication '{norm_med.title()}' is documented with multiple status entries "
                            f"({', '.join(sorted(str(s) for s in statuses_recorded))}) across different care encounters. "
                            "No inference is made regarding medication administration."
                        ),
                        category="medications",
                        sources=sources,
                        metadata={"medicine_name": norm_med, "statuses": list(statuses_recorded)},
                    )
                )

        # E. Date Inconsistency: Investigation ordered_date > result_date or invalid chronology
        for inv in all_investigations:
            ord_d = inv.get("ordered_date")
            res_d = inv.get("result_date")
            if ord_d and res_d:
                try:
                    if str(ord_d) > str(res_d):
                        flag_counter += 1
                        src_ref = SourceReference.model_validate(inv["source"]) if "source" in inv else None
                        flags.append(
                            DocumentationFlag(
                                flag_id=f"flag-date-inconsistent-{flag_counter}",
                                flag_type="date_inconsistency",
                                severity="informational",
                                title=f"Inconsistent Chronology for {inv.get('investigation_name')}",
                                description=(
                                    f"Documented ordered date ({ord_d}) is recorded after result date ({res_d}) "
                                    f"for investigation '{inv.get('investigation_name')}'."
                                ),
                                category="dates",
                                sources=[src_ref] if src_ref else [],
                                metadata={"ordered_date": str(ord_d), "result_date": str(res_d)},
                            )
                        )
                except Exception:
                    pass

        # Sort flags deterministically by flag_type then flag_id
        flags.sort(key=lambda f: (f.flag_type, f.flag_id))
        flag_types = sorted(list({f.flag_type for f in flags}))

        return PatientFlags(
            patient_id=patient_id,
            total_flags=len(flags),
            flag_types_present=flag_types,
            flags=flags,
        )

    def generate_markdown(self, flags_data: PatientFlags) -> str:
        """Render human-readable Markdown summary of all documentation flags."""
        lines = [
            "# Documentation & Information Flags",
            "",
            f"- **Patient ID:** `{flags_data.patient_id}`",
            f"- **Total Flags Identified:** {flags_data.total_flags}",
            f"- **Flag Types Present:** {', '.join(f'`{t}`' for t in flags_data.flag_types_present) if flags_data.flag_types_present else 'None'}",
            "",
            "> [!NOTE]",
            "> All flags are strictly framed as **documentation and information-gap notifications**.",
            "> JourneyBrief records documentation observations only and does not perform clinical triage or score medical severity.",
            "",
            "---",
            "",
        ]

        if not flags_data.flags:
            lines.append("No documentation gaps or inconsistencies identified in the uploaded documents.")
            lines.append("")
            return "\n".join(lines)

        current_type: Optional[str] = None
        for flg in flags_data.flags:
            if flg.flag_type != current_type:
                current_type = flg.flag_type
                type_display = current_type.replace("_", " ").title()
                lines.append(f"## Flag Category: {type_display}")
                lines.append("")

            lines.append(f"### [{flg.severity.upper()}] {flg.title}")
            lines.append(f"- **Description:** {flg.description}")
            if flg.sources:
                src_list = [f"{s.document_id} (p. {s.page_number})" for s in flg.sources]
                lines.append(f"- **Relevant Sources:** {', '.join(src_list)}")
            lines.append("")

        return "\n".join(lines)

    def save_flags(
        self,
        output_dir: Path,
        patient_id: str = "SYN-CANCER-001",
        filename_prefix: str = "patient_001",
    ) -> Tuple[Path, Path]:
        """Save detected flags to JSON and Markdown artifacts."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        flags = self.detect_flags(patient_id=patient_id)

        json_path = out_dir / f"{filename_prefix}_flags.json"
        json_path.write_text(json.dumps(flags.model_dump(mode="json"), indent=2), encoding="utf-8")

        md_path = out_dir / f"{filename_prefix}_flags.md"
        md_text = self.generate_markdown(flags)
        md_path.write_text(md_text, encoding="utf-8")

        return json_path, md_path
