#!/usr/bin/env bash
# Baut InputForge unter Linux als portablen Ordner + tar.gz.
#
#   bash packaging/build.sh [--skip-tests]
set -euo pipefail
cd "$(dirname "$0")/.."

PY=${PYTHON:-python3}
# uv-venvs enthalten kein pip → uv verwenden, wenn vorhanden, sonst pip.
if command -v uv >/dev/null; then
    [[ -d .venv ]] || uv venv .venv
    uv pip install --python .venv/bin/python -e ".[dev]"
else
    [[ -d .venv ]] || "$PY" -m venv .venv
    .venv/bin/python -m pip install --upgrade pip >/dev/null
    .venv/bin/python -m pip install -e ".[dev]"
fi

if [[ "${1:-}" != "--skip-tests" ]]; then
    QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q
fi

.venv/bin/pyinstaller packaging/inputforge.spec --noconfirm --clean

VERSION=$(.venv/bin/python -c "import inputforge; print(inputforge.__version__)")
NAME="InputForge-${VERSION}"
tar -C dist -czf "dist/${NAME}-linux-x86_64.tar.gz" "${NAME}"
echo "Fertig: dist/${NAME}-linux-x86_64.tar.gz  (starten: ${NAME}/InputForge)"
