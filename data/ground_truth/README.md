# Synthetic Cancer Care Ground Truth Dataset

## 1. 100% Synthetic Data Declaration

> [!IMPORTANT]
> **Strict Synthetic Data Policy**:
> This dataset (`patient_001.json`) is **100% synthetic**.
> - Contains **no real patient information**.
> - Contains **no identifiable health records**.
> - All names, dates, identification numbers, and facility names (e.g., *Sunrise Oncology Centre*, *Green Valley Diagnostic Centre*) are fictional.

---

## 2. Dataset Overview

- **Patient Identifier**: `SYN-CANCER-001`
- **Synthetic Flag**: `true`
- **Document Count**: 10 synthetic documents
- **Timeline Events**: 10 chronological events across multiple encounter dates (January 2026 – February 2026)
- **Domain**: Oncology / Breast Cancer Care consultation readiness

### Document Inventory

| Document ID | File Name | Document Type | Date | Pages |
| :--- | :--- | :--- | :--- | :--- |
| `doc-001` | `visit_note_2026-01-05.pdf` | `visit_note` | 2026-01-05 | 2 |
| `doc-002` | `pathology_report_2026-01-08.pdf` | `pathology_report` | 2026-01-08 | 2 |
| `doc-003` | `laboratory_report_2026-01-10.pdf` | `laboratory_report` | 2026-01-10 | 1 |
| `doc-004` | `imaging_report_2026-01-14.pdf` | `imaging_report` | 2026-01-14 | 2 |
| `doc-005` | `prescription_2026-01-15.pdf` | `prescription` | 2026-01-15 | 1 |
| `doc-006` | `procedure_note_2026-01-20.pdf` | `procedure_note` | 2026-01-20 | 2 |
| `doc-007` | `referral_letter_2026-01-21.pdf` | `referral_letter` | 2026-01-21 | 1 |
| `doc-008` | `laboratory_report_2026-02-05.pdf` | `laboratory_report` | 2026-02-05 | 1 |
| `doc-009` | `followup_visit_2026-02-07.pdf` | `visit_note` | 2026-02-07 | 2 |
| `doc-010` | `discharge_summary_2026-02-10.pdf` | `discharge_summary` | 2026-02-10 | 3 |

---

## 3. Strict Safety Boundaries

JourneyBrief is an assistive consultation-readiness tool that extracts and organizes **documented facts only**.

The ground truth explicitly adheres to the following principles:
- **No AI Clinical Interpretation**: No inferred cancer staging, grading, or diagnostic conclusions.
- **No Inferred Prognosis or Risk Scoring**: No assessment of clinical risk, disease severity, or disease progression.
- **No Treatment Recommendations**: No drug regimen or surgical suggestions.
- **No Treatment Effectiveness Scoring**: No classification of response (e.g. "poor response", "treatment working").
- **Factual Documentation Only**: Reference ranges are stored as literal text; findings reflect explicit statements recorded in source notes.

---

## 4. Purpose of Ground Truth

This ground-truth file serves as the gold-standard reference benchmark for the JourneyBrief evaluation harness:
1. **OCR & Text Extraction Evaluation**: Validating character accuracy and bounding box alignments against source pages.
2. **Clinical Entity Extraction**: Measuring precision, recall, and F1 score across clinical facts (visits, pathology findings, laboratory results, imaging reports, medications, procedures, referrals, and investigations).
3. **Timeline Event Sequencing**: Evaluating chronological ordering and fidelity of reconstructed milestone events.
4. **Source Attribution & Provenance**: Ensuring every extracted datum maintains a valid, verifiable pointer to `document_id`, `file_name`, and `page_number`.
5. **Change Detection & Inconsistency Highlighting**: Comparing documented laboratory intervals (e.g. baseline vs. post-operative Hemoglobin) and follow-up orders without autonomous clinical judgment.
