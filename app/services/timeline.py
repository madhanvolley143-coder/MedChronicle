"""Deterministic rule-based patient timeline engine for JourneyBrief.

Aggregates structured cancer-care facts across all documents, extracts explicit dates,
sorts events chronologically, preserves source provenance, and produces structured
JSON and human-readable Markdown timelines.

STRICT SAFETY BOUNDARY:
- No LLM/Gemini calls.
- No inferred dates (dates must be explicitly documented).
- No clinical interpretation, staging, prognosis, or medical advice.
"""

from datetime import date as dt_date
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.source import SourceReference


class TimelineItem(BaseModel):
    """A single chronological timeline event derived from documented facts."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(..., description="Deterministic unique identifier for timeline event")
    date: Optional[str] = Field(default=None, description="ISO date YYYY-MM-DD explicitly present in records")
    event_type: str = Field(
        ...,
        description="Category: visit, pathology, laboratory, imaging, medication, procedure, referral, investigation, discharge, other",
    )
    title: str = Field(..., description="Short factual title of documented event")
    description: str = Field(..., description="Documented factual description")
    source: SourceReference = Field(..., description="Mandatory source provenance")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional documented attributes")


class PatientTimeline(BaseModel):
    """Complete chronological patient timeline."""

    model_config = ConfigDict(extra="forbid")

    patient_id: str
    total_events: int
    dated_events_count: int
    undated_events_count: int
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    events: List[TimelineItem]
    undated_events: List[TimelineItem] = Field(default_factory=list)


class TimelineEngine:
    """Deterministic timeline generation engine."""

    def __init__(self, structured_dir: Path) -> None:
        self.structured_dir = Path(structured_dir)

    def load_structured_documents(self) -> List[Dict[str, Any]]:
        """Load all structured document JSON files in deterministic order."""
        if not self.structured_dir.is_dir():
            return []

        docs: List[Dict[str, Any]] = []
        for file_path in sorted(self.structured_dir.glob("*.json")):
            # Avoid duplicate test artifacts or summary files
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

    def _extract_items_from_document(
        self,
        doc_data: Dict[str, Any],
    ) -> List[TimelineItem]:
        """Convert all documented facts from a structured document into timeline items."""
        doc_id = doc_data.get("document_id", "unknown")
        facts = doc_data.get("facts", {})
        items: List[TimelineItem] = []

        counter = 0

        # 1. Visits & Encounters
        for v in facts.get("visits", []):
            counter += 1
            v_date = v.get("date")
            src_dict = v.get("source", {})
            v_type = v.get("visit_type") or "Clinical Visit"
            facility = v.get("facility") or "Healthcare Facility"
            dept = v.get("department") or "Department"
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-visit-{counter}",
                    date=str(v_date) if v_date else None,
                    event_type="discharge" if "discharge" in v_type.lower() else "visit",
                    title=f"{v_type}: {facility}",
                    description=f"Documented encounter in {dept}.",
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(v.get("confidence", 1.0)),
                    metadata={"facility": facility, "department": dept, "visit_type": v_type},
                )
            )

        # 2. Pathology Findings
        for p in facts.get("pathology_findings", []):
            counter += 1
            p_date = p.get("date")
            src_dict = p.get("source", {})
            name = p.get("finding_name", "Pathology Finding")
            doc_text = p.get("documented_text", "")
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-path-{counter}",
                    date=str(p_date) if p_date else None,
                    event_type="pathology",
                    title=f"Pathology: {name}",
                    description=doc_text,
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(p.get("confidence", 1.0)),
                    metadata={"finding_name": name},
                )
            )

        # 3. Laboratory Results
        for lab in facts.get("laboratory_results", []):
            counter += 1
            l_date = lab.get("date")
            src_dict = lab.get("source", {})
            test_name = lab.get("test_name", "Laboratory Test")
            val = lab.get("value", "")
            unit = lab.get("unit") or ""
            ref = lab.get("reference_range_text")
            desc = f"{test_name} documented value: {val} {unit}".strip()
            if ref:
                desc += f" (Reference interval: {ref})"

            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-lab-{counter}",
                    date=str(l_date) if l_date else None,
                    event_type="laboratory",
                    title=f"Laboratory Test: {test_name}",
                    description=desc,
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(lab.get("confidence", 1.0)),
                    metadata={"test_name": test_name, "value": val, "unit": unit, "reference_range": ref},
                )
            )

        # 4. Imaging Reports
        for img in facts.get("imaging_reports", []):
            counter += 1
            img_date = img.get("date")
            src_dict = img.get("source", {})
            modality = img.get("modality", "Imaging Study")
            site = img.get("body_site") or ""
            report_text = img.get("report_text", "")
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-img-{counter}",
                    date=str(img_date) if img_date else None,
                    event_type="imaging",
                    title=f"Imaging: {modality}{' - ' + site if site else ''}",
                    description=report_text,
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(img.get("confidence", 1.0)),
                    metadata={"modality": modality, "body_site": site},
                )
            )

        # 5. Medications
        for med in facts.get("medications", []):
            counter += 1
            m_date = med.get("date")
            src_dict = med.get("source", {})
            med_name = med.get("medicine_name", "Medication")
            status = med.get("status") or "listed"
            dose = med.get("dose") or med.get("strength") or "unspecified dose"
            route = med.get("route") or "oral"
            freq = med.get("frequency") or ""
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-med-{counter}",
                    date=str(m_date) if m_date else None,
                    event_type="medication",
                    title=f"Medication: {med_name}",
                    description=f"Status: {status}. Regimen: {dose} {route} {freq}".strip(),
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(med.get("confidence", 1.0)),
                    metadata={"medicine_name": med_name, "status": status, "dose": dose},
                )
            )

        # 6. Procedures
        for proc in facts.get("procedures", []):
            counter += 1
            pr_date = proc.get("date")
            src_dict = proc.get("source", {})
            proc_name = proc.get("procedure_name", "Procedure")
            status = proc.get("documented_status") or "performed"
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-proc-{counter}",
                    date=str(pr_date) if pr_date else None,
                    event_type="procedure",
                    title=f"Procedure: {proc_name}",
                    description=f"Documented procedure status: {status}.",
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(proc.get("confidence", 1.0)),
                    metadata={"procedure_name": proc_name, "status": status},
                )
            )

        # 7. Referrals
        for ref in facts.get("referrals", []):
            counter += 1
            r_date = ref.get("date")
            src_dict = ref.get("source", {})
            target = ref.get("referred_to", "Specialist")
            status = ref.get("status") or "documented"
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-ref-{counter}",
                    date=str(r_date) if r_date else None,
                    event_type="referral",
                    title=f"Referral: {target}",
                    description=f"Clinical referral request status: {status}.",
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(ref.get("confidence", 1.0)),
                    metadata={"referred_to": target, "status": status},
                )
            )

        # 8. Investigations
        for inv in facts.get("investigations", []):
            counter += 1
            src_dict = inv.get("source", {})
            inv_name = inv.get("investigation_name", "Investigation")
            status = inv.get("status", "ordered")
            ord_date = inv.get("ordered_date")
            res_date = inv.get("result_date")
            effective_date = res_date or ord_date
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-inv-{counter}",
                    date=str(effective_date) if effective_date else None,
                    event_type="investigation",
                    title=f"Investigation: {inv_name}",
                    description=f"Status: {status}. Ordered: {ord_date or 'N/A'}, Result: {res_date or 'N/A'}",
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(inv.get("confidence", 1.0)),
                    metadata={"investigation_name": inv_name, "status": status, "ordered_date": ord_date, "result_date": res_date},
                )
            )

        # 9. Document-level Timeline Events (if any)
        for ev in facts.get("timeline_events", []):
            counter += 1
            ev_date = ev.get("date")
            src_dict = ev.get("source", {})
            ev_type = ev.get("event_type", "event")
            desc = ev.get("description", "")
            items.append(
                TimelineItem(
                    event_id=f"{doc_id}-ev-{counter}",
                    date=str(ev_date) if ev_date else None,
                    event_type=ev_type,
                    title=f"{ev_type.title()}: {doc_id}",
                    description=desc,
                    source=SourceReference.model_validate(src_dict),
                    confidence=float(ev.get("confidence", 1.0)),
                )
            )

        return items

    def build_timeline(self, patient_id: str = "SYN-CANCER-001") -> PatientTimeline:
        """Construct deterministic, chronologically sorted patient timeline."""
        docs = self.load_structured_documents()
        all_items: List[TimelineItem] = []

        for doc in docs:
            items = self._extract_items_from_document(doc)
            all_items.extend(items)

        # Separate dated and undated items
        dated_items: List[TimelineItem] = []
        undated_items: List[TimelineItem] = []

        # Deduplication tracking (date, event_type, title, source_doc, source_page)
        seen_keys = set()

        for item in all_items:
            dedup_key = (
                item.date,
                item.event_type,
                item.title.strip().lower(),
                item.source.document_id,
                item.source.page_number,
            )
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            if item.date:
                dated_items.append(item)
            else:
                undated_items.append(item)

        # Chronological sort: primary key date, secondary key document_id, tertiary event_id
        dated_items.sort(
            key=lambda x: (
                str(x.date),
                x.source.document_id,
                x.source.page_number,
                x.event_type,
                x.event_id,
            )
        )

        earliest = dated_items[0].date if dated_items else None
        latest = dated_items[-1].date if dated_items else None

        return PatientTimeline(
            patient_id=patient_id,
            total_events=len(dated_items) + len(undated_items),
            dated_events_count=len(dated_items),
            undated_events_count=len(undated_items),
            earliest_date=earliest,
            latest_date=latest,
            events=dated_items,
            undated_events=undated_items,
        )

    def generate_markdown(self, timeline: PatientTimeline) -> str:
        """Render human-readable Markdown timeline grouped by date."""
        lines = [
            "# Patient Journey Timeline",
            "",
            f"- **Patient ID:** `{timeline.patient_id}`",
            f"- **Documented Date Range:** {timeline.earliest_date or 'N/A'} to {timeline.latest_date or 'N/A'}",
            f"- **Total Documented Events:** {timeline.total_events} ({timeline.dated_events_count} dated, {timeline.undated_events_count} undated)",
            "",
            "---",
            "",
        ]

        # Group dated events by date
        current_date: Optional[str] = None
        for ev in timeline.events:
            if ev.date != current_date:
                current_date = ev.date
                lines.append(f"## {current_date}")
                lines.append("")

            src = ev.source
            src_str = f"Source: {src.document_id}, page {src.page_number}"
            if src.file_name:
                src_str += f" (`{src.file_name}`)"

            lines.append(f"- **[{ev.event_type.upper()}] {ev.title}**")
            lines.append(f"  - {ev.description}")
            lines.append(f"  - *{src_str}* (Confidence: {ev.confidence:.2f})")
            lines.append("")

        if timeline.undated_events:
            lines.append("## Undated Events")
            lines.append("")
            for ev in timeline.undated_events:
                src = ev.source
                lines.append(f"- **[{ev.event_type.upper()}] {ev.title}**")
                lines.append(f"  - {ev.description}")
                lines.append(f"  - *Source: {src.document_id}, page {src.page_number}*")
                lines.append("")

        return "\n".join(lines)

    def save_timeline(
        self,
        output_dir: Path,
        patient_id: str = "SYN-CANCER-001",
        filename_prefix: str = "patient_001",
    ) -> Tuple[Path, Path]:
        """Save patient timeline to JSON and Markdown artifacts."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        timeline = self.build_timeline(patient_id=patient_id)

        json_path = out_dir / f"{filename_prefix}_timeline.json"
        json_path.write_text(json.dumps(timeline.model_dump(mode="json"), indent=2), encoding="utf-8")

        md_path = out_dir / f"{filename_prefix}_timeline.md"
        md_text = self.generate_markdown(timeline)
        md_path.write_text(md_text, encoding="utf-8")

        return json_path, md_path
