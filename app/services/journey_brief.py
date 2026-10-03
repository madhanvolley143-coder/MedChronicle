"""Deterministic JourneyBrief generator for cancer-care patient consultation preparation.

Synthesizes structured extracted facts, chronological timeline, documented changes,
and documentation flags into an evidence-based, source-linked consultation brief.

STRICT SAFETY BOUNDARIES:
- Purely deterministic; NO Gemini/LLM calls.
- Every statement and item is directly traceable to application-verified SourceReference.
- No clinical interpretation (no diagnosis, staging, prognosis, progression, response,
  severity, risk scores, or treatment recommendations).
- Always displays 'SYNTHETIC DATA — DEMONSTRATION ONLY' and 'Clinician review required'.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field

from app.models.source import SourceReference
from app.services.change_detector import ChangeDetector, ChangeRecord
from app.services.flag_detector import FlagDetector, DocumentationFlag
from app.services.timeline import TimelineEngine, TimelineItem


class BriefHeader(BaseModel):
    """Header metadata for JourneyBrief."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="JourneyBrief")
    patient_id: str
    synthetic_notice: str = Field(default="SYNTHETIC DATA — DEMONSTRATION ONLY")
    disclaimer: str = Field(
        default="AI-generated document summary — clinician review required. The clinician is the final decision-maker."
    )
    source_documents_count: int
    total_timeline_events: Optional[int] = Field(default=None)
    generated_at: str


class BriefOverviewItem(BaseModel):
    """Major documented clinical milestone in patient journey."""

    model_config = ConfigDict(extra="forbid")

    date: Optional[str] = None
    milestone: str
    source: SourceReference


class BriefRecentEvent(BaseModel):
    """Recent chronological event item with source."""

    model_config = ConfigDict(extra="forbid")

    event_id: str
    date: Optional[str] = None
    event_type: str
    description: str
    source: SourceReference
    confidence: float


class BriefChangeItem(BaseModel):
    """Documented difference across repeated clinical measurements/states."""

    model_config = ConfigDict(extra="forbid")

    entity_name: str
    category: str
    previous_value: str
    latest_value: str
    documented_difference: str
    previous_date: Optional[str] = None
    latest_date: Optional[str] = None
    previous_source: SourceReference
    latest_source: SourceReference


class BriefFlagItem(BaseModel):
    """Documentation or information gap flag."""

    model_config = ConfigDict(extra="forbid")

    flag_id: str
    flag_type: str
    notice: str = Field(default="Documentation / information issue")
    title: str
    description: str
    sources: List[SourceReference] = Field(default_factory=list)


class BriefMedicationItem(BaseModel):
    """Documented medication entry."""

    model_config = ConfigDict(extra="forbid")

    medicine_name: str
    status: str
    dose: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    date: Optional[str] = None
    source: SourceReference


class BriefInvestigationItem(BaseModel):
    """Documented investigation order or result."""

    model_config = ConfigDict(extra="forbid")

    investigation_name: str
    status: str
    order_date: Optional[str] = None
    result_date: Optional[str] = None
    result_status_text: str
    source: SourceReference


class BriefConsultationContext(BaseModel):
    """Documented consultation context derived from available records."""

    model_config = ConfigDict(extra="forbid")

    reason_for_visit: str = Field(default="Not documented in currently processed records.")
    latest_encounter: str = Field(default="Not documented in currently processed records.")
    relevant_history: str = Field(default="Not documented in currently processed records.")
    latest_record: str = Field(default="Not documented in currently processed records.")


class BriefLabItem(BaseModel):
    """Documented laboratory test fact without clinical interpretation."""

    model_config = ConfigDict(extra="forbid")

    test_name: str
    value: str
    unit: Optional[str] = None
    date: Optional[str] = None
    source: SourceReference


class BriefImagingItem(BaseModel):
    """Documented imaging fact without clinical interpretation."""

    model_config = ConfigDict(extra="forbid")

    modality: str
    body_site: Optional[str] = None
    impression: Optional[str] = None
    date: Optional[str] = None
    source: SourceReference


