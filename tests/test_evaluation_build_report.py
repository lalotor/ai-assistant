"""Unit tests for evaluation.build_report's file-handling seam.

build_report_from_results_file(results_path, name, title) is the only
function under test here (real filesystem I/O via tmp_path, per this
repo's established convention - see tests/rag/test_ingestion.py). The
underlying aggregation logic (build_baseline_report) is already covered
by tests/test_evaluation_report.py and is not re-tested here.
"""
import json

import pytest

from evaluation.build_report import (
    build_report_from_results_file,
    build_report_from_results_files,
    _latest_results_file,
)


def make_results_file(tmp_path, filename="eval_2026-01-01_00-00-00.json") -> str:
    data = {
        "summary": {"evaluated": 1, "passed": 1},
        "results": [
            {
                "score": 1.0,
                "score_sources": 1.0,
                "status": "pass",
                "timing_metrics": {
                    "trace": {"duration_ms": 1000.0},
                    "planner": {"duration_ms": 200.0},
                    "worker": {"duration_ms": 600.0},
                    "reviewer": {"duration_ms": 200.0},
                },
                "llm_usage": {
                    "planner": {"llm_calls": 1, "token_usage": {"input_tokens": 100, "output_tokens": 20, "model": "gpt-5.4-mini"}},
                    "worker": {"llm_calls": 1, "token_usage": {"input_tokens": 500, "output_tokens": 80, "model": "gpt-5.4-mini"}},
                    "reviewer": {"llm_calls": 1, "token_usage": {"input_tokens": 150, "output_tokens": 40, "model": "gpt-5.4-mini"}},
                    "total_llm_calls": 3,
                },
            }
        ],
    }
    path = tmp_path / filename
    path.write_text(json.dumps(data), encoding="utf-8")
    return str(path)


@pytest.mark.unit
class TestBuildReportFromResultsFile:
    def test_writes_a_json_and_a_markdown_report(self, tmp_path, mocker):
        results_path = make_results_file(tmp_path)
        reports_dir = tmp_path / "reports"
        mocker.patch("evaluation.build_report.REPORTS_DIR", str(reports_dir))

        json_path, md_path = build_report_from_results_file(results_path, name="baseline", title="Baseline run")

        assert (reports_dir / "baseline.json").exists()
        assert (reports_dir / "baseline.md").exists()
        assert json_path.endswith("baseline.json")
        assert md_path.endswith("baseline.md")

    def test_json_report_contains_the_source_results_file_reference(self, tmp_path, mocker):
        results_path = make_results_file(tmp_path)
        reports_dir = tmp_path / "reports"
        mocker.patch("evaluation.build_report.REPORTS_DIR", str(reports_dir))

        json_path, _ = build_report_from_results_file(results_path, name="baseline", title="Baseline run")

        report = json.loads((reports_dir / "baseline.json").read_text())
        assert "source_results_files" in report
        assert report["latency_ms"]["avg"] == 1000.0

    def test_markdown_report_contains_the_given_title(self, tmp_path, mocker):
        results_path = make_results_file(tmp_path)
        reports_dir = tmp_path / "reports"
        mocker.patch("evaluation.build_report.REPORTS_DIR", str(reports_dir))

        _, md_path = build_report_from_results_file(results_path, name="optimized", title="Optimized run")

        text = (reports_dir / "optimized.md").read_text()
        assert "# Optimized run" in text


@pytest.mark.unit
class TestBuildReportFromResultsFiles:
    def test_merges_results_across_multiple_files_before_aggregating(self, tmp_path, mocker):
        path_1 = make_results_file(tmp_path, filename="eval_run_1.json")
        path_2 = make_results_file(tmp_path, filename="eval_run_2.json")
        reports_dir = tmp_path / "reports"
        mocker.patch("evaluation.build_report.REPORTS_DIR", str(reports_dir))

        json_path, _ = build_report_from_results_files([path_1, path_2], name="baseline", title="Baseline run")

        report = json.loads((reports_dir / "baseline.json").read_text())
        # Each fixture file has 1 result; merging 2 files means 2 evaluated items
        assert report["evaluated"] == 2
        assert len(report["source_results_files"]) == 2


@pytest.mark.unit
class TestLatestResultsFile:
    def test_returns_the_most_recently_named_results_file(self, tmp_path, mocker):
        mocker.patch("evaluation.build_report.RESULTS_DIR", str(tmp_path))
        (tmp_path / "eval_2026-01-01_00-00-00.json").write_text("{}", encoding="utf-8")
        (tmp_path / "eval_2026-02-01_00-00-00.json").write_text("{}", encoding="utf-8")

        latest = _latest_results_file()

        assert latest.endswith("eval_2026-02-01_00-00-00.json")

    def test_raises_a_clear_error_when_no_results_files_exist(self, tmp_path, mocker):
        mocker.patch("evaluation.build_report.RESULTS_DIR", str(tmp_path))

        with pytest.raises(FileNotFoundError, match="No results files found"):
            _latest_results_file()
