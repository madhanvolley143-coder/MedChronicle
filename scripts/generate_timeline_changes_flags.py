"""CLI pipeline to generate patient timeline, what changed, and documentation flags.

Deterministic, rule-based execution on data/structured/ outputs without calling any LLM.

Usage:
    python scripts/generate_timeline_changes_flags.py
"""

from pathlib import Path
import sys
import time

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.change_detector import ChangeDetector
from app.services.flag_detector import FlagDetector
from app.services.timeline import TimelineEngine


def main() -> int:
    print("=" * 60)
    print("JourneyBrief — Timeline, Changes & Flags Engine")
    print("=" * 60)

    structured_dir = Path("data/structured")
    timeline_dir = Path("data/timeline")
    changes_dir = Path("data/changes")
    flags_dir = Path("data/flags")

    if not structured_dir.is_dir():
        print(f"Error: Structured directory not found at {structured_dir}", file=sys.stderr)
        return 1

    patient_id = "SYN-CANCER-001"
    t_start = time.time()

    # 1. Timeline Engine
    print("\n[1/3] Generating Chronological Patient Timeline...")
    timeline_engine = TimelineEngine(structured_dir=structured_dir)
    tl_json, tl_md = timeline_engine.save_timeline(output_dir=timeline_dir, patient_id=patient_id)
    tl_data = timeline_engine.build_timeline(patient_id=patient_id)
    print(f"      -> {tl_data.total_events} events ({tl_data.dated_events_count} dated, {tl_data.undated_events_count} undated)")
    print(f"      -> JSON: {tl_json}")
    print(f"      -> Markdown: {tl_md}")

    # 2. What Changed Engine
    print("\n[2/3] Detecting Documented Changes & Repeated Facts...")
    change_detector = ChangeDetector(structured_dir=structured_dir)
    ch_json, ch_md = change_detector.save_changes(output_dir=changes_dir, patient_id=patient_id)
    ch_data = change_detector.detect_changes(patient_id=patient_id)
    print(f"      -> {ch_data.total_changes_detected} comparisons across categories: {ch_data.categories_with_changes}")
    print(f"      -> JSON: {ch_json}")
    print(f"      -> Markdown: {ch_md}")

    # 3. Missing / Inconsistency Flags Engine
    print("\n[3/3] Identifying Documentation & Information Flags...")
    flag_detector = FlagDetector(structured_dir=structured_dir)
    fl_json, fl_md = flag_detector.save_flags(output_dir=flags_dir, patient_id=patient_id)
    fl_data = flag_detector.detect_flags(patient_id=patient_id)
    print(f"      -> {fl_data.total_flags} documentation flags identified: {fl_data.flag_types_present}")
    print(f"      -> JSON: {fl_json}")
    print(f"      -> Markdown: {fl_md}")

    elapsed = time.time() - t_start

    print("\n" + "=" * 60)
    print("PIPELINE EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Patient ID:                {patient_id}")
    print(f"Timeline Events Generated: {tl_data.total_events}")
    print(f"Documented Changes Found:  {ch_data.total_changes_detected}")
    print(f"Documentation Flags Found: {fl_data.total_flags}")
    print(f"Execution Time:            {elapsed:.3f} seconds (Deterministic, No LLM)")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
