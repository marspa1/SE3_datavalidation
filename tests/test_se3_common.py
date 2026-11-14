import datetime
import os

import numpy as np
import pandas as pd
import pytest

import se3_common as se3

SAMPLE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'sample')


@pytest.fixture(scope='module')
def sample_files():
    files = se3.find_files(SAMPLE_DIR)
    if not files:
        pytest.skip('no sample data in data/sample/')
    return files


def test_set_calibration_interpolates_linearly():
    se3.set_calibration([
        ('2026-01-01', 0.0),
        ('2026-06-02 18:00', 0.5),
        ('2026-11-01', 1.0),
    ])
    t1 = pd.Timestamp('2026-06-02 18:00')
    t2 = pd.Timestamp('2026-11-01')
    mid = t1 + (t2 - t1) / 2
    idx = pd.DatetimeIndex([
        pd.Timestamp('2025-12-01'),
        t1,
        mid,
        t2,
        pd.Timestamp('2026-12-01'),
    ])
    assert np.allclose(se3.cal_for(idx), [0.0, 0.5, 0.75, 1.0, 1.0])


@pytest.mark.parametrize('history', [
    [],
    [('2026-01-01', 0.0), ('2026-01-01', 1.0)],
    [('2026-06-01', 0.0), ('2026-01-01', 1.0)],
])
def test_set_calibration_rejects_invalid_history(history):
    with pytest.raises(ValueError):
        se3.set_calibration(history)


def test_cal_for_works_across_index_resolutions():
    se3.set_calibration([('2026-06-02 18:00', 0.5)])
    for unit in ['ns', 'us', 'ms', 's']:
        idx = pd.DatetimeIndex([pd.Timestamp('2026-06-02 18:00')]).as_unit(unit)
        assert se3.cal_for(idx)[0] == 0.5


def test_file_date():
    assert se3.file_date('SE3-2009372275-02-06-2026.csv') == pd.Timestamp('2026-06-02')
    assert se3.file_date('readme.txt') is None


def test_find_files_sorted_and_filtered(sample_files):
    files = se3.find_files(
        SAMPLE_DIR, datetime.date(2026, 6, 3), datetime.date(2026, 12, 31))
    assert files == ['SE3-2009372275-03-06-2026.csv']
    assert se3.find_files(SAMPLE_DIR) == sorted(sample_files)


def test_read_day_parses_sample_file(sample_files):
    df = se3.read_day(SAMPLE_DIR, sample_files[0])
    assert list(df.columns) == se3.data_columns
    assert df.index.is_monotonic_increasing
    assert df.index[0] == pd.Timestamp('2026-06-02 13:45:34.123')


def test_sample_data_is_8hz(sample_files):
    df = se3.read_day(SAMPLE_DIR, sample_files[0])
    dt_ms = df.index.to_series().diff().dt.total_seconds().dropna() * 1000
    assert abs(dt_ms.median() - 125.0) < 1.0


def test_adjust_day_applies_calibration_and_free_field():
    se3.set_calibration([('2026-01-01', 0.0), ('2026-06-02 18:00', 0.5)])
    idx = pd.date_range('2026-06-02 17:00', periods=8, freq='125ms')
    df = pd.DataFrame(
        {'LAF': 50.0, 'LAeq1s': 50.0, 'LAS': 50.0, 'LCpeak': 60.0}, index=idx)
    adjusted = se3.adjust_day(df, free_field_comp=6)
    assert np.allclose(adjusted['LAF'] - df['LAF'], se3.cal_for(idx) - 6)
    assert np.allclose(adjusted['LCpeak'] - df['LCpeak'], se3.cal_for(idx) - 6)


def test_save_and_load_calibration_roundtrip(tmp_path):
    se3.set_calibration([('2026-01-01', 0.0), ('2026-06-02 18:00', 0.5)])
    se3.save_calibration(tmp_path, [('2026-03-29 03:00:00', 1)])
    dst = se3.load_calibration(os.path.join(tmp_path, 'calibration.json'))
    assert dst == [(pd.Timestamp('2026-03-29 03:00:00'), 1)]
    assert se3.cal_for(pd.DatetimeIndex([pd.Timestamp('2026-06-02 20:00')]))[0] == 0.5


def test_hourly_aggregation_and_parquet_roundtrip(tmp_path, sample_files):
    se3.set_calibration([('2026-01-01', 0.0)])
    frames = []
    for fname in sample_files:
        d = se3.adjust_day(se3.read_day(SAMPLE_DIR, fname), 6)
        log_lin = 10 ** (d['LAF'] / 10)
        frames.append(pd.DataFrame({
            'count':   log_lin.resample('1h', label='left').count(),
            'sum_log': log_lin.resample('1h', label='left').sum(),
        }))
    hourly = pd.concat(frames)
    hourly['LAeq'] = 10 * np.log10(hourly['sum_log'] / hourly['count'])
    assert hourly['LAeq'].between(0, 120).all()

    hourly.to_parquet(os.path.join(tmp_path, 'hourly_stats.parquet'))
    reloaded = pd.read_parquet(os.path.join(tmp_path, 'hourly_stats.parquet'))
    pd.testing.assert_frame_equal(hourly, reloaded, check_freq=False)