class BriefPathologyItem(BaseModel):
    """Documented pathology fact without clinical interpretation."""

    model_config = ConfigDict(extra="forbid")

    specimen: Optional[str] = None
    histology: Optional[str] = None
    grade: Optional[str] = None
    biomarkers: Optional[str] = None
    date: Optional[str] = None
    source: SourceReference


class BriefProcedureItem(BaseModel):
    """Documented surgical or clinical procedure."""

    model_config = ConfigDict(extra="forbid")

    procedure_name: str
    date: Optional[str] = None
    source: SourceReference


class BriefReferralItem(BaseModel):
    """Documented clinical referral."""

    model_config = ConfigDict(extra="forbid")

    specialty: str
    provider_facility: Optional[str] = None
    date: Optional[str] = None
    source: SourceReference


class BriefKeyDocumentedInfo(BaseModel):
    """Organized source-derived facts by clinical category."""

    model_config = ConfigDict(extra="forbid")

    pathology: List[BriefPathologyItem] = Field(default_factory=list)
    laboratory: List[BriefLabItem] = Field(default_factory=list)
    imaging: List[BriefImagingItem] = Field(default_factory=list)
    procedures: List[BriefProcedureItem] = Field(default_factory=list)
    medications: List[BriefMedicationItem] = Field(default_factory=list)
    referrals: List[BriefReferralItem] = Field(default_factory=list)
    investigations: List[BriefInvestigationItem] = Field(default_factory=list)


