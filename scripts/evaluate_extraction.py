"""CLI script to evaluate structured extraction outputs against ground truth.

Usage:
    python scripts/evaluate_extraction.py [--ground-truth PATH] [--structured-dir PATH] [--output-dir PATH]
"""

import argparse
import json
from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.evaluation import EvaluationService


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate JourneyBrief structured extractions against ground truth")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("data/ground_truth/patient_001.json"),
        help="Path to synthetic ground truth JSON",
    )
    parser.add_argument(
        "--structured-dir",
        type=Path,
        default=Path("data/structured"),
        help="Directory containing structured doc-XXX.json files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/evaluation"),
        help="Directory to save evaluation reports",
    )
    parser.add_argument(
        "--processing-time",
        type=float,
        default=None,
        help="Optional extraction processing time in seconds to record",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("JourneyBrief — Extraction Evaluation Pipeline")
    print("=" * 60)
    print(f"Ground Truth: {args.ground_truth}")
    print(f"Structured Directory: {args.structured_dir}")
    print(f"Output Directory: {args.output_dir}")

    evaluator = EvaluationService(
        ground_truth_path=args.ground_truth,
        structured_dir=args.structured_dir,
    )

    t0 = time.time()
    json_path, md_path = evaluator.save_reports(
        output_dir=args.output_dir,
        processing_time_seconds=args.processing_time,
    )
    elapsed = time.time() - t0

    # Load and print summary
    report = json.loads(json_path.read_text(encoding="utf-8"))
    doc_cov = report["document_coverage"]
    sf = report["summary_facts"]
    prov = report["provenance"]
    safety = report["safety"]
    conf = report["confidence"]

    print("\n" + "=" * 60)
    print("EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Documents Expected:    {report['documents_expected']}")
    print(f"Documents Successful:  {report['documents_successful']}")
    print(f"Documents Failed:      {report['documents_failed']}")
    print(f"Document Coverage:     {doc_cov['coverage_pct']}%")
    print("-" * 60)
    print(f"Total Expected Facts:  {sf['total_expected']}")
    print(f"Total Extracted Facts: {sf['total_extracted']}")
    print(f"Total Matched Facts:   {sf['total_matched']}")
    print(f"Total Missing Facts:   {sf['total_missing']}")
    print(f"Total Extra Facts:     {sf['total_extra']}")
    print(f"Fact Recall:           {sf['overall_recall_pct']}%")
    print("-" * 60)
    print(f"Source Provenance:     {'PASSED' if prov['passed'] else 'FAILED'} ({prov['provenance_accuracy_pct']}%)")
    print(f"Clinical Safety:       {'PASSED' if safety['passed'] else 'FAILED'} (Violations: {safety['violations_count']})")
    print(f"Average Confidence:    {conf['average_confidence']}")
    print(f"Facts at Confidence 1: {conf['facts_at_1_0']} ({conf['facts_at_1_0_pct']}%)")
    print("-" * 60)
    print(f"JSON Report Saved:     {json_path}")
    print(f"Markdown Report Saved: {md_path}")
    print(f"Evaluation Completed:  {elapsed:.2f}s")
    print("=" * 60)

    return 0 if (report["documents_failed"] == 0 and safety["passed"]) else 1


if __name__ == "__main__":
    sys.exit(main())
