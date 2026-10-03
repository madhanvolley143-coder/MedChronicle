"""Synthetic clinical PDF document generator for JourneyBrief.

Reads data/ground_truth/patient_001.json and generates clean, deterministic,
professional medical PDFs matching ground truth metadata, dates, and exact page counts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class NumberedCanvas(canvas.Canvas):
    """Custom canvas that tracks total pages and draws running headers and footers."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: List[Dict[str, Any]] = []
        self.doc_id: str = ""
        self.doc_date: str = ""
        self.patient_id: str = "SYN-CANCER-001"
        self.facility_name: str = "Sunrise Oncology Centre"

    @classmethod
    def create_factory(cls, doc_id: str, doc_date: str, facility_name: str) -> type:
        class DocumentCanvas(cls):
            def __init__(self, *args: Any, **kwargs: Any) -> None:
                super().__init__(*args, **kwargs)
                self.doc_id = doc_id
                self.doc_date = doc_date
                self.facility_name = facility_name
        return DocumentCanvas

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count: int) -> None:
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#2C3E50"))

        # Running header rule
        self.setStrokeColor(colors.HexColor("#BDC3C7"))
        self.setLineWidth(0.75)
        self.line(40, 755, 572, 755)

        # Header metadata
        self.drawString(
            40,
            760,
            f"{self.facility_name.upper()} | Doc: {self.doc_id} | Date: {self.doc_date}",
        )
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#C0392B"))
        self.drawRightString(
            572,
            760,
            f"SYNTHETIC RECORD: {self.patient_id}",
        )

        # Running footer rule
        self.setStrokeColor(colors.HexColor("#BDC3C7"))
        self.setLineWidth(0.75)
        self.line(40, 42, 572, 42)

        # Footer text
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#7F8C8D"))
        self.drawString(
            40,
            32,
            "FOR RESEARCH & ALGORITHM EVALUATION ONLY — 100% SYNTHETIC DATA — NOT A REAL PATIENT RECORD",
        )
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#2C3E50"))
        self.drawRightString(
            572,
            32,
            f"Page {self._pageNumber} of {page_count}",
        )
        self.restoreState()


def build_meta_table(
    doc_id: str,
    doc_date: str,
    doc_type: str,
    facility: str,
    dept: str,
    patient_id: str = "SYN-CANCER-001",
) -> Table:
    """Build standardized clinical document metadata box."""
    data = [
        ["Patient ID:", f"{patient_id} (Synthetic)", "Document ID:", doc_id],
        ["Document Date:", doc_date, "Document Type:", doc_type.replace("_", " ").title()],
        ["Facility:", facility, "Department:", dept],
    ]
    t = Table(data, colWidths=[90, 176, 90, 176])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
                ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#2C3E50")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (2, 0), (2, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTNAME", (3, 0), (3, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#D5DBDB")),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#EAEDED")),
            ]
        )
    )
    return t


