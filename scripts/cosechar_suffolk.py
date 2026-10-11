#!/usr/bin/env python3
"""
Cosecha las entrevistas de código abierto del Suffolk LIT Lab (Assembly Line) y las convierte en
Markdown para la base de conocimiento de DocAssemble Expert.

Fuente: los repositorios públicos ``docassemble-*`` de GitHub (SuffolkLITLab, mplp, masslegalhelp).
Son los mismos paquetes que se instalan en apps-dev.suffolklitlab.org, pero completos: YAML de las
entrevistas, módulos Python, plantillas DOCX/PDF y README. No se raspa el servidor.

Salida:
    knowledge/suffolk/_catalogo.md            índice por área (familia, vivienda, laboral, penal...)
    knowledge/suffolk/paquetes/<repo>.md      un archivo por paquete, listo para file_search
    .cache/suffolk/catalogo.json              el mismo catálogo en JSON
    .cache/suffolk/repos/<org>/<repo>/        clones superficiales (se reutilizan en cada ejecución)

Uso:
    python3 scripts/cosechar_suffolk.py --solo-listar          # enumera repositorios, sin clonar
    python3 scripts/cosechar_suffolk.py                        # clona/actualiza y genera el Markdown
    python3 scripts/cosechar_suffolk.py --sin-clonar           # regenera el Markdown desde la caché
    python3 scripts/cosechar_suffolk.py --repos docassemble-MA209AProtectiveOrder docassemble-ALRecipes
    python3 scripts/crear_vector_store.py                      # después: indexar en OpenAI

Licencias: solo se incluyen repositorios con licencia declarada (la mayoría MIT). Los que no tienen
licencia se listan en el catálogo pero no se copian, salvo con --incluir-sin-licencia.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ORGS = ["SuffolkLITLab", "mplp", "masslegalhelp"]
DEFAULT_CACHE_DIR = ROOT / ".cache" / "suffolk"
DEFAULT_OUT_DIR = ROOT / "knowledge" / "suffolk"

MAX_TEXT_FILE_BYTES = 300_000
SKIP_DIRS = {".git", ".github", "node_modules", "__pycache__", "build", "dist", "static", "tests"}
SKIP_MD_NAMES = {"changelog.md", "code_of_conduct.md", "contributing.md", "security.md"}

# Repositorios de infraestructura (framework, herramientas, ejemplos) frente a formularios concretos.
FRAMEWORK_PATTERN = re.compile(
    r"^docassemble-(AssemblyLine|AL(Toolbox|Weaver|GeneralFlow|Recipes|Dashboard|Kiln|ThemeTemplate|Massachusetts|Sessions)"
    r"|EFSPIntegration|InterviewStats|MACourts|MassAccess|ALMassachusetts|GithubFeedbackForm|FormFyxer)",
    re.I,
)
# Utilidades sin contenido jurídico (temas, pruebas, linters, índices, apps internas de clínicas).
TOOLING_NAME_PATTERN = re.compile(
    r"theme|(?<!con)test|^ALLinter|branding|index|select|validation|hello|training|timeline|icebreaker|lablibs|reflection"
    r"|signup|reviewscreen|framework|clinicintake|caseopening|povertyscale|anystate",
    re.I,
)

# Prefijos de la taxonomía LIST (Legal Issues Taxonomy) usada en metadata.LIST_topics.
LIST_AREAS = {
    "FA": "familia",
    "HO": "vivienda",
    "MO": "civil-deudas-consumidor",
    "WO": "laboral",
    "CR": "penal",
    "TR": "penal",
    "ES": "sucesiones",
    "CO": "procesal-general",
    "BE": "beneficios-sociales",
    "HE": "salud",
    "IM": "migratorio",
    "ED": "educacion",
    "TO": "responsabilidad-civil",
    "VE": "beneficios-sociales",
}

KEYWORD_AREAS = [
    ("familia", r"divorc|custod|child|parent|marri|209a|258e|guardian|famil|alimony|support|paternity|abuse"
                r"|protective|separation|name.?change|\bppo\b|dv.?hotline|pet.?protection"),
    ("vivienda", r"evict|tenant|landlord|housing|rent|repair|deposit|lease|habitab|summary.?process|sanitary"
                 r"|tenancy|grievance"),
    ("laboral", r"wage|employ|unemploy|worker|job|work.?authori"),
    ("penal", r"criminal|seal|cori|expunge|bail|traffic|probation|record|juvenile|case.?integrity"),
    ("civil-deudas-consumidor", r"debt|small.?claim|consumer|collection|credit|garnish|judgment|financial"),
    ("sucesiones", r"\bwill\b|estate|power.?s?.?of.?attorney|healthcare.?proxy"),
    ("beneficios-sociales", r"snap|food|\bdta\b|benefit|poverty"),
    ("migratorio", r"immigra"),
    ("procesal-general", r"indigen|fee.?waiver|motion|appeal|court|continu|default|filing"),
]

# Equivalencia orientativa con la jurisdicción colombiana (para el catálogo, no es asesoría jurídica).
COLOMBIA_HINTS = {
    "familia": "Familia (Código de Infancia y Adolescencia, Ley 1257/2008, CGP procesos de familia)",
    "vivienda": "Civil (arrendamiento urbano Ley 820/2003, restitución de inmueble arrendado CGP art. 384)",
    "laboral": "Laboral (CST, CPTSS)",
    "penal": "Penal (Ley 906/2004; habeas data penal y antecedentes)",
    "civil-deudas-consumidor": "Civil / consumidor (CGP, Ley 1480/2011, insolvencia de persona natural)",
    "sucesiones": "Civil / familia (sucesiones, CGP y Código Civil)",
    "procesal-general": "Procesal transversal (amparo de pobreza CGP arts. 151-158, memoriales, recursos)",
    "beneficios-sociales": "Administrativo / seguridad social (derechos de petición, tutela)",
    "salud": "Salud (derecho de petición, tutela, Superintendencia de Salud)",
    "migratorio": "Migratorio (Migración Colombia, PPT)",
    "educacion": "Administrativo / educación",
    "responsabilidad-civil": "Civil (responsabilidad civil extracontractual)",
    "framework": "Infraestructura reutilizable (no es un formulario)",
    "sin-clasificar": "Revisar manualmente",
}


@dataclass
class RepoInfo:
    org: str
    name: str
    url: str
    description: str = ""
    license: str = "-"
    archived: bool = False
    pushed_at: str = ""
    default_branch: str = "main"
    size_kb: int = 0


@dataclass
class PackageSummary:
    repo: RepoInfo
    kind: str = "formulario"
    area: str = "sin-clasificar"
    title: str = ""
    short_description: str = ""
    jurisdiction: str = ""
    form_numbers: List[str] = field(default_factory=list)
    list_topics: List[str] = field(default_factory=list)
    languages: List[str] = field(default_factory=list)
    interviews: List[str] = field(default_factory=list)
    templates: List[str] = field(default_factory=list)
    included: bool = True
    exclusion_reason: str = ""
    output_file: str = ""


# --------------------------------------------------------------------------- GitHub


def github_token() -> Optional[str]:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token
    try:
        out = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None


def list_repos(orgs: Iterable[str], token: Optional[str]) -> List[RepoInfo]:
    import requests  # import tardío: las funciones de extracción no lo necesitan

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    repos: List[RepoInfo] = []
    for org in orgs:
        url: Optional[str] = f"https://api.github.com/orgs/{org}/repos?per_page=100&type=public"
        while url:
            resp = requests.get(url, headers=headers, timeout=30)
            if resp.status_code == 404:  # cuenta de usuario, no organización
                url = f"https://api.github.com/users/{org}/repos?per_page=100"
                continue
            resp.raise_for_status()
            for item in resp.json():
                if not item["name"].lower().startswith("docassemble-") or item.get("fork"):
                    continue
                repos.append(
                    RepoInfo(
                        org=org,
                        name=item["name"],
                        url=item["html_url"],
                        description=item.get("description") or "",
                        license=(item.get("license") or {}).get("spdx_id") or "-",
                        archived=bool(item.get("archived")),
                        pushed_at=(item.get("pushed_at") or "")[:10],
                        default_branch=item.get("default_branch") or "main",
                        size_kb=item.get("size") or 0,
                    )
                )
            url = resp.links.get("next", {}).get("url")
    return repos


def sync_repo(repo: RepoInfo, repos_dir: Path) -> Optional[str]:
    """Clona (superficial) o actualiza el repositorio. Devuelve un mensaje de error o None."""
    target = repos_dir / repo.org / repo.name
    try:
        if (target / ".git").is_dir():
            subprocess.run(["git", "-C", str(target), "fetch", "--depth", "1", "-q", "origin", repo.default_branch],
                           check=True, capture_output=True, timeout=300)
            subprocess.run(["git", "-C", str(target), "reset", "-q", "--hard", "FETCH_HEAD"],
                           check=True, capture_output=True, timeout=60)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "clone", "-q", "--depth", "1", "--single-branch", repo.url + ".git", str(target)],
                           check=True, capture_output=True, timeout=600)
    except subprocess.CalledProcessError as exc:
        return (exc.stderr or b"").decode("utf-8", "replace").strip() or str(exc)
    except subprocess.TimeoutExpired:
        return "tiempo de espera agotado"
    return None


# --------------------------------------------------------------------------- Extracción


def docx_text(path: Path) -> str:
    """Texto de una plantilla DOCX conservando las etiquetas Jinja ({{ }}, {% %}), párrafo por párrafo."""
    try:
        with zipfile.ZipFile(path) as zf:
            xml = zf.read("word/document.xml").decode("utf-8", "replace")
    except (zipfile.BadZipFile, KeyError, OSError):
        return ""
    paragraphs = []
    for para in re.findall(r"<w:p[ >].*?</w:p>", xml, flags=re.S):
        runs = re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", para, flags=re.S)
        text = "".join(runs)
        if text.strip():
            paragraphs.append(_unescape_xml(text))
    return "\n".join(paragraphs)


def _unescape_xml(text: str) -> str:
    return (text.replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"')
            .replace("&apos;", "'").replace("&amp;", "&"))


def pdf_field_names(path: Path) -> List[str]:
    try:
        from PyPDF2 import PdfReader

        fields = PdfReader(str(path)).get_fields() or {}
    except Exception:  # PDFs dañados o cifrados: no deben detener la cosecha
        return []
    return sorted(fields)


def load_yaml_documents(text: str) -> List[Dict[str, Any]]:
    """Bloques YAML de una entrevista como diccionarios; ignora los que no se pueden interpretar."""
    try:
        import yaml
    except ImportError:
        return []
    docs = []
    for chunk in re.split(r"^---\s*$", text, flags=re.M):
        if not chunk.strip():
            continue
        try:
            data = yaml.safe_load(chunk)
        except yaml.YAMLError:
            continue
        if isinstance(data, dict):
            docs.append(data)
    return docs


def extract_metadata(yaml_texts: Iterable[str]) -> Dict[str, Any]:
    """Fusiona los bloques ``metadata:`` de todas las entrevistas.

    Manda el archivo con el bloque más completo (normalmente la entrevista principal del paquete);
    los demás solo completan las claves que falten.
    """
    per_file: List[Dict[str, Any]] = []
    for text in yaml_texts:
        meta: Dict[str, Any] = {}
        for doc in load_yaml_documents(text):
            block = doc.get("metadata")
            if isinstance(block, dict):
                for key, value in block.items():
                    if value not in (None, "", []) and key not in meta:
                        meta[key] = value
        if meta:
            per_file.append(meta)
    merged: Dict[str, Any] = {}
    for meta in sorted(per_file, key=len, reverse=True):
        for key, value in meta.items():
            merged.setdefault(key, value)
    return merged


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if v not in (None, "")]
    return [str(value)]


def classify_area(name: str, title: str, list_topics: Iterable[str]) -> str:
    if FRAMEWORK_PATTERN.match(name) or TOOLING_NAME_PATTERN.search(name.removeprefix("docassemble-")):
        return "framework"
    for topic in list_topics:
        area = LIST_AREAS.get(str(topic)[:2].upper())
        if area:
            return area
    haystack = f"{name} {title}".lower()
    for area, pattern in KEYWORD_AREAS:
        if re.search(pattern, haystack):
            return area
    return "sin-clasificar"


def _iter_files(base: Path, suffixes: Iterable[str]) -> List[Path]:
    wanted = {s.lower() for s in suffixes}
    found = []
    for path in sorted(base.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in wanted:
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(base).parts[:-1]):
            continue
        found.append(path)
    return found


def _read_text(path: Path) -> str:
    if path.stat().st_size > MAX_TEXT_FILE_BYTES:
        return f"(archivo omitido: {path.stat().st_size // 1024} KB supera el límite de {MAX_TEXT_FILE_BYTES // 1024} KB)"
    return path.read_text(encoding="utf-8", errors="replace")


def _fence(text: str, lang: str) -> str:
    ticks = "````" if "```" in text else "```"
    return f"{ticks}{lang}\n{text.rstrip()}\n{ticks}"


def build_package(repo: RepoInfo, repo_dir: Path) -> tuple[PackageSummary, str]:
    """Analiza un repositorio clonado y devuelve su resumen y el Markdown para la base de conocimiento."""
    yaml_files = _iter_files(repo_dir, [".yml", ".yaml"])
    yaml_files = [p for p in yaml_files if "docassemble" in p.relative_to(repo_dir).parts[:1]]
    yaml_texts = {p: _read_text(p) for p in yaml_files}
    meta = extract_metadata(yaml_texts.values())

    title = str(meta.get("title") or meta.get("short title") or repo.description or repo.name)
    list_topics = _as_list(meta.get("LIST_topics"))
    summary = PackageSummary(
        repo=repo,
        title=title.strip(),
        short_description=" ".join(str(meta.get("description") or repo.description).split())[:400],
        jurisdiction=str(meta.get("jurisdiction") or ""),
        form_numbers=_as_list(meta.get("form_numbers")),
        list_topics=list_topics,
        languages=_as_list(meta.get("languages")),
        interviews=[str(p.relative_to(repo_dir)) for p in yaml_files if "questions" in p.parts],
    )
    summary.area = classify_area(repo.name, summary.title, list_topics)
    summary.kind = "framework" if summary.area == "framework" else "formulario"
    if summary.kind == "framework":  # su metadata describe una entrevista de ejemplo, no el paquete
        summary.title = f"{repo.name} — {repo.description}" if repo.description else repo.name
        summary.short_description = repo.description

    templates = _iter_files(repo_dir, [".docx", ".pdf"])
    templates = [p for p in templates if "templates" in p.parts]
    summary.templates = [str(p.relative_to(repo_dir)) for p in templates]

    blob_base = f"{repo.url}/blob/{repo.default_branch}"
    lines = [
        f"# {summary.title}",
        "",
        f"- **Paquete:** `{repo.name.replace('docassemble-', 'docassemble.', 1)}`",
        f"- **Repositorio:** {repo.url} (licencia: {repo.license}{', ARCHIVADO' if repo.archived else ''}; último cambio {repo.pushed_at})",
        f"- **Tipo:** {summary.kind}",
        f"- **Área (EE. UU.):** {summary.area} · **Equivalente orientativo en Colombia:** {COLOMBIA_HINTS.get(summary.area, '')}",
    ]
    if summary.jurisdiction:
        lines.append(f"- **Jurisdicción original:** {summary.jurisdiction}")
    if summary.form_numbers:
        lines.append(f"- **Formularios oficiales:** {', '.join(summary.form_numbers)}")
    if list_topics:
        lines.append(f"- **LIST topics:** {', '.join(list_topics)}")
    lines.append("- **Fuente:** Suffolk LIT Lab / Document Assembly Line. Contenido de Massachusetts (EE. UU.); "
                 "adaptar normas, formularios y lenguaje antes de usarlo en Colombia.")
    for key in ("description", "can_I_use_this_form", "before_you_start"):
        if meta.get(key):
            lines += ["", f"## {key}", "", str(meta[key]).strip()]

    readme = next((p for p in (repo_dir / "README.md", repo_dir / "readme.md") if p.is_file()), None)
    if readme:
        lines += ["", "## README", "", _read_text(readme).strip()]

    docs = [p for p in _iter_files(repo_dir, [".md", ".mdx"])
            if p != readme and p.name.lower() not in SKIP_MD_NAMES]
    for path in docs:
        lines += ["", f"## Documentación: {path.relative_to(repo_dir)}", "", _read_text(path).strip()]

    for path, text in yaml_texts.items():
        rel = path.relative_to(repo_dir)
        lines += ["", f"## YAML: {rel}", "", f"Fuente: {blob_base}/{rel}", "", _fence(text, "yaml")]

    py_files = [p for p in _iter_files(repo_dir / "docassemble", [".py"]) if p.name not in {"__init__.py", "setup.py"}] \
        if (repo_dir / "docassemble").is_dir() else []
    for path in py_files:
        rel = path.relative_to(repo_dir)
        lines += ["", f"## Python: {rel}", "", _fence(_read_text(path), "python")]

    for path in templates:
        rel = path.relative_to(repo_dir)
        if path.suffix.lower() == ".docx":
            text = docx_text(path)
            if text:
                lines += ["", f"## Plantilla DOCX: {rel}", "", _fence(text, "jinja")]
        else:
            fields = pdf_field_names(path)
            if fields:
                lines += ["", f"## Plantilla PDF (campos rellenables): {rel}", "",
                          "\n".join(f"- `{name}`" for name in fields)]

    return summary, "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- Catálogo


def render_catalog(summaries: List[PackageSummary]) -> str:
    included = [s for s in summaries if s.included]
    lines = [
        "# Catálogo de entrevistas del Suffolk LIT Lab (Document Assembly Line)",
        "",
        f"Generado el {date.today().isoformat()} con `scripts/cosechar_suffolk.py`. "
        f"{len(included)} paquetes incluidos de {len(summaries)} repositorios encontrados.",
        "",
        "Las entrevistas resuelven necesidades legales de Massachusetts (EE. UU.). Sirven como patrones de "
        "diseño (flujo, preguntas, validaciones, plantillas) para construir entrevistas colombianas; las normas, "
        "formularios y autoridades deben sustituirse por las colombianas.",
    ]
    by_area: Dict[str, List[PackageSummary]] = {}
    for s in included:
        by_area.setdefault(s.area, []).append(s)
    for area in sorted(by_area, key=lambda a: (a in {"framework", "sin-clasificar"}, a)):
        items = sorted(by_area[area], key=lambda s: s.repo.name.lower())
        lines += ["", f"## {area} ({len(items)})", "", f"Equivalente orientativo en Colombia: {COLOMBIA_HINTS.get(area, '')}", ""]
        for s in items:
            flags = " (archivado)" if s.repo.archived else ""
            forms = f" · formularios: {', '.join(s.form_numbers)}" if s.form_numbers else ""
            desc = f" — {s.short_description[:220]}" if s.short_description else ""
            lines.append(f"- **{s.title}**{flags} · `{s.repo.name}` · {s.repo.url}{forms}{desc}")
    excluded = [s for s in summaries if not s.included]
    if excluded:
        lines += ["", "## Repositorios no incluidos", ""]
        lines += [f"- `{s.repo.name}` ({s.repo.url}): {s.exclusion_reason}" for s in excluded]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- CLI


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--orgs", nargs="+", default=DEFAULT_ORGS, help="Organizaciones o usuarios de GitHub")
    parser.add_argument("--repos", nargs="+", help="Procesar solo estos repositorios (nombre exacto)")
    parser.add_argument("--cache-dir", type=Path, default=DEFAULT_CACHE_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--solo-listar", action="store_true", help="Solo enumerar repositorios, sin clonar")
    parser.add_argument("--sin-clonar", action="store_true", help="No clonar ni actualizar; usar la caché")
    parser.add_argument("--sin-archivados", action="store_true", help="Excluir repositorios archivados")
    parser.add_argument("--incluir-sin-licencia", action="store_true",
                        help="Incluir repositorios sin licencia declarada (revise los derechos antes de publicarlos)")
    parser.add_argument("--workers", type=int, default=8, help="Clonaciones en paralelo")
    args = parser.parse_args(argv)

    cache_dir: Path = args.cache_dir
    repos_dir = cache_dir / "repos"
    repos_file = cache_dir / "repos.json"

    if args.sin_clonar and repos_file.is_file():
        repos = [RepoInfo(**r) for r in json.loads(repos_file.read_text(encoding="utf-8"))]
    else:
        print(f"Consultando GitHub: {', '.join(args.orgs)}...")
        repos = list_repos(args.orgs, github_token())
        cache_dir.mkdir(parents=True, exist_ok=True)
        repos_file.write_text(json.dumps([asdict(r) for r in repos], indent=1), encoding="utf-8")
    if args.repos:
        wanted = {r.lower() for r in args.repos}
        repos = [r for r in repos if r.name.lower() in wanted]
    print(f"{len(repos)} repositorios docassemble-* encontrados.")

    summaries: List[PackageSummary] = []
    to_process: List[RepoInfo] = []
    for repo in repos:
        reason = ""
        if args.sin_archivados and repo.archived:
            reason = "archivado"
        elif repo.license == "-" and not args.incluir_sin_licencia:
            reason = "sin licencia declarada"
        if reason:
            summaries.append(PackageSummary(repo=repo, title=repo.name, included=False, exclusion_reason=reason))
        else:
            to_process.append(repo)

    if args.solo_listar:
        for repo in sorted(to_process, key=lambda r: r.name.lower()):
            print(f"  {repo.org}/{repo.name}  [{repo.license}]{' (archivado)' if repo.archived else ''}")
        print(f"\n{len(to_process)} se procesarían; {len(summaries)} quedan excluidos.")
        return 0

    if not args.sin_clonar:
        print(f"Clonando/actualizando {len(to_process)} repositorios en {repos_dir}...")
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
            errors = list(pool.map(lambda r: sync_repo(r, repos_dir), to_process))
        for repo, error in zip(to_process, errors):
            if error:
                print(f"  ! {repo.name}: {error}", file=sys.stderr)

    packages_dir = args.out_dir / "paquetes"
    packages_dir.mkdir(parents=True, exist_ok=True)
    total_bytes = 0
    for repo in to_process:
        repo_dir = repos_dir / repo.org / repo.name
        if not repo_dir.is_dir():
            summaries.append(PackageSummary(repo=repo, title=repo.name, included=False, exclusion_reason="no se pudo clonar"))
            continue
        summary, markdown = build_package(repo, repo_dir)
        if not summary.interviews and summary.kind == "formulario" and not summary.templates:
            summary.included = False
            summary.exclusion_reason = "no contiene entrevistas ni plantillas"
        else:
            out_file = packages_dir / f"{repo.name}.md"
            out_file.write_text(markdown, encoding="utf-8")
            summary.output_file = str(out_file.relative_to(ROOT) if ROOT in out_file.parents else out_file)
            total_bytes += len(markdown.encode("utf-8"))
        summaries.append(summary)

    (args.out_dir / "_catalogo.md").write_text(render_catalog(summaries), encoding="utf-8")
    (cache_dir / "catalogo.json").write_text(
        json.dumps([asdict(s) for s in summaries], indent=1, ensure_ascii=False), encoding="utf-8")

    included = [s for s in summaries if s.included]
    areas: Dict[str, int] = {}
    for s in included:
        areas[s.area] = areas.get(s.area, 0) + 1
    print(f"\n{len(included)} paquetes escritos en {packages_dir} ({total_bytes / 1_048_576:.1f} MB).")
    print("Por área: " + ", ".join(f"{a}={n}" for a, n in sorted(areas.items(), key=lambda x: -x[1])))
    print(f"Excluidos: {len(summaries) - len(included)} (detalle en {args.out_dir / '_catalogo.md'}).")
    print("\nSiguiente paso: python3 scripts/crear_vector_store.py --dry-run")
    return 0


if __name__ == "__main__":
    sys.exit(main())
