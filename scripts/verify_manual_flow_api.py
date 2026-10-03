"""API test for the 17-step manual flow."""
import json
from pathlib import Path
import urllib.request
import requests

PATIENT_ID = "SYN-CANCER-001"
BASE_URL = "http://127.0.0.1:8000"

# Step 1: Reset demo data
res = requests.post(f"{BASE_URL}/api/patient/{PATIENT_ID}/reset")
print("Reset status:", res.status_code, res.json())

# Step 2: Confirm 10 documents, baseline timeline count, baseline changes, baseline flags
brief_res = requests.get(f"{BASE_URL}/api/patient/{PATIENT_ID}/brief").json()
print("Baseline source docs:", brief_res["header"]["source_documents_count"])
print("Baseline timeline:", brief_res["header"]["total_timeline_events"])
print("Baseline changes:", len(brief_res["what_changed"]))
print("Baseline flags:", len(brief_res["documentation_flags"]))
print("Baseline context:", brief_res["consultation_context"])

# Step 3 & 4: Upload 6 files from test documents folder
files_dir = Path(r"D:\Downloads\JourneyBrief_Manual_Test_Documents")
file_names = [
    "01_2026-01-05_consultation_note.pdf",
    "02_2026-01-08_pathology_report.pdf",
    "03_2026-01-10_baseline_lab_report.pdf",
    "04_2026-01-14_scanned_imaging_report.pdf",
    "05_2026-01-15_prescription.jpg",
    "06_2026-02-05_followup_lab_report.pdf",
]

files_to_upload = []
open_fps = []
for name in file_names:
    p = files_dir / name
    if not p.is_file():
        p = Path("data/messy_documents") / name
    fp = open(p, "rb")
    open_fps.append(fp)
    mime = "application/pdf" if name.endswith(".pdf") else "image/jpeg"
    files_to_upload.append(("files", (name, fp, mime)))

upload_res = requests.post(f"{BASE_URL}/api/patient/{PATIENT_ID}/documents/upload", files=files_to_upload)
for fp in open_fps:
    fp.close()

print("Upload response code:", upload_res.status_code)
upload_json = upload_res.json()
print("Batch processed docs count:", upload_json.get("total_documents"))

# Step 5 & 6 & 7: Confirm 16 source documents, dynamic timeline count, dynamic changes, dynamic flags
brief_after = requests.get(f"{BASE_URL}/api/patient/{PATIENT_ID}/brief").json()
print("Updated source docs count:", brief_after["header"]["source_documents_count"])
print("Updated timeline count:", brief_after["header"]["total_timeline_events"])
print("Updated changes count:", len(brief_after["what_changed"]))
print("Updated flags count:", len(brief_after["documentation_flags"]))

# Step 8 & 9: Confirm What Changed
changes_entities = [c["entity_name"] for c in brief_after["what_changed"]]
print("Changes present:", changes_entities)
print("Is Hemoglobin in changes?", "Hemoglobin" in changes_entities)
print("Is Platelet Count in changes?", any("platelet" in c.lower() for c in changes_entities))
print("Is ALT (SGPT) 22->22 in changes?", any("alt" in c.lower() for c in changes_entities))
print("Is CA 15-3 22.4->22.4 in changes?", any("ca 15-3" in c.lower() for c in changes_entities))

# Step 10 & 11: Sources
sources = [d["file_name"] for d in brief_after["source_documents"]]
print("Total sources in brief:", len(sources))
for fn in file_names:
    print(f"Is {fn} in sources?", fn in sources)

# Step 12 & 13: Fetch PDF and JPG
r_pdf = requests.get(f"{BASE_URL}/api/patient/{PATIENT_ID}/documents/01_2026-01-05_consultation_note.pdf")
print("PDF retrieval status:", r_pdf.status_code, r_pdf.headers.get("Content-Type"))

r_jpg = requests.get(f"{BASE_URL}/api/patient/{PATIENT_ID}/documents/05_2026-01-15_prescription.jpg")
print("JPG retrieval status:", r_jpg.status_code, r_jpg.headers.get("Content-Type"))

# Step 14 & 15: Doctor review
rev_res = requests.post(f"{BASE_URL}/api/patient/{PATIENT_ID}/review", json={"review_status": "reviewed"}).json()
print("Review status updated:", rev_res.get("review_status"))

# Step 16 & 17: Reset
reset_final = requests.post(f"{BASE_URL}/api/patient/{PATIENT_ID}/reset").json()
brief_final = requests.get(f"{BASE_URL}/api/patient/{PATIENT_ID}/brief").json()
print("Final reset source docs count:", brief_final["header"]["source_documents_count"])
print("Final reset timeline count:", brief_final["header"]["total_timeline_events"])
