# JourneyBrief — Hackathon Judge Q&A & Technical Defense Guide

This document provides concise, technically accurate answers to expected questions from hackathon judges, clinical evaluators, and system architects. Every answer reflects the actual implementation of JourneyBrief in Stage 18.

---

### 1. What problem are you solving?
Cancer care patients present with voluminous, fragmented medical histories: clinic consultation notes, pathology reports, serial blood work, PET/CT scans, and prescriptions scattered across multiple clinics and formats (PDFs, photocopies, images). Oncologists have only 10–15 minutes per consultation and cannot manually correlate historical records, track parameter shifts across documents, or verify pending items.

### 2. Who is the user?
Medical oncologists, surgical oncologists, radiation oncologists, oncology nurses, fellows, and clinical care navigators preparing for a patient consultation or multidisciplinary tumor board review.

### 3. Why is this needed?
Unorganized records cause consultation delays, repeat testing, missed historical baselines, and clinician burnout. Manual review of 100+ pages of unstructured scans is error-prone. JourneyBrief structures and indexes these documents into a verifiable consultation-readiness brief in seconds.

### 4. What makes JourneyBrief different from a normal chatbot?
Normal chatbots accept unconstrained prompts and output free-form, unverified prose with frequent hallucinations, missing source references, and dangerous clinical speculations. JourneyBrief is **not a chatbot**:
- It uses an LLM **only** for structured entity extraction into rigid Pydantic schemas.
- All timeline generation, parameter change detection, information gap flags, and brief synthesis are **100% deterministic rule-based algorithms**.
- Every single fact retains immutable source provenance (`document_id`, `file_name`, `page_number`).
- Clinicians review and verify extracted facts with a dedicated checklist before consultation.

### 5. Why Gemini?
Google Gemini 3.5 Flash-Lite provides high structured-extraction precision, sub-6-second processing speed per document, robust multimodal/OCR text handling, and strict adherence to JSON schemas via temperature `0.0`. It delivers high throughput at low computational latency.

### 6. Why not use an LLM to generate the entire summary?
Generating medical summaries end-to-end with an LLM is clinically unsafe:
- LLMs hallucinate clinical relationships, infer cancer stages, predict survival, or synthesize medical advice without explicit evidence.
- LLMs fail at deterministic temporal sorting across multiple documents.
- LLMs cannot guarantee exact provenance down to the page number for every stated fact.
In JourneyBrief, downstream synthesis is **code, not prompts**.

### 7. Why is the Timeline deterministic?
Medical timelines require absolute chronological consistency. Dates extracted from consultation notes, pathology reports, and laboratory tests are parsed into ISO dates (`YYYY-MM-DD`) and sorted deterministically. Undated records are partitioned into an undated group rather than having an LLM hallucinate or guess encounter dates.

### 8. Why is What Changed deterministic?
Clinicians need exact numeric and textual comparisons (e.g., Hemoglobin 13.4 g/dL on Jan 10 → 12.8 g/dL on Feb 5). A deterministic comparison engine extracts the previous and latest values, calculates objective differences, and preserves the source documents for both timestamps without interpreting whether the change represents clinical "improvement" or "progression".

### 9. How do you prevent hallucination?
- **Pydantic Validation**: `extra='forbid'` rejects any non-schema fields returned by the LLM.
- **Negative Prompting Constraints**: Extraction prompts forbid diagnosis, cancer staging inference, prognosis, severity scores, and treatment recommendations.
- **Source Grounding**: Facts without a valid `document_id`, `file_name`, and `page_number >= 1` fail validation and are rejected.
- **Deterministic Assembly**: Downstream brief text is assembled directly from validated Pydantic instances.

### 10. How do you maintain source traceability?
During ingestion, every document receives a unique `document_id`. Page numbers are tracked during extraction. When entities are instantiated, a `SourceReference` object is injected and validated. In the UI, clicking **"Open source page"** opens the exact document and page in an embedded viewer (`/documents/{doc_id}#page={page}`).

### 11. What happens when OCR is wrong?
- Tesseract calculates character- and word-level optical confidence scores (0.0 to 1.0).
- If OCR confidence falls below the technical threshold, the document receives a **Technical Quality Warning**: *"Technical document-quality warning: OCR confidence is low for this page. Please verify the extracted text against the original document."*
- Technical OCR confidence is strictly separated from LLM extraction confidence and is never portrayed as clinical certainty. The clinician is prompted to review the original page in the viewer.

### 12. What happens when a document is low quality?
The `DocumentQualityChecker` evaluates resolution (< 150 DPI), low text density, blank pages, and skewed orientation. Low-quality pages are processed defensively, assigned a `needs_review` status, and flagged with a non-clinical technical alert.

### 13. What happens when one document fails?
JourneyBrief features **per-document failure isolation**:
- In a multi-document batch, each document is ingested, classified, and extracted independently.
- If one document is corrupted or unsupported, its individual status is marked `failed` in the response, while the remaining valid documents are successfully processed, extracted, and integrated into the JourneyBrief. One failure never aborts or corrupts the entire batch.

