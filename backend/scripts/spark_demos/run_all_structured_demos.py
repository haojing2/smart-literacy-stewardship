"""Run every Pydantic-validated Spark provider demo sequentially.

This intentionally excludes 01/02 because they demonstrate raw content rather
than structured provider contracts. Each demo is independent and writes no DB.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

from demo_common import show


DEMO_FILES = [
    "03_analyze_research.py", "04_research_chat.py", "05_generate_evidence_card.py",
    "06_diagnose_course_context.py", "07_generate_course_objectives.py",
    "08_recommend_course_pedagogy.py", "09_generate_course_assessments.py",
    "10_generate_course_blueprint.py", "11_regenerate_course_activity.py",
    "12_check_course_quality.py", "13_recommend_resource_settings.py",
    "14_generate_teaching_resource.py", "15_transform_resource_block.py",
    "16_review_teaching_resource.py", "17_propose_resource_revision.py",
]


async def main() -> int:
    directory = Path(__file__).resolve().parent
    failures = 0
    for filename in DEMO_FILES:
        module_name = f"spark_demo_{filename.removesuffix('.py')}"
        spec = importlib.util.spec_from_file_location(module_name, directory / filename)
        if spec is None or spec.loader is None:
            print(f"Unable to load {filename}", file=sys.stderr)
            failures += 1
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        print(f"\n=== {filename} ===")
        try:
            show(await module.demo())
        except Exception as exc:
            failures += 1
            print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    return failures


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
