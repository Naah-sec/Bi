# Windows Installation and Run Guide

## 1) Install Python

1. Download Python 3.11 from `https://www.python.org/downloads/windows/`.
2. During install, check **Add python.exe to PATH**.

## 2) Open project in VSCode

1. Open VSCode.
2. Open this project folder.

## 3) Create and activate virtual environment

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\activate
```

## 4) Upgrade pip and install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## 5) Put your Excel file in data folder

Place your file at:

```text
.\data\Sales_TD.xlsx
```

## 6) Build / refresh DuckDB warehouse

```powershell
python -m src.warehouse --build
```

This creates:
- `.\data\warehouse.duckdb`
- `.\reports\qa_report.csv`
- `.\reports\profile.md`

## 7) Run Streamlit dashboard

```powershell
streamlit run app/streamlit_app.py
```

## Troubleshooting

1. If `streamlit` is not found:
   - Ensure `.venv` is activated.
   - Re-run `pip install -r requirements.txt`.

2. If Excel parsing fails:
   - Check required columns in `SalesRaw`.
   - Ensure French numeric formats follow expected parsing (`500 000,00` supported).

3. If default port is blocked:
```powershell
streamlit run app/streamlit_app.py --server.port 8502
```