def generate_doc_001(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 001: Visit Note (2 pages) - Initial surgical oncology consultation."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    # Title & Metadata
    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("OUTPATIENT SURGICAL ONCOLOGY CONSULTATION NOTE", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Department of Surgical Oncology",
        )
    )
    story.append(Spacer(1, 10))

    # Page 1: History, Encounter details & Clinical Examination
    story.append(Paragraph("CHIEF COMPLAINT & ENCOUNTER DETAILS", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "<b>Encounter:</b> Initial oncology consultation for palpable right breast mass. "
            "Patient reports a self-discovered, non-tender nodule in the upper outer quadrant of the right breast.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("CLINICAL PHYSICAL EXAMINATION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "<b>Right Breast:</b> Discrete, firm, mobile mass palpable at approximately the 10 o'clock position, "
            "measuring approximately 2.0 to 2.5 cm on manual palpation. No overlying skin retraction or peau d'orange. "
            "No spontaneous nipple discharge.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Left Breast:</b> Symmetrical, soft, no dominant masses, nodules, or architectural distortion.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Regional Lymph Nodes:</b> No palpable lymphadenopathy in bilateral axillae, supraclavicular, or infraclavicular fossae.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("DOCUMENTED BASELINE VITALS", styles["SectionTitle"]))
    vitals_data = [
        ["Parameter", "Recorded Value", "Parameter", "Recorded Value"],
        ["Blood Pressure", "122/78 mmHg", "Heart Rate", "72 bpm, regular"],
        ["Respiratory Rate", "16 breaths/min", "Body Temperature", "36.8 deg C"],
        ["Oxygen Saturation", "99% on room air", "BMI", "24.2 kg/m2"],
    ]
    vt = Table(vitals_data, colWidths=[133, 133, 133, 133])
    vt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#34495E")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]
        )
    )
    story.append(vt)

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    # Page 2: Orders, Plan & Verification
    story.append(Paragraph("DOCUMENTED INVESTIGATIONS ORDERED", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "1. <b>Diagnostic Mammogram and Breast Ultrasound:</b> Ordered on 2026-01-05 for anatomical characterization.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "2. <b>Image-Guided Core Needle Biopsy:</b> Pending diagnostic imaging verification.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "3. <b>Baseline Laboratory Panel:</b> Complete blood count and serum tumor markers.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 12))

    story.append(Paragraph("DOCUMENTED CONSULTATION PLAN", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Follow-up scheduled post-imaging and histopathology review. All orders transmitted to diagnostic radiology.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 30))

    story.append(Paragraph("PHYSICIAN DOCUMENTATION SIGN-OFF", styles["SectionTitle"]))
    story.append(Paragraph("Documented by: Surgical Oncology Service, Sunrise Oncology Centre", styles["Body"]))
    story.append(Paragraph("Date of record finalization: 2026-01-05 16:45 EST", styles["Body"]))

    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_002(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 002: Pathology Report (2 pages) - Core needle biopsy findings."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("GREEN VALLEY DIAGNOSTIC CENTRE", styles["DocHeader"]))
    story.append(Paragraph("SURGICAL PATHOLOGY & HISTOPATHOLOGY REPORT", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Green Valley Diagnostic Centre",
            dept="Department of Anatomical Pathology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("SPECIMEN IDENTIFICATION & CLINICAL DATA", styles["SectionTitle"]))
    story.append(Paragraph("<b>Specimen:</b> Core Needle Biopsy, Right Breast.", styles["Body"]))
    story.append(Paragraph("<b>Procedure Date:</b> 2026-01-08", styles["Body"]))
    story.append(Paragraph("<b>Clinical History:</b> Palpable right breast mass in upper-outer quadrant.", styles["Body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("GROSS / MACROSCOPIC DESCRIPTION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Received in formalin labeled with synthetic patient ID SYN-CANCER-001 are four (4) core needle biopsy fragments. "
            "The tissue cores range in length from 1.1 cm to 1.6 cm, with a uniform diameter of 0.1 cm. "
            "Color is tan-white to fibrofatty. Entire specimen submitted in one cassette (Block A1).",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("PROCESSING PROTOCOL", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Standard formalin fixation (18 hours), automated paraffin embedding, 4-micron microtomy sections, "
            "and routine Hematoxylin & Eosin (H&E) staining performed. Immunohistochemical (IHC) profiling initiated.",
            styles["Body"],
        )
    )

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    story.append(Paragraph("MICROSCOPIC DESCRIPTION & FINAL DOCUMENTED FINDINGS", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Sections demonstrate invasive carcinoma with glandular and corded architectural patterns. "
            "Tubule formation is moderate. Nuclei exhibit moderate pleomorphism with occasional visible mitotic figures. "
            "Surrounding stroma reveals desmoplastic reaction with minimal lymphocytic infiltrate.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6))

    story.append(
        Paragraph(
            "<b>Documented Histopathology Diagnosis:</b><br/>"
            "Pathology report documents: Invasive ductal carcinoma, histological Nottingham grade 2. "
            "Estrogen receptor (ER) positive (85%), Progesterone receptor (PR) positive (70%), "
            "HER2 negative (score 1+ by IHC). Ki-67 index: 15%.",
            styles["HighlightedText"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("IMMUNOHISTOCHEMICAL BIOMARKER PROFILE", styles["SectionTitle"]))
    ihc_data = [
        ["Biomarker", "Method", "Documented Result", "Reference Criteria"],
        ["Estrogen Receptor (ER)", "IHC (Clone SP1)", "Positive (85% strong nuclear staining)", "ASCO/CAP >= 1% positive"],
        ["Progesterone Receptor (PR)", "IHC (Clone 1E2)", "Positive (70% moderate nuclear staining)", "ASCO/CAP >= 1% positive"],
        ["HER2 / neu Protein", "IHC (Clone 4B5)", "Negative (Score 1+ faint membrane staining)", "ASCO/CAP Guidelines"],
        ["Ki-67 Proliferation Index", "IHC (Clone MIB-1)", "15% nuclear labeling index", "Documented count per 1000 cells"],
    ]
    ihc_table = Table(ihc_data, colWidths=[120, 112, 160, 140])
    ihc_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]
        )
    )
    story.append(ihc_table)
    story.append(Spacer(1, 20))

    story.append(Paragraph("PATHOLOGIST SIGN-OFF", styles["SectionTitle"]))
    story.append(Paragraph("Reporting Pathologist: Green Valley Diagnostic Pathology Staff", styles["Body"]))
    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Green Valley Diagnostic Centre",
        ),
    )


def generate_doc_003(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 003: Laboratory Report (1 page) - Baseline CA 15-3 and Hemoglobin."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("GREEN VALLEY DIAGNOSTIC CENTRE", styles["DocHeader"]))
    story.append(Paragraph("CLINICAL LABORATORY INVESTIGATION REPORT", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Green Valley Diagnostic Centre",
            dept="Clinical Chemistry & Hematology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("SPECIMEN & COLLECTION INFORMATION", styles["SectionTitle"]))
    story.append(Paragraph("<b>Collection Date/Time:</b> 2026-01-10 08:30 EST | <b>Specimen Type:</b> Venous Blood (EDTA / Serum)", styles["Body"]))
    story.append(Paragraph("<b>Ordering Clinician:</b> Surgical Oncology Service, Sunrise Oncology Centre", styles["Body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("LABORATORY RESULTS SUMMARY", styles["SectionTitle"]))
    lab_data = [
        ["Analyte / Test Name", "Result Value", "Unit", "Documented Reference Interval", "Status"],
        ["CA 15-3", "22.4", "U/mL", "0.0 - 30.0 U/mL", "Completed"],
        ["Hemoglobin", "13.4", "g/dL", "12.0 - 15.5 g/dL", "Completed"],
        ["White Blood Cells (WBC)", "6.8", "x10^3/uL", "4.5 - 11.0 x10^3/uL", "Completed"],
        ["Platelet Count", "240", "x10^3/uL", "150 - 450 x10^3/uL", "Completed"],
        ["Serum Creatinine", "0.85", "mg/dL", "0.60 - 1.10 mg/dL", "Completed"],
        ["Alanine Aminotransferase (ALT)", "22", "U/L", "7 - 35 U/L", "Completed"],
    ]
    lt = Table(lab_data, colWidths=[150, 80, 60, 162, 80])
    lt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("BACKGROUND", (0, 1), (-1, 2), colors.HexColor("#F2F4F4")),
            ]
        )
    )
    story.append(lt)
    story.append(Spacer(1, 10))

    story.append(Paragraph("DOCUMENTED EXTRACT ANCHORS", styles["SectionTitle"]))
    story.append(Paragraph("Laboratory report records: CA 15-3 value 22.4 U/mL", styles["HighlightedText"]))
    story.append(Paragraph("Laboratory report records: Hemoglobin value 13.4 g/dL", styles["HighlightedText"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("LABORATORY DIRECTOR VERIFICATION", styles["SectionTitle"]))
    story.append(Paragraph("Certified by: Clinical Chemistry Section Head, Green Valley Diagnostic Centre", styles["Body"]))
    story.append(Paragraph("Report Released: 2026-01-10 14:15 EST", styles["Body"]))

    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Green Valley Diagnostic Centre",
        ),
    )


def generate_doc_004(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 004: Imaging Report (2 pages) - CT Chest/Abdomen/Pelvis."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("DIAGNOSTIC RADIOLOGY REPORT — COMPUTED TOMOGRAPHY", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Department of Diagnostic Imaging",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("EXAMINATION DETAILS", styles["SectionTitle"]))
    story.append(Paragraph("<b>Procedure:</b> Contrast-Enhanced CT Chest, Abdomen, and Pelvis (IV contrast administered).", styles["Body"]))
    story.append(Paragraph("<b>Clinical Indication:</b> Staging evaluation for newly diagnosed right breast carcinoma.", styles["Body"]))
    story.append(Paragraph("<b>Technique:</b> Axial helical acquisitions obtained from lung apices through ischial tuberosities with reconstructed coronal and sagittal reformations.", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("TECHNICAL QUALITY & RADIATION DOSE", styles["SectionTitle"]))
    story.append(Paragraph("Dose-length product (DLP): 680 mGy*cm. Quality: Diagnostic, no motion artifacts.", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("ORGAN-BY-ORGAN PRELIMINARY OBSERVATIONS", styles["SectionTitle"]))
    story.append(Paragraph("<b>Lower Neck / Thyroid:</b> Visualized thyroid gland is unremarkable without nodules.", styles["Body"]))
    story.append(Paragraph("<b>Mediastinum & Hila:</b> No pathological lymphadenopathy detected in mediastinum or hilar stations.", styles["Body"]))
    story.append(Paragraph("<b>Pleural Spaces:</b> No pleural effusions or pleural thickening identified bilaterally.", styles["Body"]))

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    story.append(Paragraph("DETAILED ANATOMICAL FINDINGS", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "<b>Breast & Chest Wall:</b> 2.2 cm discrete non-calcified mass in upper-outer quadrant of right breast. "
            "Underlying pectoralis major muscle plane is preserved without direct invasion. Left breast unremarkable.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Lungs:</b> No focal lesions in lung parenchyma. Tracheobronchial tree is clear.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Abdomen:</b> Liver is normal in size and attenuation; no focal lesions. Spleen, pancreas, adrenal glands, and kidneys unremarkable.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Pelvis:</b> Bladder and pelvic organs unremarkable. No pelvic free fluid. No pathological lymphadenopathy detected in retroperitoneum.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Bones:</b> No focal destructive or blastic lesions in osseous structures.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("IMPRESSION & DOCUMENTED TEXT ANCHOR", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Imaging report states: 2.2 cm discrete non-calcified mass in upper-outer quadrant of right breast. "
            "No focal lesions in lung parenchyma, liver, or osseous structures. "
            "No pathological lymphadenopathy detected in mediastinum or retroperitoneum.",
            styles["HighlightedText"],
        )
    )
    story.append(Spacer(1, 20))

    story.append(Paragraph("REPORTING RADIOLOGIST", styles["SectionTitle"]))
    story.append(Paragraph("Interpreting Radiologist: Staff Radiologist, Sunrise Diagnostic Imaging", styles["Body"]))
    story.append(Paragraph("Final Verification: 2026-01-14 16:10 EST", styles["Body"]))
    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_005(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 005: Prescription (1 page) - Tamoxifen medication order."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("OUTPATIENT PHARMACY PRESCRIPTION ORDER", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Department of Medical Oncology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("PRESCRIBER INFORMATION", styles["SectionTitle"]))
    story.append(Paragraph("<b>Prescribing Physician:</b> Medical Oncology Staff, Sunrise Oncology Centre", styles["Body"]))
    story.append(Paragraph("<b>License / NPI:</b> SYN-LIC-99281 | <b>DEA:</b> SYN-DEA-00412", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("MEDICATION ORDER DETAILS", styles["SectionTitle"]))
    med_data = [
        ["Field", "Prescribed Specification"],
        ["Medication Name", "Tamoxifen"],
        ["Dosage Strength", "20 mg"],
        ["Dosage Form", "Oral Tablet"],
        ["Directions / Sig", "Take 1 tablet (20 mg) orally once daily in the morning"],
        ["Route of Administration", "Oral"],
        ["Frequency", "Daily"],
        ["Documented Status", "started"],
        ["Dispense Quantity", "30 tablets (1 month supply)"],
        ["Refills Authorized", "5 (five refills)"],
    ]
    mt = Table(med_data, colWidths=[160, 372])
    mt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAEDED")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTNAME", (1, 0), (1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]
        )
    )
    story.append(mt)
    story.append(Spacer(1, 10))

    story.append(Paragraph("DOCUMENTED TEXT ANCHOR", styles["SectionTitle"]))
    story.append(Paragraph("Prescription lists: Tamoxifen 20 mg tablet oral daily", styles["HighlightedText"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("PHARMACY DISPENSING INSTRUCTIONS", styles["SectionTitle"]))
    story.append(Paragraph("Dispense as written. Patient educated regarding once-daily schedule.", styles["Body"]))
    story.append(Spacer(1, 20))
    story.append(Paragraph("Physician Electronic Signature: Medical Oncology Service (Verified 2026-01-15 11:20 EST)", styles["Body"]))
    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_006(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 006: Procedure Note (2 pages) - Right partial mastectomy & sentinel lymph node biopsy."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("OPERATIVE & PROCEDURE REPORT", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Operating Room / Surgical Oncology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("OPERATIVE SUMMARY", styles["SectionTitle"]))
    story.append(Paragraph("<b>Procedure Date:</b> 2026-01-20", styles["Body"]))
    story.append(Paragraph("<b>Documented Status:</b> completed", styles["Body"]))
    story.append(Paragraph("<b>Preoperative Diagnosis:</b> Documented right breast neoplasm.", styles["Body"]))
    story.append(Paragraph("<b>Postoperative Diagnosis:</b> Documented right breast neoplasm post-resection.", styles["Body"]))
    story.append(
        Paragraph(
            "<b>Procedure Performed:</b> Right partial mastectomy with sentinel lymph node biopsy.",
            styles["HighlightedText"],
        )
    )
    story.append(Paragraph("<b>Anesthesia:</b> General endotracheal anesthesia.", styles["Body"]))
    story.append(Paragraph("<b>Estimated Blood Loss:</b> Approximately 25 mL.", styles["Body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("PREPARATION & SENTINEL NODE LOCALIZATION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "The patient was identified, verified, and brought to the operating suite. "
            "Preoperative technetium-99m sulfur colloid radiotracer was administered periareolarly. "
            "Gamma probe confirmed focal radioactive count in the right axilla prior to incision.",
            styles["Body"],
        )
    )

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    story.append(Paragraph("OPERATIVE NARRATIVE & TECHNIQUE", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "A curvilinear incision was made over the right breast upper-outer quadrant directly overlying the palpable lesion. "
            "Full-thickness excision of the lesion was carried down to the pre-pectoral fascia. "
            "Specimen oriented with standard surgical sutures (superior, lateral, deep) and submitted for surgical pathology.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "A separate transverse incision in the lower right axilla was performed. "
            "Using the handheld gamma probe, two hot sentinel lymph nodes were identified, dissected free, "
            "and sent for permanent histopathological evaluation.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(
        Paragraph(
            "Hemostasis achieved with electrocautery. Surgical counts verified correct. "
            "Wounds closed in anatomical layers using absorbable sutures. Sterile dressings applied.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("DOCUMENTED TEXT ANCHOR", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Procedure note documents: Right breast partial mastectomy and sentinel lymph node biopsy completed.",
            styles["HighlightedText"],
        )
    )
    story.append(Spacer(1, 20))

    story.append(Paragraph("ATTENDING SURGEON SIGNATURE", styles["SectionTitle"]))
    story.append(Paragraph("Attending Surgical Oncologist, Sunrise Oncology Centre", styles["Body"]))
    story.append(Paragraph("Operative Record Completed: 2026-01-20 15:00 EST", styles["Body"]))

    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_007(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 007: Referral Letter (1 page) - Referral to Radiation Oncology."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("CLINICAL REFERRAL & CONSULTATION REQUEST", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Department of Surgical Oncology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("REFERRAL SUMMARY", styles["SectionTitle"]))
    story.append(Paragraph("<b>Referring Clinician:</b> Surgical Oncology Service, Sunrise Oncology Centre", styles["Body"]))
    story.append(
        Paragraph(
            "<b>Referred To:</b> Department of Radiation Oncology, Sunrise Oncology Centre",
            styles["HighlightedText"],
        )
    )
    story.append(Paragraph("<b>Referral Request Date:</b> 2026-01-21", styles["Body"]))
    story.append(Paragraph("<b>Referral Status:</b> scheduled", styles["Body"]))
    story.append(Spacer(1, 10))

    story.append(Paragraph("CLINICAL REASON FOR REFERRAL", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Referral letter documents request for adjuvant radiation oncology consultation. "
            "Patient is status-post right partial mastectomy on 2026-01-20. "
            "Requesting formal evaluation for post-operative adjuvant external beam radiation therapy planning.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("ENCLOSED DOCUMENTATION", styles["SectionTitle"]))
    story.append(Paragraph("- Operative note dated 2026-01-20 (doc-006)", styles["Body"]))
    story.append(Paragraph("- Baseline imaging CT report dated 2026-01-14 (doc-004)", styles["Body"]))
    story.append(Paragraph("- Biopsy pathology report dated 2026-01-08 (doc-002)", styles["Body"]))
    story.append(Spacer(1, 20))

    story.append(Paragraph("REFERRING PHYSICIAN SIGNATURE", styles["SectionTitle"]))
    story.append(Paragraph("Surgical Oncology Department, Sunrise Oncology Centre", styles["Body"]))
    story.append(Paragraph("Dispatched: 2026-01-21 09:15 EST", styles["Body"]))

    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_008(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 008: Laboratory Report (1 page) - Post-operative follow-up Hemoglobin."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("GREEN VALLEY DIAGNOSTIC CENTRE", styles["DocHeader"]))
    story.append(Paragraph("POST-OPERATIVE FOLLOW-UP LABORATORY REPORT", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Green Valley Diagnostic Centre",
            dept="Department of Clinical Hematology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("SPECIMEN & COLLECTION INFORMATION", styles["SectionTitle"]))
    story.append(Paragraph("<b>Collection Date/Time:</b> 2026-02-05 09:15 EST | <b>Specimen Type:</b> Whole Blood (K2-EDTA)", styles["Body"]))
    story.append(Paragraph("<b>Clinical Indication:</b> Post-operative routine hematology evaluation.", styles["Body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("HEMATOLOGY PROFILE RESULTS", styles["SectionTitle"]))
    hem_data = [
        ["Test Name", "Result Value", "Unit", "Documented Reference Range", "Status"],
        ["Hemoglobin", "12.8", "g/dL", "12.0 - 15.5 g/dL", "Completed"],
        ["Hematocrit", "38.2", "%", "36.0 - 46.0 %", "Completed"],
        ["Red Blood Cell Count (RBC)", "4.21", "x10^6/uL", "3.80 - 5.10 x10^6/uL", "Completed"],
        ["White Blood Cell Count (WBC)", "6.1", "x10^3/uL", "4.5 - 11.0 x10^3/uL", "Completed"],
        ["Platelet Count", "255", "x10^3/uL", "150 - 450 x10^3/uL", "Completed"],
    ]
    ht = Table(hem_data, colWidths=[150, 80, 60, 162, 80])
    ht.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
                ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F2F4F4")),
            ]
        )
    )
    story.append(ht)
    story.append(Spacer(1, 10))

    story.append(Paragraph("DOCUMENTED TEXT ANCHOR", styles["SectionTitle"]))
    story.append(Paragraph("Laboratory report records: Hemoglobin value 12.8 g/dL", styles["HighlightedText"]))
    story.append(Spacer(1, 15))

    story.append(Paragraph("LABORATORY DIRECTOR VERIFICATION", styles["SectionTitle"]))
    story.append(Paragraph("Certified by: Laboratory Hematologist, Green Valley Diagnostic Centre", styles["Body"]))
    story.append(Paragraph("Report Validated: 2026-02-05 13:40 EST", styles["Body"]))
    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Green Valley Diagnostic Centre",
        ),
    )


def generate_doc_009(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 009: Follow-up Visit Note (2 pages) - Surgical oncology follow-up & RT planning order."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("SURGICAL ONCOLOGY POST-OPERATIVE FOLLOW-UP NOTE", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Department of Surgical Oncology",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("ENCOUNTER & CLINICAL REVIEW", styles["SectionTitle"]))
    story.append(Paragraph("<b>Visit ID:</b> VIS-002 | <b>Visit Type:</b> Post-Operative Follow-Up", styles["Body"]))
    story.append(
        Paragraph(
            "Post-operative surgical oncology follow-up consultation. "
            "Patient seen in clinic approximately 2.5 weeks following right partial mastectomy and sentinel lymph node dissection.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("WOUND & PHYSICAL EXAMINATION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "<b>Surgical Site:</b> Right breast incision clean, dry, and intact with mild healing erythema. "
            "No seroma or hematoma. Right axillary incision is healing appropriately without tenderness.",
            styles["Body"],
        )
    )
    story.append(
        Paragraph(
            "<b>Systemic Review:</b> Pain adequately managed with oral non-opioid analgesics. No fever or chills reported.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("MEDICATION VERIFICATION", styles["SectionTitle"]))
    story.append(Paragraph("<b>Active Medication:</b> Tamoxifen 20 mg oral daily continued as prescribed on 2026-01-15.", styles["Body"]))

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    story.append(Paragraph("INVESTIGATION ORDERS PLACED", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "<b>Ordered Investigation:</b> CT Simulation Planning Scan for Adjuvant Radiotherapy<br/>"
            "<b>Status:</b> ordered<br/>"
            "<b>Ordered Date:</b> 2026-02-07<br/>"
            "<b>Result Date:</b> null (pending scheduling)",
            styles["HighlightedText"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("MULTIDISCIPLINARY CARE COORDINATION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Case reviewed. Patient to complete radiation oncology simulation scan. "
            "Next surgical oncology surveillance visit planned in 3 months.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 30))

    story.append(Paragraph("CLINICIAN SIGNATURE", styles["SectionTitle"]))
    story.append(Paragraph("Attending Surgical Oncologist, Sunrise Oncology Centre", styles["Body"]))
    story.append(Paragraph("Encounter Finalized: 2026-02-07 14:30 EST", styles["Body"]))
    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def generate_doc_010(output_path: Path, meta: Dict[str, Any], styles: Dict[str, ParagraphStyle]) -> None:
    """Doc 010: Discharge Summary (3 pages) - Surgical episode discharge."""
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=55,
        bottomMargin=55,
    )
    story: List[Any] = []

    # PAGE 1: Admission & Surgical Episode Course
    story.append(Paragraph("SUNRISE ONCOLOGY CENTRE", styles["DocHeader"]))
    story.append(Paragraph("INPATIENT SURGICAL ONCOLOGY DISCHARGE SUMMARY", styles["DocSubHeader"]))
    story.append(Spacer(1, 6))
    story.append(
        build_meta_table(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            doc_type=meta["document_type"],
            facility="Sunrise Oncology Centre",
            dept="Inpatient Surgical Oncology Service",
        )
    )
    story.append(Spacer(1, 10))

    story.append(Paragraph("EPISODE & ADMISSION INFORMATION", styles["SectionTitle"]))
    story.append(Paragraph("<b>Admission Date:</b> 2026-01-20 | <b>Discharge Finalized:</b> 2026-02-10", styles["Body"]))
    story.append(Paragraph("<b>Primary Service:</b> Department of Surgical Oncology", styles["Body"]))
    story.append(Paragraph("<b>Procedure Performed:</b> Right partial mastectomy with sentinel lymph node biopsy on 2026-01-20", styles["Body"]))
    story.append(Spacer(1, 8))

    story.append(Paragraph("HOSPITAL COURSE SUMMARY", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "The patient underwent planned surgical intervention on 2026-01-20 under general anesthesia. "
            "Post-operative recovery in PACU was uncomplicated. Vital signs remained stable throughout hospitalization. "
            "Surgical drains were removed per protocol. Tolerated regular oral diet and mobilized independently.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("DOCUMENTED LAB REVIEW PRIOR TO DISCHARGE", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Post-operative laboratory testing on 2026-02-05 recorded Hemoglobin at 12.8 g/dL with stable electrolyte panel. "
            "No evidence of surgical site infection or systemic complications during the episode.",
            styles["Body"],
        )
    )

    # PAGE BREAK to ensure Page 2
    story.append(PageBreak())

    # PAGE 2: Discharge instructions, Anchor, Investigations
    story.append(Paragraph("DISCHARGE STATUS & SUMMARY RECORD", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Discharge summary records surgical episode completion and scheduled radiation oncology planning.",
            styles["HighlightedText"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("DISCHARGE MEDICATIONS RECONCILIATION", styles["SectionTitle"]))
    dis_meds = [
        ["Medication Name", "Strength", "Dose & Frequency", "Status"],
        ["Tamoxifen", "20 mg", "1 tablet orally daily", "continued"],
        ["Acetaminophen", "500 mg", "1-2 tablets orally every 6 hours PRN mild pain", "as needed"],
    ]
    dt = Table(dis_meds, colWidths=[150, 80, 222, 80])
    dt.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]
        )
    )
    story.append(dt)
    story.append(Spacer(1, 10))

    story.append(Paragraph("PENDING & SCHEDULED INVESTIGATIONS", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "1. <b>CT Simulation Planning Scan:</b> Ordered on 2026-02-07 for radiation therapy localization.<br/>"
            "2. <b>Mammography Surveillance:</b> Scheduled at 6 months post-operatively.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 8))

    story.append(Paragraph("PATIENT DISCHARGE INSTRUCTIONS", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "Patient instructed regarding wound care, activity limitations (no heavy lifting > 10 lbs on right arm for 2 weeks), "
            "and signs of infection requiring immediate contact.",
            styles["Body"],
        )
    )

    # PAGE BREAK to ensure Page 3
    story.append(PageBreak())

    # PAGE 3: Follow-up Appointments & Attending Physician Sign-Off
    story.append(Paragraph("OUTPATIENT CARE COORDINATION & FOLLOW-UP SCHEDULE", styles["SectionTitle"]))
    appts = [
        ["Specialty / Service", "Scheduled Facility", "Date / Time", "Contact"],
        ["Radiation Oncology", "Sunrise Oncology Centre", "2026-02-18 10:00 EST", "Clinic Ext. 4100"],
        ["Medical Oncology", "Sunrise Oncology Centre", "2026-03-05 14:00 EST", "Clinic Ext. 4200"],
        ["Surgical Oncology", "Sunrise Oncology Centre", "2026-05-12 11:30 EST", "Clinic Ext. 4300"],
    ]
    at = Table(appts, colWidths=[140, 160, 132, 100])
    at.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2C3E50")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")),
            ]
        )
    )
    story.append(at)
    story.append(Spacer(1, 20))

    story.append(Paragraph("FORMAL DISCHARGE CERTIFICATION", styles["SectionTitle"]))
    story.append(
        Paragraph(
            "The patient was discharged in stable clinical condition. "
            "Discharge instructions and prescription counseling were provided.",
            styles["Body"],
        )
    )
    story.append(Spacer(1, 40))

    story.append(Paragraph("Attending Physician: Inpatient Surgical Oncology Director", styles["Body"]))
    story.append(Paragraph("Sunrise Oncology Centre — Finalized: 2026-02-10 11:00 EST", styles["Body"]))

    doc.build(
        story,
        canvasmaker=NumberedCanvas.create_factory(
            doc_id=meta["document_id"],
            doc_date=meta["document_date"],
            facility_name="Sunrise Oncology Centre",
        ),
    )


def main() -> None:
    """Main generation entry point."""
    base_dir = Path(__file__).resolve().parent.parent
    ground_truth_path = base_dir / "data" / "ground_truth" / "patient_001.json"
    output_dir = base_dir / "data" / "documents"
    output_dir.mkdir(parents=True, exist_ok=True)

    if not ground_truth_path.is_file():
        raise FileNotFoundError(f"Ground truth not found at {ground_truth_path}")

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    # Styles
    sample_styles = getSampleStyleSheet()

    styles = {
        "DocHeader": ParagraphStyle(
            "DocHeader",
            parent=sample_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1B4F72"),
            alignment=1,  # Center
        ),
        "DocSubHeader": ParagraphStyle(
            "DocSubHeader",
            parent=sample_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#2C3E50"),
            alignment=1,
        ),
        "SectionTitle": ParagraphStyle(
            "SectionTitle",
            parent=sample_styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#1A5276"),
            spaceBefore=4,
            spaceAfter=3,
        ),
        "Body": ParagraphStyle(
            "Body",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#2C3E50"),
            spaceAfter=2,
        ),
        "HighlightedText": ParagraphStyle(
            "HighlightedText",
            parent=sample_styles["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#17202A"),
            backColor=colors.HexColor("#EAF2F8"),
            borderColor=colors.HexColor("#A9CCE3"),
            borderWidth=0.5,
            borderPadding=4,
            spaceBefore=3,
            spaceAfter=3,
        ),
    }

    doc_generators = {
        "doc-001": generate_doc_001,
        "doc-002": generate_doc_002,
        "doc-003": generate_doc_003,
        "doc-004": generate_doc_004,
        "doc-005": generate_doc_005,
        "doc-006": generate_doc_006,
        "doc-007": generate_doc_007,
        "doc-008": generate_doc_008,
        "doc-009": generate_doc_009,
        "doc-010": generate_doc_010,
    }

    print(f"Loaded ground truth for patient {ground_truth['patient']['patient_id']}")
    print(f"Generating 10 PDFs into {output_dir}...")

    for doc_meta in ground_truth["patient"]["documents"]:
        doc_id = doc_meta["document_id"]
        # Required format: doc-xxx_filename.pdf
        out_filename = f"{doc_id}_{doc_meta['file_name']}"
        out_file = output_dir / out_filename

        generator = doc_generators.get(doc_id)
        if not generator:
            raise KeyError(f"No generator mapped for document {doc_id}")

        generator(out_file, doc_meta, styles)
        print(f"  [OK] Generated {out_filename} (expected {doc_meta['page_count']} pages)")

    print("All synthetic PDFs successfully generated.")


if __name__ == "__main__":
    main()
