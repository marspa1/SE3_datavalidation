# SE3_datavalidation

Handle sound data from SE3 measurements.

## Workflow

1. `01_ingest_USBdata.ipynb` — reads the SE3-CSV files **one day at a time**
   (low memory usage, ~50 MB per day regardless of measurement period) and
   computes:
   - hourly statistics: sample count and sum/max of 10^(LAF/10), the basis
     for exact LAeq/LAFmax values in the analysis step
   - peaks: noisy passages detected with `find_peaks` on LAF
   - envelope: min/mean/max per 10 min for overview plots
   Results are saved as Parquet files.
2. `02_analysis.ipynb` — reads the Parquet aggregates and does all analysis,
   plotting and CSV export. Full-resolution data for a limited interval is
   loaded on demand from the daily files.

The sampling rate is **8 Hz** (125 ms). Data files are per day and named
`SE3-<id>-DD-MM-YYYY.csv`.

Shared helpers for file handling, parsing and calibration live in
`se3_common.py` and are used by both notebooks.

## Calibration

The calibration constant is entered as a history table, `cal_history` in
`01_ingest_USBdata.ipynb`: one `(date, level in dB)` entry per field
calibration. The constant changes **linearly between the entered dates**
(first value before the first date, last value after the last date), which
matches the typically fast drift from one level to another over days or
weeks. The table is applied per sample at ingestion and passed to the
analysis notebook via `calibration.json` in the aggregate folder, so both
steps always use identical corrections. Update the table at each field
calibration and rerun notebook 01.

## Requirements

Python with pandas, numpy, scipy, matplotlib, pyarrow and Jupyter, e.g.:

```
pip install pandas numpy scipy matplotlib pyarrow jupyterlab
```

## Data

Real measurement data stays outside the repository (see `.gitignore`).
Place the daily CSV files in a local data directory and set `datapath`,
`outpath` and `exppath` in the notebooks accordingly.

### Sample data

`data/sample/` contains (truncated) SE3-CSV files in the same format and
with the same naming convention as the real measurement files. They are
intended for testing the ingestion pipeline without access to the full
data set. Rerun `01_ingest_USBdata.ipynb` on a sample directory to verify
parsing, the 8 Hz sampling rate and the aggregation logic.
