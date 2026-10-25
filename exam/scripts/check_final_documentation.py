# Generated with an AI assistant
"""Compare script ASTs and final CSV hashes without executing project code."""
import ast
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'reports' / 'final_documentation_before.json'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def snapshot():
    scripts = {}
    for path in sorted((ROOT / 'scripts').rglob('*.py')):
        text = path.read_text()
        scripts[str(path.relative_to(ROOT))] = {
            'ast_sha256': sha(ast.dump(ast.parse(text, type_comments=True), include_attributes=False).encode()),
            'source_sha256': sha(path.read_bytes()),
            'ai_header_present': text.splitlines()[0] == '# Generated with an AI assistant'}
    csvs = {name: sha((ROOT / name).read_bytes()) for name in
            ['submission_frequency_bonus3.csv', 'submission_ppr.csv', 'submission_frequency_bonus6.csv']}
    return {'scripts': scripts, 'final_csv_sha256': csvs,
            'prediction_checks_sha256': sha((ROOT / 'reports' / 'final_prediction_checks.json').read_bytes())}


if __name__ == '__main__':
    current = snapshot()
    if sys.argv[1] == 'before':
        BASELINE.write_text(json.dumps(current, indent=2)+'\n')
        print(f"Recorded {len(current['scripts'])} script ASTs and three final CSV hashes.")
    elif sys.argv[1] == 'after':
        before = json.loads(BASELINE.read_text())
        assert before['scripts'].keys() == current['scripts'].keys()
        for name, info in current['scripts'].items():
            assert before['scripts'][name]['ast_sha256'] == info['ast_sha256'], name
            assert info['ai_header_present'], name
        assert before['final_csv_sha256'] == current['final_csv_sha256']
        assert before['prediction_checks_sha256'] == current['prediction_checks_sha256']
        official = json.loads((ROOT / 'reports' / 'final_prediction_checks.json').read_text())
        assert all(official['files'][name]['sha256'] == value for name, value in current['final_csv_sha256'].items())
        report = {'status': 'passed', 'scripts_checked': len(current['scripts']),
            'all_ast_unchanged': True, 'all_ai_headers_present': True,
            'final_csv_files_unchanged': True, 'original_prediction_checks_unchanged': True,
            'scripts': {name: {'ast_before_sha256': before['scripts'][name]['ast_sha256'],
                             'ast_after_sha256': info['ast_sha256'],
                             'source_before_sha256': before['scripts'][name]['source_sha256'],
                             'source_after_sha256': info['source_sha256']} for name, info in current['scripts'].items()},
            'final_csv_sha256': current['final_csv_sha256'],
            'method': 'ast.parse(type_comments=True), ast.dump(include_attributes=False); no project code executed.'}
        (ROOT / 'reports' / 'final_documentation_checks.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f"PASS: {len(current['scripts'])} unchanged ASTs; all AI headers present; three CSV hashes and prediction-check manifest unchanged.")
    else:
        raise ValueError('Use before or after.')
