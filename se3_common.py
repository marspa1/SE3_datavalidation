"""
se3_common.py — gemensamma hjälpfunktioner för SE3-data.

Används av både 01_ingest_USBdata.ipynb (inläsning och aggregering) och
02_analysis.ipynb (analys) så att inläsning och justeringar är identiska
i båda stegen.
"""

import json
import os
import re

import numpy as np
import pandas as pd

# Kolumner med ljudnivådata i SE3-filerna
data_columns = ['LAF', 'LAeq1s', 'LAS', 'LCpeak']

# Filnamnsmönster: SE3-<id>-DD-MM-YYYY.csv
_filename_re = re.compile(r'SE3-[^-]+-(\d{2})-(\d{2})-(\d{4})\.csv')

# Aktiv kalibreringshistorik (sätts med set_calibration)
cal_history = []
cal_times = np.empty(0)
cal_vals = np.empty(0)


def set_calibration(history):
    """Aktivera kalibreringshistoriken: [(datum, konstant i dB), ...].

    Konstanten ändras linjärt mellan angivna datum. Före första datumet
    gäller det första värdet, efter sista datumet det sista värdet.
    """
    global cal_history, cal_times, cal_vals
    if not history:
        raise ValueError("cal_history får inte vara tom")
    cal_history = [(pd.Timestamp(date), float(value)) for date, value in history]
    dates = [date for date, _ in cal_history]
    if any(later <= earlier for earlier, later in zip(dates, dates[1:])):
        raise ValueError("Kalibreringsdatumen måste vara stigande och unika")
    cal_times = np.array([date.timestamp() for date in dates])
    cal_vals = np.array([value for _, value in cal_history])


def cal_for(index):
    """Linjärt interpolerad kalibreringskonstant för varje tidpunkt."""
    t_ns = index.astype('datetime64[ns]').asi8
    return np.interp(t_ns / 1e9, cal_times, cal_vals)


def save_calibration(outpath, dst_shifts=()):
    """Spara kalibrering och sommartidsjusteringar som JSON i outpath."""
    payload = {
        'cal_history': [[date.isoformat(), value]
                        for date, value in cal_history],
        'dst_shifts': [[pd.Timestamp(ts).isoformat(), hours]
                       for ts, hours in dst_shifts],
    }
    with open(os.path.join(outpath, 'calibration.json'), 'w') as f:
        json.dump(payload, f, indent=2)


def load_calibration(path):
    """Läs kalibrering och sommartidsjusteringar från steg 1.

    Aktiverar kalibreringshistoriken och returnerar sommartidsjusteringarna
    som [(tidpunkt, shift i timmar), ...].
    """
    with open(path) as f:
        payload = json.load(f)
    set_calibration(payload['cal_history'])
    return [(pd.Timestamp(ts), hours)
            for ts, hours in payload.get('dst_shifts', [])]


def file_date(fname):
    """Datumet ur filnamnet SE3-<id>-DD-MM-YYYY.csv, eller None."""
    match = _filename_re.search(fname)
    if not match:
        return None
    day, month, year = match.groups()
    return pd.Timestamp(f'{year}-{month}-{day}')


def find_files(datapath, startdate=None, enddate=None):
    """Sorterad lista med SE3-CSV-filer i datapath inom datumintervallet."""
    filelist = []
    for fname in os.listdir(datapath):
        fdate = file_date(fname)
        if fdate is None:
            continue
        if startdate is not None and fdate.date() < startdate:
            continue
        if enddate is not None and fdate.date() > enddate:
            continue
        filelist.append(fname)
    filelist.sort()
    return filelist


def read_day(datapath, fname):
    """Läs en dags datafil, returnera DataFrame med datetime-index."""
    df = pd.read_csv(
        os.path.join(datapath, fname),
        sep=';',
        dtype={'Ms': str, 'Time': str, 'Date': str},
    )
    df['DateTime'] = pd.to_datetime(
        df['Date'] + ' ' + df['Time'] + '.' + df['Ms'].str.zfill(3).str[1:],
        format='%d-%m-%Y %H:%M:%S.%f'
    )
    df.drop(columns=['Date', 'Time', 'Ms'], inplace=True)
    df.set_index('DateTime', inplace=True)
    return df[data_columns]


def adjust_day(df, free_field_comp=0, dst_shifts=()):
    """Kalibrerings- och frifältskorrigering samt sommartidsjustering."""
    df = df.copy()
    cal = pd.Series(cal_for(df.index), index=df.index)
    df[data_columns] = df[data_columns].add(cal, axis=0)
    df[data_columns] -= free_field_comp
    for ts, hours in dst_shifts:
        df.update(df.loc[df.index >= pd.Timestamp(ts)].shift(hours, freq='h'))
    return df
