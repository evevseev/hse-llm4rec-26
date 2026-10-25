# Generated with an AI assistant
"""Optional local OpenMP runtime for XGBoost on Apple Silicon macOS.

No system installation is changed. The conda-forge package and its license are
extracted under the ignored .venv directory, and provenance is recorded there.
"""
import hashlib
import json
import platform
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
URL = 'https://api.anaconda.org/download/conda-forge/llvm-openmp/15.0.5/osx-arm64/llvm-openmp-15.0.5-h7cfbb63_0.tar.bz2'


if __name__ == '__main__':
    if platform.system() != 'Darwin' or platform.machine() != 'arm64':
        print('This optional local package is for Apple Silicon macOS only; use the platform OpenMP runtime elsewhere.')
    else:
        archive = ROOT / '.venv' / 'libomp.tar.bz2'
        target = ROOT / '.venv' / 'libomp'
        if not (target / 'lib' / 'libomp.dylib').exists():
            urllib.request.urlretrieve(URL, archive)
            target.mkdir(exist_ok=True)
            with tarfile.open(archive) as package:
                package.extractall(target, filter='data')
        record = {'source_url': URL, 'package': 'conda-forge llvm-openmp 15.0.5 osx-arm64',
                  'archive_sha256': hashlib.sha256(archive.read_bytes()).hexdigest() if archive.exists() else None}
        (ROOT / '.venv' / 'libomp_source.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps(record, indent=2))
