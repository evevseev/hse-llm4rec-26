# Generated with an AI assistant
"""Prepare the earlier robustness fold without touching original inputs/artifacts."""
from pathlib import Path

from prepare_validation import prepare_fold, timestamp

ROOT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    prepare_fold(output_dir=ROOT / 'data' / 'processed' / 'search_secondary',
                 report_path=ROOT / 'reports' / 'search_secondary_preparation.json',
                 begin=timestamp('2020-03-09 00:00:00'), cutoff=timestamp('2020-04-20 00:00:00'),
                 finish=timestamp('2020-05-18 00:00:00'), sources=('export_arh_11-20-final.csv',))