### 14. How is doctor review implemented?
A dedicated Doctor Review checklist allows clinicians to inspect each extracted fact against its source document:
- Clinicians can click `[Verify]` (marking that the clinician confirmed the fact in the source document) or `[Needs Review]` (flagging for clarification).
- An overall review toggle tracks whether the patient journey is `PENDING REVIEW` or `REVIEWED`.
- "Verify" strictly indicates clinical document review; it does not approve treatments or make clinical decisions.

### 15. Why synthetic data?
To guarantee zero patient privacy/HIPAA violations during research, hackathon evaluation, and prototyping. All 10 documents for patient `SYN-CANCER-001` were programmatically generated with ReportLab to reflect realistic clinical oncological structures (infiltrating ductal carcinoma, pathology margins, receptor markers, CBC panels, Tamoxifen prescriptions) without using real patient data.

### 16. Can this use real hospital data?
Yes, in a future production phase. However, real-world deployment requires formal institutional review board (IRB) approval, business associate agreements (BAAs), HIPAA compliance auditing, on-premise or HIPAA-compliant cloud hosting, and EHR integration.

### 17. How will privacy be handled?
In production:
- On-premise deployment or zero-data-retention HIPAA-compliant enterprise LLM endpoints.
- Role-based access control (RBAC) ensuring only authorized care-team members can view patient records.
- De-identification / redaction of direct patient identifiers (Safe Harbor standard) prior to cloud processing.
- Full cryptographic audit trails of all document uploads and review actions.

### 18. Why not RAG (Retrieval-Augmented Generation)?
RAG is suitable for conversational search across thousands of pages, but poorly suited for structured consultation readiness:
- RAG retrieves chunked fragments, which frequently fragments timelines, separates lab test names from their dates, and loses chronological context.
- RAG synthesizes answers with free-form text, which risks hallucinated summaries.
- JourneyBrief requires **100% structured fact extraction** across all uploaded documents, not partial vector similarity lookups.

### 19. Why not a production database yet?
Stage 18 is a focused, hackathon-tested consultation-readiness prototype. Using structured JSON storage in `data/` maximizes auditability, portability, determinism, and zero-dependency reproducibility. Production database migration (PostgreSQL with row-level security) is part of the future roadmap.

### 20. How would you scale this?
1. **Asynchronous Task Queue**: Celery / Redis or AWS SQS for parallel document ingestion and background extraction.
2. **Horizontal Workers**: Distributed containerized OCR and extraction workers across multiple nodes.
3. **Database Tier**: PostgreSQL for structured facts with pgvector for optional semantic indexing.
4. **Caching**: Redis caching for parsed documents and rendered PDF pages.

### 21. What works offline?
- Ingestion of PDFs, PNG, JPG, JPEG.
- PyMuPDF text extraction.
- Tesseract OCR engine (local binary).
- Pydantic validation.
- Timeline generation, Change detection, Flag detection, and JourneyBrief synthesis.
- Doctor review service and JSON persistence.
- Ollama / Llama 3.1:8b local LLM structured extraction (when configured).

### 22. What does not work offline?
Google Gemini 3.5 Flash-Lite extraction requires active internet connectivity to communicate with Google's API endpoints. If offline, the system seamlessly falls back to Ollama / Llama 3.1:8b.

### 23. What is the Tamil OCR limitation?
Local Tesseract 5.5.3 contains `eng` (English) and `osd` (Orientation and Script Detection). The language pack `tam.traineddata` is **not installed** in the local tessdata directory. JourneyBrief truthfully and explicitly reports Tamil OCR as unavailable in the UI and documentation rather than claiming unverified multilingual capability.

### 24. What does the 100% recall metric actually mean?
It means that across the 10-document synthetic cancer-care evaluation dataset (`data/ground_truth/patient_001.json`), JourneyBrief's extraction pipeline successfully extracted 100% (12 out of 12) of the predefined gold-standard clinical benchmark facts with complete source provenance. **It measures extraction coverage on synthetic data; it is NEVER claimed as 100% clinical diagnostic accuracy.**

### 25. Is this a diagnostic system?
**NO.** JourneyBrief is strictly an assistive documentation tool. It extracts and organizes facts explicitly written in uploaded records. It does not diagnose, stage cancer, assess prognosis, or determine disease status.

### 26. Can it recommend treatment?
**NO.** JourneyBrief has strict negative guardrails in prompts, schemas, and algorithms prohibiting treatment recommendations, medication changes, surgical advice, or clinical guidance. The clinician is the sole decision-maker.

### 27. What are the current limitations?
1. Evaluated strictly on synthetic oncology records (`SYN-CANCER-001`).
2. Tamil OCR is unavailable until `tam.traineddata` is installed.
3. The source viewer displays the original document page, but pixel/bounding-box text highlighting on scanned PDFs is not yet implemented.
4. Uses local JSON prototype persistence rather than an enterprise database.
5. Documentation flags identify information gaps deterministically, not clinical risks.

### 28. What is the next production step?
1. **FHIR / HL7 Ingestion**: Direct integration with hospital EHRs (Epic, Cerner).
2. **Bounding-Box Highlighting**: Exact visual highlight coordinates rendered directly onto PDF pages in the source viewer.
3. **Multi-User Collaboration**: Attending oncologists, fellows, and nurses reviewing and annotating the brief with role-based sign-offs.
4. **Enterprise Database**: Migration to PostgreSQL with row-level encryption and HIPAA compliance auditing.
