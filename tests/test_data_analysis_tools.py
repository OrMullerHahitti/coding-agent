"""Tests for data analysis tools."""

from __future__ import annotations

import re

import pytest

from coding_agent.tools.data_analysis import (
    ClearDatasetsTool,
    DatasetDescribeTool,
    DatasetFilterTool,
    DatasetHeadTool,
    ExportDatasetTool,
    LoadDatasetTool,
    SaveHistogramPlotTool,
)
from coding_agent.tools.filesystem import configure_allowed_paths


def _extract_dataset_id(message: str) -> str:
    match = re.search(r"dataset_id=([0-9a-f]{6,})", message)
    if not match:
        raise AssertionError(f"Could not extract dataset_id from: {message}")
    return match.group(1)


@pytest.fixture(autouse=True)
def _clear_datasets_between_tests() -> None:
    ClearDatasetsTool().execute()


def test_load_csv_and_head(tmp_path) -> None:
    configure_allowed_paths([str(tmp_path)])

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,hello\n2,world\n", encoding="utf-8")

    msg = LoadDatasetTool().execute(path=str(csv_path), format="csv")
    dataset_id = _extract_dataset_id(msg)

    head = DatasetHeadTool().execute(dataset_id=dataset_id, n=2)
    assert "a" in head
    assert "b" in head
    assert "hello" in head
    assert "world" in head


def test_filter_and_describe(tmp_path) -> None:
    configure_allowed_paths([str(tmp_path)])

    csv_path = tmp_path / "numbers.csv"
    csv_path.write_text("x\n1\n2\n3\n4\n", encoding="utf-8")

    msg = LoadDatasetTool().execute(path=str(csv_path), format="csv")
    dataset_id = _extract_dataset_id(msg)

    filtered_msg = DatasetFilterTool().execute(
        dataset_id=dataset_id,
        conditions=[{"column": "x", "op": ">", "value": 2}],
    )
    filtered_id = _extract_dataset_id(filtered_msg)

    summary = DatasetDescribeTool().execute(dataset_id=filtered_id, columns=["x"])
    assert "mean" in summary
    assert "4" in summary or "3" in summary


def test_export_dataset_csv(tmp_path) -> None:
    configure_allowed_paths([str(tmp_path)])

    csv_path = tmp_path / "data.csv"
    csv_path.write_text("a,b\n1,hello\n", encoding="utf-8")

    msg = LoadDatasetTool().execute(path=str(csv_path), format="csv")
    dataset_id = _extract_dataset_id(msg)

    out_path = tmp_path / "out.csv"
    result = ExportDatasetTool().execute(dataset_id=dataset_id, path=str(out_path), format="csv", overwrite=False)
    assert "Exported" in result
    assert out_path.exists()
    assert out_path.read_text(encoding="utf-8").startswith("a,b")


def test_xlsx_support_optional(tmp_path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    configure_allowed_paths([str(tmp_path)])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["a", "b"])
    ws.append([1, "hello"])
    xlsx_path = tmp_path / "data.xlsx"
    wb.save(xlsx_path)
    wb.close()

    msg = LoadDatasetTool().execute(path=str(xlsx_path), format="xlsx", sheet_name="Sheet1")
    dataset_id = _extract_dataset_id(msg)

    out_path = tmp_path / "out.xlsx"
    result = ExportDatasetTool().execute(dataset_id=dataset_id, path=str(out_path), format="xlsx", overwrite=False)
    assert "Exported" in result
    assert out_path.exists()


def test_plot_saving_optional(tmp_path) -> None:
    pytest.importorskip("matplotlib")
    configure_allowed_paths([str(tmp_path)])

    csv_path = tmp_path / "numbers.csv"
    csv_path.write_text("x\n1\n2\n3\n4\n", encoding="utf-8")

    msg = LoadDatasetTool().execute(path=str(csv_path), format="csv")
    dataset_id = _extract_dataset_id(msg)

    out_path = tmp_path / "hist.png"
    result = SaveHistogramPlotTool().execute(dataset_id=dataset_id, column="x", path=str(out_path))
    assert "Saved histogram plot" in result
    assert out_path.exists()

