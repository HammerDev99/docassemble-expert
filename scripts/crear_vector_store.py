#!/usr/bin/env python3
"""
Crea o actualiza el vector store de DocAssemble Expert en OpenAI a partir de la carpeta ``knowledge/``.

Es el reemplazo de la base de conocimiento (File Search) que tenía el antiguo Assistant.

Uso:
    python3 scripts/crear_vector_store.py --dry-run                   # solo lista los archivos
    python3 scripts/crear_vector_store.py                             # crea un vector store nuevo
    python3 scripts/crear_vector_store.py --vector-store-id vs_xxx    # agrega archivos a uno existente
    python3 scripts/crear_vector_store.py --vector-store-id vs_xxx --sincronizar   # sube solo lo nuevo o modificado
    python3 scripts/crear_vector_store.py --vector-store-id vs_xxx --sincronizar --podar   # y borra paquetes que ya no existen
    python3 scripts/crear_vector_store.py --knowledge-dir otra/carpeta

Requiere OPENAI_API_KEY en el entorno o en .streamlit/secrets.toml.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_DIR = ROOT / "knowledge"
DEFAULT_NAME = "DocAssemble Expert - Base de conocimiento"
SUPPORTED_SUFFIXES = {".pdf", ".md", ".txt", ".docx", ".pptx", ".html", ".json", ".csv"}
EXCLUDED_NAMES = {"README.md"}
# Solo los archivos que genera scripts/cosechar_suffolk.py se pueden podar; los manuales subidos a mano nunca.
PRUNABLE_PATTERN = re.compile(r"^docassemble-.+\.md$")
MAX_PRUNE_RATIO = 0.10


def read_api_key() -> str | None:
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    secrets_file = ROOT / ".streamlit" / "secrets.toml"
    if secrets_file.is_file():
        match = re.search(r'^\s*OPENAI_API_KEY\s*=\s*"([^"]+)"', secrets_file.read_text(encoding="utf-8"), re.M)
        if match:
            return match.group(1)
    return None


def collect_files(knowledge_dir: Path) -> list[Path]:
    files = []
    for path in sorted(knowledge_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES and path.name not in EXCLUDED_NAMES:
            files.append(path)
    return files


def plan_sync(local: list[Path], remote: dict[str, tuple[str, int]]) -> tuple[list[Path], list[str], int]:
    """Compara archivos locales con los del vector store (nombre -> (file_id, bytes)).

    Devuelve (archivos a subir, ids remotos a reemplazar, cantidad sin cambios). Un archivo con el mismo nombre
    y el mismo tamaño se considera sin cambios.
    """
    to_upload: list[Path] = []
    to_replace: list[str] = []
    unchanged = 0
    for path in local:
        match = remote.get(path.name)
        if match and match[1] == path.stat().st_size:
            unchanged += 1
            continue
        if match:
            to_replace.append(match[0])
        to_upload.append(path)
    return to_upload, to_replace, unchanged


def plan_prune(local: list[Path], remote: dict[str, tuple[str, int]]) -> list[tuple[str, str]]:
    """Archivos del corpus cosechado que siguen en el vector store pero ya no existen localmente: (nombre, file_id)."""
    local_names = {path.name for path in local}
    return sorted((name, file_id) for name, (file_id, _) in remote.items()
                  if PRUNABLE_PATTERN.match(name) and name not in local_names)


def remote_files(client, vector_store_id: str) -> dict[str, tuple[str, int]]:
    """Archivos del vector store por nombre, con su id y tamaño."""
    in_store = {f.id for f in client.vector_stores.files.list(vector_store_id=vector_store_id, limit=100)}
    found: dict[str, tuple[str, int]] = {}
    for f in client.files.list(purpose="assistants", limit=10000):
        if f.id in in_store:
            found[f.filename] = (f.id, f.bytes)
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--knowledge-dir", type=Path, default=DEFAULT_KNOWLEDGE_DIR)
    parser.add_argument("--vector-store-id", help="ID (vs_...) de un vector store existente al que agregar archivos")
    parser.add_argument("--name", default=DEFAULT_NAME, help="Nombre del vector store nuevo")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar los archivos, sin llamar a OpenAI")
    parser.add_argument("--sincronizar", action="store_true",
                        help="Con --vector-store-id: subir solo archivos nuevos o modificados y reemplazar los modificados")
    parser.add_argument("--podar", action="store_true",
                        help="Con --sincronizar: borrar del vector store los paquetes cosechados que ya no existen localmente")
    parser.add_argument("--forzar-poda", action="store_true",
                        help=f"Permitir podar más del {int(MAX_PRUNE_RATIO * 100)} %% del corpus en una sola ejecución")
    args = parser.parse_args(argv)

    knowledge_dir: Path = args.knowledge_dir
    if not knowledge_dir.is_dir():
        print(f"No existe la carpeta {knowledge_dir}", file=sys.stderr)
        return 1

    files = collect_files(knowledge_dir)
    if not files:
        print(f"No hay archivos admitidos en {knowledge_dir} ({', '.join(sorted(SUPPORTED_SUFFIXES))})", file=sys.stderr)
        return 1

    if args.sincronizar and not args.vector_store_id:
        print("--sincronizar requiere --vector-store-id.", file=sys.stderr)
        return 1

    if not args.sincronizar:
        print(f"Archivos a indexar ({len(files)}):")
        for path in files:
            print(f"  - {path.relative_to(ROOT) if ROOT in path.parents else path}  ({path.stat().st_size // 1024} KB)")

    if args.dry_run and not args.sincronizar:
        print("\n--dry-run: no se llamó a OpenAI.")
        return 0

    api_key = read_api_key()
    if not api_key:
        print("Falta OPENAI_API_KEY (entorno o .streamlit/secrets.toml).", file=sys.stderr)
        return 1

    from openai import OpenAI  # import tardío para que --dry-run funcione sin el SDK

    client = OpenAI(api_key=api_key)

    if args.vector_store_id:
        vector_store = client.vector_stores.retrieve(args.vector_store_id)
        print(f"\nUsando vector store existente: {vector_store.id} ({vector_store.name})")
        if args.sincronizar:
            remote = remote_files(client, vector_store.id)
            to_prune = plan_prune(files, remote) if args.podar else []
            corpus_size = sum(1 for name in remote if PRUNABLE_PATTERN.match(name)) or 1
            if len(to_prune) / corpus_size > MAX_PRUNE_RATIO and not args.forzar_poda:
                print(f"Se podarían {len(to_prune)} de {corpus_size} paquetes; parece una cosecha incompleta. "
                      "Revise la cosecha o use --forzar-poda.", file=sys.stderr)
                return 3
            for name, _ in to_prune:
                print(f"  podar: {name}")
            files, to_replace, unchanged = plan_sync(files, remote)
            print(f"Sin cambios: {unchanged}. Nuevos: {len(files) - len(to_replace)}. Modificados: {len(to_replace)}. "
                  f"A podar: {len(to_prune)}.")
            for path in files:
                print(f"  - {path.relative_to(ROOT) if ROOT in path.parents else path}")
            if args.dry_run:
                print("\n--dry-run: no se modificó el vector store.")
                return 0
            for file_id in to_replace + [file_id for _, file_id in to_prune]:
                client.vector_stores.files.delete(file_id=file_id, vector_store_id=vector_store.id)
                client.files.delete(file_id)
            if not files:
                print("Nada que subir.")
                return 0
    else:
        vector_store = client.vector_stores.create(name=args.name)
        print(f"\nVector store creado: {vector_store.id} ({vector_store.name})")

    handles = [path.open("rb") for path in files]
    try:
        batch = client.vector_stores.file_batches.upload_and_poll(
            vector_store_id=vector_store.id, files=handles
        )
    finally:
        for handle in handles:
            handle.close()

    counts = batch.file_counts
    print(f"Estado del lote: {batch.status} (completados={counts.completed}, fallidos={counts.failed}, total={counts.total})")
    if counts.failed:
        print("Algunos archivos fallaron. Revise el detalle en el panel de OpenAI (Storage > Vector stores).", file=sys.stderr)

    print("\nAgregue esta línea a .streamlit/secrets.toml o a los secrets de Streamlit Cloud:")
    print(f'VECTOR_STORE_ID = "{vector_store.id}"')
    return 0 if not counts.failed else 2


if __name__ == "__main__":
    sys.exit(main())
