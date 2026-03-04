from __future__ import annotations

import pandas as pd

from src.qa import generate_profile_markdown, run_qa


def test_qa_reports_are_generated(tmp_path):
    df = pd.DataFrame(
        {
            "date_cmd": [pd.to_datetime("2025-01-01").date(), pd.to_datetime("2025-01-02").date()],
            "amount_ht": [100.0, 200.0],
            "tax_amount": [19.0, 38.0],
            "amount_ttc": [119.0, 238.0],
            "qty": [1, 2],
            "category": ["Laptop", "Unknown"],
        }
    )

    report = run_qa(df, missing_prefixes=["UNK"], output_dir=tmp_path, tolerance=0.01)
    assert (tmp_path / "qa_report.csv").exists()
    assert not report.empty

    profile_path = generate_profile_markdown(df, output_dir=tmp_path)
    assert profile_path.exists()

