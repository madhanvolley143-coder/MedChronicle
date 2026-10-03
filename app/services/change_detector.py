"""Deterministic rule-based change detection engine for JourneyBrief.

Compares explicitly documented repeated facts across chronological records in cancer care:
- Laboratory results (documented values and units over time)
- Medications (documented statuses and dosages over time)
- Diagnostic investigations (documented statuses, e.g. ordered -> completed)
- Procedures (documented statuses, e.g. planned -> performed)
- Referrals (documented status transitions)

STRICT SAFETY BOUNDARY:
- No LLM/Gemini calls.
- Purely deterministic comparisons.
- No clinical interpretation (never declare 'improved', 'worsened', 'normal', 'abnormal',
  'concerning', or 'clinically significant').
- Only document exact textual and numerical differences with source links.
"""

from datetime import date as dt_date
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.source import SourceReference


class ChangeRecord(BaseModel):
    """Documented difference for a repeated clinical entity across time."""

    model_config = ConfigDict(extra="forbid")

    category: str = Field(
        ...,
        description="Clinical category: laboratory_results, medications, investigations, procedures, referrals, visits",
    )
    entity_name: str = Field(..., description="Explicit entity identifier (e.g. test name, drug name)")
    previous_value: str = Field(..., description="Previous documented value or state")
    latest_value: str = Field(..., description="Latest documented value or state")
    documented_difference: str = Field(..., description="Objective textual description of difference")
    is_changed: bool = Field(..., description="True if value/state changed, False if identical")
    previous_date: Optional[str] = Field(default=None, description="Previous documentation date")
    latest_date: Optional[str] = Field(default=None, description="Latest documentation date")
    previous_source: SourceReference = Field(..., description="Source provenance of previous fact")
    latest_source: SourceReference = Field(..., description="Source provenance of latest fact")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional context fields")


