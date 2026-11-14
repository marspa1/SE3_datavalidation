"""
convert_to_parquet.py — konvertera SE3-CSV-filer till Parquet.

Kör:
    python convert_to_parquet.py <datapath> [--startdate ÅÅÅÅ-MM-DD] [--enddate ÅÅÅÅ-MM-DD]

Skapar en zstd-komprimerad Parquet-fil vid sidan om varje CSV-fil
(~5 gånger mindre, ~30 gånger snabbare att läsa). Original-CSV-filerna
ändras inte — de är mätoriginalen; Parquet-filerna är en arbetskopia som
läses automatiskt i stället för CSV:erna av `read_day`.
"""

import argparse
import datetime
import os

import se3_common as se3


def main():
    parser = argparse.ArgumentParser(
        description='Konvertera SE3-CSV-filer till Parquet (zstd).')
    parser.add_argument('datapath', help='katalog med SE3-CSV-filer')
    parser.add_argument('--startdate', default=None,
                        help='konvertera bara filer från och med detta datum')
    parser.add_argument('--enddate', default=None,
                        help='konvertera bara filer fram till detta datum')
    args = parser.parse_args()

    start = (datetime.datetime.strptime(args.startdate, '%Y-%m-%d').date()
             if args.startdate else None)
    end = (datetime.datetime.strptime(args.enddate, '%Y-%m-%d').date()
           if args.enddate else None)

    csv_files = [f for f in se3.find_files(args.datapath, start, end)
                 if f.endswith('.csv')]
    if not csv_files:
        print('Inga CSV-filer att konvertera.')
        return

    csv_total = pq_total = 0.0
    for i, fname in enumerate(csv_files, 1):
        pq_path = se3.convert_day(args.datapath, fname)
        csv_mb = os.path.getsize(os.path.join(args.datapath, fname)) / 1e6
        pq_mb = os.path.getsize(pq_path) / 1e6
        csv_total += csv_mb
        pq_total += pq_mb
        print(f'[{i}/{len(csv_files)}] {fname}: {csv_mb:.1f} MB -> {pq_mb:.1f} MB')

    print(f'Klar: {len(csv_files)} filer, '
          f'{csv_total:.0f} MB -> {pq_total:.0f} MB '
          f'({csv_total / pq_total:.1f}x mindre)')


if __name__ == '__main__':
    main()
