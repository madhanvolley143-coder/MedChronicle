"""Synthetic messy document generator for JourneyBrief.

Generates realistic messy test inputs from existing synthetic clean PDFs:
1. Scanned PDF (raster images embedded in PDF with NO selectable text layer)
2. Rotated PDF (page orientation rotated 90 degrees)
3. Low-resolution image (low pixel dimensions)
4. Document photo (JPEG format with photo compression)
5. Document scan (PNG format)
6. Multilingual Tamil/English document (contains Tamil headers and English clinical facts)

STRICT BOUNDARY:
- Uses ONLY synthetic medical information from existing synthetic files.
- Never uses real patient data.
- Stores output in data/messy_documents/ without modifying clean PDFs.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pymupdf


def generate_messy_documents(
    source_dir: Path = Path("data/documents"),
    output_dir: Path = Path("data/messy_documents"),
) -> None:
    """Generate sample messy documents for OCR and ingestion testing."""
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    doc_003_path = source_dir / "doc-003_laboratory_report_2026-01-10.pdf"
    doc_001_path = source_dir / "doc-001_visit_note_2026-01-05.pdf"

    if not doc_003_path.is_file() or not doc_001_path.is_file():
        raise FileNotFoundError("Source synthetic PDFs not found in data/documents/.")

    # -----------------------------------------------------------------
    # 1. Scanned PDF (True raster-only PDF with NO selectable text)
    # -----------------------------------------------------------------
    src_doc = pymupdf.open(str(doc_003_path))
    page = src_doc[0]
    pix = page.get_pixmap(dpi=150)
    img_bytes = pix.tobytes("png")
    src_doc.close()

    scanned_pdf_path = output_dir / "messy_scanned_lab_report.pdf"
    new_pdf = pymupdf.open()
    rect = pymupdf.Rect(0, 0, pix.width, pix.height)
    new_page = new_pdf.new_page(width=rect.width, height=rect.height)
    new_page.insert_image(rect, stream=img_bytes)
    new_pdf.save(str(scanned_pdf_path))
    new_pdf.close()
    print(f"Generated: {scanned_pdf_path}")

    # -----------------------------------------------------------------
    # 2. Rotated PDF (Page rotated by 90 degrees)
    # -----------------------------------------------------------------
    rot_doc = pymupdf.open(str(doc_001_path))
    rot_doc[0].set_rotation(90)
    rot_pdf_path = output_dir / "messy_rotated_visit_note.pdf"
    rot_doc.save(str(rot_pdf_path))
    rot_doc.close()
    print(f"Generated: {rot_pdf_path}")

    # -----------------------------------------------------------------
    # 3. Document Scan (PNG format)
    # -----------------------------------------------------------------
    png_path = output_dir / "messy_document_scan.png"
    pix.save(str(png_path))
    print(f"Generated: {png_path}")

    # -----------------------------------------------------------------
    # 4. Document Photo (JPEG format with mobile photo compression)
    # -----------------------------------------------------------------
    jpeg_path = output_dir / "messy_document_photo.jpg"
    pil_img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    pil_img.save(str(jpeg_path), "JPEG", quality=65)
    print(f"Generated: {jpeg_path}")

    # -----------------------------------------------------------------
    # 5. Low-Resolution Image (Reduced dimension for quality check)
    # -----------------------------------------------------------------
    low_res_path = output_dir / "messy_low_res_lab.png"
    low_res_img = pil_img.resize((260, 360), Image.Resampling.LANCZOS)
    low_res_img.save(str(low_res_path))
    print(f"Generated: {low_res_path}")

    # -----------------------------------------------------------------
    # 6. Multilingual Tamil + English Document
    # -----------------------------------------------------------------
    multi_path = output_dir / "messy_tamil_english_report.png"
    multi_img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(multi_img)

    # Synthetic document text with Tamil hospital header & English clinical details
    lines = [
        "Sunrise Oncology Centre / சன்ரைஸ் புற்றுநோய் மையம்",
        "Patient ID: SYN-CANCER-001",
        "Date of Examination: 2026-01-10",
        "Department: Laboratory Medicine / ஆய்வகப் பிரிவு",
        "Test Name: Complete Blood Count (CBC)",
        "Hemoglobin (Hb): 13.4 g/dL",
        "Platelet Count: 250,000 /mcL",
        "White Blood Cell (WBC): 7,200 /mcL",
        "Status: Verified / சரிபார்க்கப்பட்டது",
        "Notes: Synthetic clinical test record for evaluation.",
    ]

    y = 50
    for line in lines:
        draw.text((50, y), line, fill=(0, 0, 0))
        y += 40

    multi_img.save(str(multi_path))
    print(f"Generated: {multi_path}")

    print("\nAll 6 synthetic messy documents generated successfully in data/messy_documents/!")


if __name__ == "__main__":
    generate_messy_documents()
