"""El repositorio es público: no debe exponer datos del cargo, enlaces institucionales ni canales retirados.

Contacto del autor: GitHub, portafolio, LinkedIn y correo personal (Gmail).
"""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
THIS_FILE = Path(__file__).resolve()

FORBIDDEN = [
    ("correo institucional", re.compile(r"@cendoj", re.I)),
    ("correo retirado", re.compile(r"@hotmail\.", re.I)),
    ("redes retiradas", re.compile(r"instagram\.com/daniel_arbe99|(x|twitter)\.com/hammerdev99|youtube\.com/@daainti", re.I)),
    ("blog pendiente de revisión", re.compile(r"blog\.sprintjudicial\.com", re.I)),
    ("SharePoint institucional", re.compile(r"sharepoint\.com", re.I)),
    ("municipio o dependencia del cargo", re.compile(r"\bbello\b|Centro de Servicios Judiciales", re.I)),
    ("adopción sin fuente", re.compile(r"retroalimentación en la implementación", re.I)),
]

BINARY_SUFFIXES = {".png", ".ico", ".webp", ".jpg", ".jpeg", ".gif", ".pdf", ".docx", ".xlsx", ".zip"}


def tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    return [name for name in out.decode("utf-8").split("\0") if name]


def tracked_text(name):
    path = ROOT / name
    if path.resolve() == THIS_FILE or path.suffix.lower() in BINARY_SUFFIXES or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


@pytest.mark.parametrize("label,pattern", FORBIDDEN, ids=[label for label, _ in FORBIDDEN])
def test_tracked_files_do_not_expose(label, pattern):
    hits = []
    for name in tracked_files():
        for number, line in enumerate(tracked_text(name).splitlines(), 1):
            if pattern.search(line):
                hits.append(f"{name}:{number}")
    assert not hits, f"{label}: {hits[:10]}"
