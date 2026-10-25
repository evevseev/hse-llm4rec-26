# Generated with an AI assistant. Independent standard-library CSV verification.
import csv
import hashlib
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'data'
with (data / 'submission.csv').open(newline='') as stream:
    users = [row['user_id'] for row in csv.DictReader(stream)]
with (data / 'export_arh_31-42-final.csv').open(newline='', encoding='utf-8-sig') as stream:
    allowed = {int(row['tv_show_id']) for row in csv.DictReader(stream)
               if int(row['tv_show_id']) and int(row['duration']) > 0}
checks = []
for name in ['submission_frequency_bonus3.csv', 'submission_ppr.csv', 'submission_frequency_bonus6.csv']:
    path = root / name
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ['user_id', 'tv_show_id']
        rows = list(reader)
    assert len(rows) == 1260 and [row['user_id'] for row in rows] == users
    for row in rows:
        ids = list(map(int, row['tv_show_id'].split()))
        assert len(ids) == len(set(ids)) == 5 and set(ids) <= allowed
    checks.append({'file': name, 'rows': len(rows), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
print(json.dumps(checks, indent=2))