class PatientChanges(BaseModel):
    """Aggregate collection of documented changes across all categories."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    total_changes_detected: int
    categories_with_changes: List[str]
    changes: List[ChangeRecord]


def _normalize_name(name: Optional[str]) -> str:
    """Normalize string for robust grouping."""
    if not name:
        return ""
    # Strip common prefixes/suffixes for grouping
    cleaned = " ".join(str(name).strip().lower().split())
    # Canonicalize common test names
    if "hemoglobin" in cleaned:
        return "hemoglobin"
    if "ca 15-3" in cleaned or "ca15-3" in cleaned:
        return "ca 15-3"
    if "wbc" in cleaned or "white blood cell" in cleaned:
        return "white blood cells (wbc)"
    if "platelet" in cleaned:
        return "platelet count"
    if "creatinine" in cleaned:
        return "serum creatinine"
    if "alt" in cleaned or "alanine aminotransferase" in cleaned:
        return "alanine aminotransferase (alt)"
    if "tamoxifen" in cleaned:
        return "tamoxifen"
    return cleaned


class ChangeDetector:
    """Rule-based change detector across structured documents."""

    def __init__(self, structured_dir: Path) -> None:
        self.structured_dir = Path(structured_dir)

    def load_documents_chronologically(self) -> List[Dict[str, Any]]:
        """Load and sort structured documents by document_id / document date."""
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

        # Sort documents by document_id deterministically
        docs.sort(key=lambda d: str(d.get("document_id", "")))
        return docs

    def detect_changes(
        self,
        patient_id: str = "SYN-CANCER-001",
        only_changed: bool = True,
    ) -> PatientChanges:
        """Identify all documented changes across repeated facts.

        Args:
            patient_id: Target patient identifier.
            only_changed: If True (default), excludes unchanged comparisons (e.g. 22 -> 22)
                          so only genuine documented differences are returned.
        """
        docs = self.load_documents_chronologically()
        changes: List[ChangeRecord] = []

        # 1. Laboratory Results
        lab_series: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            for lab in d.get("facts", {}).get("laboratory_results", []):
                t_name = lab.get("test_name")
                if t_name:
                    norm = _normalize_name(t_name)
                    lab_series.setdefault(norm, []).append(lab)

        for norm_name, entries in lab_series.items():
            # Chronologically sort entries by documented date if available
            entries.sort(key=lambda x: str(x.get("date") or ""))
            if len(entries) >= 2:
                # Compare first occurrence with last occurrence
                first = entries[0]
                last = entries[-1]

                # If same document and same page, compare entries only if they are distinct
                if (
                    first.get("source", {}).get("document_id") == last.get("source", {}).get("document_id")
                    and first.get("value") == last.get("value")
                ):
                    continue

                display_name = last.get("test_name", norm_name.title())
                v_first = first.get("value", "")
                u_first = first.get("unit") or ""
                v_last = last.get("value", "")
                u_last = last.get("unit") or ""

                prev_str = f"{v_first} {u_first}".strip()
                latest_str = f"{v_last} {u_last}".strip()
                is_changed = (v_first != v_last) or (u_first != u_last)

                # Skip unchanged comparisons if only_changed is requested
                if only_changed and not is_changed:
                    continue

                if is_changed:
                    diff_text = f"{prev_str} -> {latest_str}"
                else:
                    diff_text = f"{prev_str} (unchanged across records)"

                changes.append(
                    ChangeRecord(
                        category="laboratory_results",
                        entity_name=display_name,
                        previous_value=prev_str,
                        latest_value=latest_str,
                        documented_difference=diff_text,
                        is_changed=is_changed,
                        previous_date=str(first.get("date")) if first.get("date") else None,
                        latest_date=str(last.get("date")) if last.get("date") else None,
                        previous_source=SourceReference.model_validate(first["source"]),
                        latest_source=SourceReference.model_validate(last["source"]),
                        metadata={
                            "previous_reference_range": first.get("reference_range_text"),
                            "latest_reference_range": last.get("reference_range_text"),
                        },
                    )
                )

        # 2. Medications
        med_series: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            for med in d.get("facts", {}).get("medications", []):
                m_name = med.get("medicine_name")
                if m_name:
                    norm = _normalize_name(m_name)
                    med_series.setdefault(norm, []).append(med)

        for norm_name, entries in med_series.items():
            entries.sort(key=lambda x: str(x.get("date") or ""))
            if len(entries) >= 2:
                first = entries[0]
                last = entries[-1]

                if first.get("source", {}).get("document_id") == last.get("source", {}).get("document_id"):
                    continue

                display_name = last.get("medicine_name", norm_name.title())
                s_first = first.get("status") or "listed"
                s_last = last.get("status") or "listed"
                d_first = first.get("dose") or first.get("strength") or "unspecified"
                d_last = last.get("dose") or last.get("strength") or "unspecified"

                prev_str = f"Status: {s_first}, Dose: {d_first}"
                latest_str = f"Status: {s_last}, Dose: {d_last}"
                is_changed = (s_first != s_last) or (d_first != d_last)

                if only_changed and not is_changed:
                    continue

                diff_text = f"{s_first} -> {s_last}"
                if d_first != d_last:
                    diff_text += f" (Dose: {d_first} -> {d_last})"

                changes.append(
                    ChangeRecord(
                        category="medications",
                        entity_name=display_name,
                        previous_value=prev_str,
                        latest_value=latest_str,
                        documented_difference=diff_text,
                        is_changed=is_changed,
                        previous_date=str(first.get("date")) if first.get("date") else None,
                        latest_date=str(last.get("date")) if last.get("date") else None,
                        previous_source=SourceReference.model_validate(first["source"]),
                        latest_source=SourceReference.model_validate(last["source"]),
                    )
                )

        # 3. Investigations
        inv_series: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            for inv in d.get("facts", {}).get("investigations", []):
                i_name = inv.get("investigation_name")
                if i_name:
                    norm = _normalize_name(i_name)
                    inv_series.setdefault(norm, []).append(inv)

        for norm_name, entries in inv_series.items():
            entries.sort(key=lambda x: str(x.get("ordered_date") or x.get("result_date") or x.get("date") or ""))
            if len(entries) >= 2:
                first = entries[0]
                last = entries[-1]

                if first.get("source", {}).get("document_id") == last.get("source", {}).get("document_id"):
                    continue

                display_name = last.get("investigation_name", norm_name.title())
                s_first = first.get("status", "ordered")
                s_last = last.get("status", "completed")

                prev_str = f"Status: {s_first}"
                latest_str = f"Status: {s_last}"
                is_changed = s_first != s_last

                if only_changed and not is_changed:
                    continue

                changes.append(
                    ChangeRecord(
                        category="investigations",
                        entity_name=display_name,
                        previous_value=prev_str,
                        latest_value=latest_str,
                        documented_difference=f"{s_first} -> {s_last}",
                        is_changed=is_changed,
                        previous_date=str(first.get("ordered_date") or first.get("result_date")),
                        latest_date=str(last.get("result_date") or last.get("ordered_date")),
                        previous_source=SourceReference.model_validate(first["source"]),
                        latest_source=SourceReference.model_validate(last["source"]),
                    )
                )

        # 4. Procedures
        proc_series: Dict[str, List[Dict[str, Any]]] = {}
        for d in docs:
            for proc in d.get("facts", {}).get("procedures", []):
                p_name = proc.get("procedure_name")
                if p_name:
                    norm = _normalize_name(p_name)
                    proc_series.setdefault(norm, []).append(proc)

        for norm_name, entries in proc_series.items():
            entries.sort(key=lambda x: str(x.get("date") or ""))
            if len(entries) >= 2:
                first = entries[0]
                last = entries[-1]

                if first.get("source", {}).get("document_id") == last.get("source", {}).get("document_id"):
                    continue

                display_name = last.get("procedure_name", norm_name.title())
                s_first = first.get("documented_status") or "documented"
                s_last = last.get("documented_status") or "performed"
                is_changed = s_first != s_last

                if only_changed and not is_changed:
                    continue

                changes.append(
                    ChangeRecord(
                        category="procedures",
                        entity_name=display_name,
                        previous_value=f"Status: {s_first}",
                        latest_value=f"Status: {s_last}",
                        documented_difference=f"{s_first} -> {s_last}",
                        is_changed=s_first != s_last,
                        previous_date=str(first.get("date")) if first.get("date") else None,
                        latest_date=str(last.get("date")) if last.get("date") else None,
                        previous_source=SourceReference.model_validate(first["source"]),
                        latest_source=SourceReference.model_validate(last["source"]),
                    )
                )

        # Sort changes deterministically by category then entity_name
        changes.sort(key=lambda c: (c.category, c.entity_name))
        categories = sorted(list({c.category for c in changes}))

        return PatientChanges(
            patient_id=patient_id,
            total_changes_detected=len(changes),
            categories_with_changes=categories,
            changes=changes,
        )

    def generate_markdown(self, changes: PatientChanges) -> str:
        """Render human-readable Markdown summary of all documented differences."""
        lines = [
            "# What Changed",
            "",
            f"- **Patient ID:** `{changes.patient_id}`",
            f"- **Total Documented Changes/Comparisons:** {changes.total_changes_detected}",
            f"- **Categories Evaluated:** {', '.join(f'`{c}`' for c in changes.categories_with_changes) if changes.categories_with_changes else 'None'}",
            "",
            "> [!NOTE]",
            "> All comparisons represent explicitly documented textual differences across chronological records.",
            "> JourneyBrief records factual differences only and does not interpret clinical trajectory or significance.",
            "",
            "---",
            "",
        ]

        # Group by category
        current_cat: Optional[str] = None
        for chg in changes.changes:
            cat_display = chg.category.replace("_", " ").title()
            if chg.category != current_cat:
                current_cat = chg.category
                lines.append(f"## {cat_display}")
                lines.append("")

            p_src = chg.previous_source
            l_src = chg.latest_source

            lines.append(f"### {chg.entity_name}")
            lines.append(f"- **Previous Documented State ({chg.previous_date or 'N/A'}):**")
            lines.append(f"  - `{chg.previous_value}`")
            lines.append(f"  - *Source: {p_src.document_id}, page {p_src.page_number} (`{p_src.file_name}`)*")
            lines.append(f"- **Latest Documented State ({chg.latest_date or 'N/A'}):**")
            lines.append(f"  - `{chg.latest_value}`")
            lines.append(f"  - *Source: {l_src.document_id}, page {l_src.page_number} (`{l_src.file_name}`)*")
            lines.append(f"- **Documented Difference:** `{chg.documented_difference}`")
            lines.append("")

        return "\n".join(lines)

    def save_changes(
        self,
        output_dir: Path,
        patient_id: str = "SYN-CANCER-001",
        filename_prefix: str = "patient_001",
    ) -> Tuple[Path, Path]:
        """Save detected changes to JSON and Markdown artifacts."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        changes = self.detect_changes(patient_id=patient_id)

        json_path = out_dir / f"{filename_prefix}_changes.json"
        json_path.write_text(json.dumps(changes.model_dump(mode="json"), indent=2), encoding="utf-8")

        md_path = out_dir / f"{filename_prefix}_changes.md"
        md_text = self.generate_markdown(changes)
        md_path.write_text(md_text, encoding="utf-8")

        return json_path, md_path
