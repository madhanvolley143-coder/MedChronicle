# Documentation & Information Flags

- **Patient ID:** `SYN-CANCER-001`
- **Total Flags Identified:** 2
- **Flag Types Present:** `medication_documentation_mismatch`, `missing_result`

> [!NOTE]
> All flags are strictly framed as **documentation and information-gap notifications**.
> JourneyBrief records documentation observations only and does not perform clinical triage or score medical severity.

---

## Flag Category: Medication Documentation Mismatch

### [INFORMATIONAL] Medication Status Transition Documented: Tamoxifen
- **Description:** Medication 'Tamoxifen' is documented with multiple status entries (continued, started) across different care encounters. No inference is made regarding medication administration.
- **Relevant Sources:** doc-005 (p. 1), doc-009 (p. 1), doc-010 (p. 2)

## Flag Category: Missing Result

### [INFORMATIONAL] Documented Order Awaiting Result: Diagnostic Mammogram and Breast Ultrasound
- **Description:** Investigation 'Diagnostic Mammogram and Breast Ultrasound' is documented as ordered on 2026-01-05. Result not found in currently processed records.
- **Relevant Sources:** doc-001 (p. 2)