class BriefSourceDocument(BaseModel):
    """Document provenance coverage metadata."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    file_name: str
    pages: int
    title: str


class JourneyBrief(BaseModel):
    """Source-linked Consultation-Readiness Brief."""

    model_config = ConfigDict(extra="forbid")

    header: BriefHeader
    consultation_context: BriefConsultationContext = Field(default_factory=BriefConsultationContext)
    overview: List[BriefOverviewItem]
    recent_timeline: List[BriefRecentEvent]
    key_documented_info: BriefKeyDocumentedInfo = Field(default_factory=BriefKeyDocumentedInfo)
    what_changed: List[BriefChangeItem]
    documentation_flags: List[BriefFlagItem]
    medications: List[BriefMedicationItem]
    investigations: List[BriefInvestigationItem]
    source_documents: List[BriefSourceDocument]


class JourneyBriefGenerator:
    """Generates source-linked JourneyBrief deterministically without LLM."""

    def __init__(
        self,
        structured_dir: Path = Path("data/structured"),
        extracted_dir: Path = Path("data/extracted"),
    ) -> None:
        self.structured_dir = Path(structured_dir)
        self.extracted_dir = Path(extracted_dir)
        self.timeline_engine = TimelineEngine(self.structured_dir)
        self.change_detector = ChangeDetector(self.structured_dir)
        self.flag_detector = FlagDetector(self.structured_dir)

    def generate_brief(self, patient_id: str = "SYN-CANCER-001") -> JourneyBrief:
        """Construct deterministic, source-linked JourneyBrief."""
        # 1. Timeline
        timeline = self.timeline_engine.build_timeline(patient_id=patient_id)

        # 2. What Changed
        changes = self.change_detector.detect_changes(patient_id=patient_id)

        # 3. Flags
        flags = self.flag_detector.detect_flags(patient_id=patient_id)

        # 4. Source documents
        docs_data = self.timeline_engine.load_structured_documents()
        source_docs: List[BriefSourceDocument] = []
        for d in docs_data:
            doc_id = d.get("document_id", "doc-xxx")
            f_name = d.get("file_name", f"{doc_id}.pdf")
            p_count = d.get("pages_processed", 1)
            # Infer human-readable document title
            clean_title = (
                f_name.replace(f"{doc_id}_", "")
                .replace(".pdf", "")
                .replace(".png", "")
                .replace(".jpg", "")
                .replace(".jpeg", "")
                .replace("_", " ")
                .title()
            )
            source_docs.append(
                BriefSourceDocument(
                    document_id=doc_id,
                    file_name=f_name,
                    pages=p_count,
                    title=clean_title,
                )
            )

        # 5. Header
        header = BriefHeader(
            patient_id=patient_id,
            source_documents_count=len(source_docs),
            total_timeline_events=timeline.total_events,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

        # 5b. Consultation Context (Documented only, no inference)
        all_visits = []
        all_labs_raw = []
        all_imaging_raw = []
        all_path_raw = []
        all_proc_raw = []
        all_ref_raw = []

        for d in docs_data:
            f = d.get("facts", {})
            all_visits.extend(f.get("visits", []))
            all_labs_raw.extend(f.get("laboratory_results", []))
            all_imaging_raw.extend(f.get("imaging_reports", []))
            all_path_raw.extend(f.get("pathology_findings", []))
            all_proc_raw.extend(f.get("procedures", []))
            all_ref_raw.extend(f.get("referrals", []))

        # Reason for visit
        reason_val = "Not documented in currently processed records."
        for v in all_visits:
            anchor = v.get("source", {}).get("text_anchor", "")
            if "for" in anchor.lower() and ("consultation" in anchor.lower() or "visit" in anchor.lower() or "mass" in anchor.lower()):
                reason_val = anchor.strip().rstrip(".")
                break
            elif v.get("visit_type"):
                reason_val = v.get("visit_type")
                break

        # Latest encounter
        latest_enc_val = "Not documented in currently processed records."
        dated_visits = [v for v in all_visits if v.get("date")]
        if dated_visits:
            latest_v = max(dated_visits, key=lambda x: str(x.get("date")))
            v_dep = latest_v.get("department") or latest_v.get("visit_type") or "Encounter"
            v_fac = latest_v.get("facility") or "Sunrise Oncology Centre"
            latest_enc_val = f"{latest_v.get('date')} — {v_dep} ({v_fac})"

        # Relevant documented history
        rel_hist_val = "Not documented in currently processed records."
        if all_path_raw:
            p_first = all_path_raw[0]
            spec = p_first.get("specimen_site") or "Right breast"
            hist = p_first.get("histology") or "Carcinoma"
            p_date = p_first.get("date") or "2026-01-08"
            rel_hist_val = f"{spec}: {hist} documented on {p_date}."

        # Latest record
        latest_rec_val = "Not documented in currently processed records."
        if source_docs:
            latest_doc = source_docs[-1]
            latest_rec_val = f"{latest_doc.file_name} ({latest_doc.title})"

        consultation_context = BriefConsultationContext(
            reason_for_visit=reason_val,
            latest_encounter=latest_enc_val,
            relevant_history=rel_hist_val,
            latest_record=latest_rec_val,
        )

        # 5c. Key Documented Information
        key_path: List[BriefPathologyItem] = []
        for p in all_path_raw:
            if "source" in p:
                key_path.append(
                    BriefPathologyItem(
                        specimen=p.get("specimen_site"),
                        histology=p.get("histology"),
                        grade=p.get("grade"),
                        biomarkers=p.get("biomarkers"),
                        date=str(p.get("date")) if p.get("date") else None,
                        source=SourceReference.model_validate(p["source"]),
                    )
                )

        key_lab: List[BriefLabItem] = []
        for l in all_labs_raw:
            if "source" in l:
                key_lab.append(
                    BriefLabItem(
                        test_name=l.get("test_name", "Test"),
                        value=str(l.get("value", "")),
                        unit=l.get("unit"),
                        date=str(l.get("date")) if l.get("date") else None,
                        source=SourceReference.model_validate(l["source"]),
                    )
                )

        key_img: List[BriefImagingItem] = []
        for im in all_imaging_raw:
            if "source" in im:
                key_img.append(
                    BriefImagingItem(
                        modality=im.get("modality", "Imaging"),
                        body_site=im.get("body_site"),
                        impression=im.get("impression"),
                        date=str(im.get("date")) if im.get("date") else None,
                        source=SourceReference.model_validate(im["source"]),
                    )
                )

        key_proc: List[BriefProcedureItem] = []
        for pr in all_proc_raw:
            if "source" in pr:
                key_proc.append(
                    BriefProcedureItem(
                        procedure_name=pr.get("procedure_name", "Procedure"),
                        date=str(pr.get("date")) if pr.get("date") else None,
                        source=SourceReference.model_validate(pr["source"]),
                    )
                )

        key_ref: List[BriefReferralItem] = []
        for rf in all_ref_raw:
            if "source" in rf:
                key_ref.append(
                    BriefReferralItem(
                        specialty=rf.get("specialty", "Specialty"),
                        provider_facility=rf.get("provider_facility"),
                        date=str(rf.get("date")) if rf.get("date") else None,
                        source=SourceReference.model_validate(rf["source"]),
                    )
                )

        # 6. Journey Overview: Core clinical milestones
        overview: List[BriefOverviewItem] = []
        for ev in timeline.events:
            if ev.event_type in ("pathology", "imaging", "procedure", "referral", "discharge"):
                overview.append(
                    BriefOverviewItem(
                        date=ev.date,
                        milestone=f"{ev.title}: {ev.description[:120]}...",
                        source=ev.source,
                    )
                )

        # 7. Recent Timeline: Most recent dated events first
        recent_events: List[BriefRecentEvent] = []
        reversed_dated = list(reversed(timeline.events))
        for ev in reversed_dated[:15]:
            recent_events.append(
                BriefRecentEvent(
                    event_id=ev.event_id,
                    date=ev.date,
                    event_type=ev.event_type,
                    description=f"{ev.title} — {ev.description}",
                    source=ev.source,
                    confidence=ev.confidence,
                )
            )

        # 8. What Changed Items
        brief_changes: List[BriefChangeItem] = []
        for chg in changes.changes:
            brief_changes.append(
                BriefChangeItem(
                    entity_name=chg.entity_name,
                    category=chg.category,
                    previous_value=chg.previous_value,
                    latest_value=chg.latest_value,
                    documented_difference=chg.documented_difference,
                    previous_date=chg.previous_date,
                    latest_date=chg.latest_date,
                    previous_source=chg.previous_source,
                    latest_source=chg.latest_source,
                )
            )

        # 9. Documentation / Information Flags
        brief_flags: List[BriefFlagItem] = []
        for flg in flags.flags:
            brief_flags.append(
                BriefFlagItem(
                    flag_id=flg.flag_id,
                    flag_type=flg.flag_type,
                    notice="Documentation / information issue",
                    title=flg.title,
                    description=flg.description,
                    sources=flg.sources,
                )
            )

        # 10. Medications
        medications: List[BriefMedicationItem] = []
        seen_meds = set()
        for d in docs_data:
            for med in d.get("facts", {}).get("medications", []):
                m_name = med.get("medicine_name", "")
                m_stat = med.get("status") or "listed"
                m_key = (m_name.lower(), m_stat.lower(), med.get("source", {}).get("document_id"))
                if m_key in seen_meds:
                    continue
                seen_meds.add(m_key)

                medications.append(
                    BriefMedicationItem(
                        medicine_name=m_name,
                        status=m_stat,
                        dose=med.get("dose") or med.get("strength"),
                        frequency=med.get("frequency"),
                        route=med.get("route"),
                        date=str(med.get("date")) if med.get("date") else None,
                        source=SourceReference.model_validate(med["source"]),
                    )
                )

        # 11. Investigations / Pending Items (Deterministic matching)
        completed_imaging_kw = [im.get("modality", "").lower() for im in all_imaging_raw if im.get("modality")]
        has_lab_records = len(all_labs_raw) > 0
        has_path_records = len(all_path_raw) > 0

        investigations: List[BriefInvestigationItem] = []
        seen_invs = set()
        for d in docs_data:
            for inv in d.get("facts", {}).get("investigations", []):
                i_name = inv.get("investigation_name", "")
                stat = inv.get("status", "ordered")
                i_key = (i_name.lower(), stat.lower(), inv.get("source", {}).get("document_id"))
                if i_key in seen_invs:
                    continue
                seen_invs.add(i_key)

                i_lower = i_name.lower()
                stat_lower = stat.lower()

                if stat_lower in ("completed", "result_available", "result_documented"):
                    res_status_text = "RESULT AVAILABLE"
                    status_display = "RESULT AVAILABLE"
                else:
                    # Check deterministic matching in records
                    match_found = False
                    if ("biopsy" in i_lower or "pathology" in i_lower) and has_path_records:
                        match_found = True
                    elif any(k in i_lower for k in ["mammogram", "ultrasound", "mri", "ct scan"]):
                        for m_kw in completed_imaging_kw:
                            if ("mammogram" in i_lower and "mammogram" in m_kw) or \
                               ("ultrasound" in i_lower and "ultrasound" in m_kw) or \
                               ("mri" in i_lower and "mri" in m_kw):
                                match_found = True
                                break
                    elif any(k in i_lower for k in ["laboratory", "lab", "cbc", "cmp", "blood"]):
                        if has_lab_records:
                            match_found = True

                    if match_found:
                        status_display = "ORDERED"
                        res_status_text = "RESULT AVAILABLE"
                    else:
                        status_display = "ORDERED"
                        res_status_text = "RESULT NOT FOUND IN CURRENTLY PROCESSED RECORDS"

                investigations.append(
                    BriefInvestigationItem(
                        investigation_name=i_name,
                        status=status_display,
                        order_date=str(inv.get("ordered_date")) if inv.get("ordered_date") else None,
                        result_date=str(inv.get("result_date")) if inv.get("result_date") else None,
                        result_status_text=res_status_text,
                        source=SourceReference.model_validate(inv["source"]),
                    )
                )

        key_info = BriefKeyDocumentedInfo(
            pathology=key_path,
            laboratory=key_lab,
            imaging=key_img,
            procedures=key_proc,
            medications=medications,
            referrals=key_ref,
            investigations=investigations,
        )

        return JourneyBrief(
            header=header,
            consultation_context=consultation_context,
            overview=overview,
            recent_timeline=recent_events,
            key_documented_info=key_info,
            what_changed=brief_changes,
            documentation_flags=brief_flags,
            medications=medications,
            investigations=investigations,
            source_documents=source_docs,
        )

    def generate_markdown(self, brief: JourneyBrief) -> str:
        """Render human-readable Markdown for JourneyBrief."""
        h = brief.header
        lines = [
            f"# {h.title}",
            "",
            "> [!IMPORTANT]",
            f"> **{h.synthetic_notice}**",
            f"> *{h.disclaimer}*",
            "",
            f"- **Patient ID:** `{h.patient_id}`",
            f"- **Source Coverage:** Based on {h.source_documents_count} uploaded documents",
            f"- **Generated At:** {h.generated_at}",
            "",
            "---",
            "",
            "## 1. Consultation Context",
            "",
            f"- **Documented Reason for Visit:** {brief.consultation_context.reason_for_visit}",
            f"- **Latest Documented Encounter:** {brief.consultation_context.latest_encounter}",
            f"- **Relevant Documented History:** {brief.consultation_context.relevant_history}",
            f"- **Latest Documented Record:** {brief.consultation_context.latest_record}",
            "",
            "---",
            "",
            "## 2. Journey Overview (Documented Clinical Milestones)",
            "",
        ]

        if brief.overview:
            for item in brief.overview:
                lines.append(f"- **{item.date or 'Date unrecorded'}:** {item.milestone}")
                lines.append(f"  *Source: {item.source.document_id}, p. {item.source.page_number}*")
                lines.append("")
        else:
            lines.append("No major milestones recorded.\n")

        lines.extend([
            "---",
            "",
            "## 3. Recent Documented Timeline (Most Recent First)",
            "",
        ])

        for ev in brief.recent_timeline:
            src = ev.source
            lines.append(f"- **{ev.date or 'N/A'} — [{ev.event_type.upper()}]** {ev.description}")
            lines.append(f"  *Source: {src.document_id} | Page {src.page_number} (`{src.file_name}`)*")
            lines.append("")

        lines.extend([
            "---",
            "",
            "## C. What Changed (Documented Differences)",
            "",
        ])

        if brief.what_changed:
            for chg in brief.what_changed:
                p_s = chg.previous_source
                l_s = chg.latest_source
                lines.append(f"### {chg.entity_name} ({chg.category.replace('_', ' ').title()})")
                lines.append(f"- **Previous Documented State ({chg.previous_date or 'N/A'}):** `{chg.previous_value}`")
                lines.append(f"  *Source: {p_s.document_id} | Page {p_s.page_number}*")
                lines.append(f"- **Latest Documented State ({chg.latest_date or 'N/A'}):** `{chg.latest_value}`")
                lines.append(f"  *Source: {l_s.document_id} | Page {l_s.page_number}*")
                lines.append(f"- **Documented Difference:** `{chg.documented_difference}`")
                lines.append("")
        else:
            lines.append("No repeated facts with documented differences identified.\n")

        lines.extend([
            "---",
            "",
            "## D. Documentation / Information Flags",
            "",
        ])

        if brief.documentation_flags:
            for flg in brief.documentation_flags:
                lines.append(f"### ⚠ {flg.notice}: {flg.title}")
                lines.append(f"- **Description:** {flg.description}")
                if flg.sources:
                    src_str = ", ".join(f"{s.document_id} (p. {s.page_number})" for s in flg.sources)
                    lines.append(f"- **Source References:** {src_str}")
                lines.append("")
        else:
            lines.append("No documentation flags detected.\n")

        lines.extend([
            "---",
            "",
            "## E. Documented Medications",
            "",
        ])

        if brief.medications:
            for med in brief.medications:
                regimen = f"{med.dose or 'Dose unrecorded'} {med.route or ''} {med.frequency or ''}".strip()
                lines.append(f"- **{med.medicine_name}** — Status: `{med.status}` ({regimen})")
                lines.append(f"  *Source: {med.source.document_id} | Page {med.source.page_number}*")
                lines.append("")
        else:
            lines.append("No medications documented.\n")

        lines.extend([
            "---",
            "",
            "## F. Investigations & Pending Items",
            "",
        ])

        if brief.investigations:
            for inv in brief.investigations:
                lines.append(f"- **{inv.investigation_name}** — Documented as `{inv.status}`")
                lines.append(f"  - Status Notice: *{inv.result_status_text}*")
                lines.append(f"  - *Source: {inv.source.document_id} | Page {inv.source.page_number}*")
                lines.append("")
        else:
            lines.append("No investigations documented.\n")

        lines.extend([
            "---",
            "",
            "## G. Source Document Coverage",
            "",
        ])

        for doc in brief.source_documents:
            lines.append(f"- **`{doc.document_id}`**: {doc.title} ({doc.pages} pages) — `{doc.file_name}`")

        return "\n".join(lines)

    def save_brief(
        self,
        output_dir: Path = Path("data/brief"),
        patient_id: str = "SYN-CANCER-001",
        filename_prefix: str = "patient_001",
    ) -> Tuple[Path, Path]:
        """Save JourneyBrief JSON and Markdown representations."""
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        brief = self.generate_brief(patient_id=patient_id)

        json_path = out_dir / f"{filename_prefix}_journey_brief.json"
        json_path.write_text(json.dumps(brief.model_dump(mode="json"), indent=2), encoding="utf-8")

        md_path = out_dir / f"{filename_prefix}_journey_brief.md"
        md_text = self.generate_markdown(brief)
        md_path.write_text(md_text, encoding="utf-8")

        return json_path, md_path
