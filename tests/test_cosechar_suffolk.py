"""Pruebas sin red del cosechador de entrevistas del Suffolk LIT Lab."""
import zipfile

from scripts.cosechar_suffolk import (
    RepoInfo,
    build_package,
    classify_area,
    docx_text,
    extract_metadata,
    render_catalog,
)

MAIN_YAML = """\
---
include:
  - docassemble.AssemblyLine:assembly_line.yml
---
metadata:
  title: Motion to Stay Eviction
  description: Ask the court to delay your eviction.
  jurisdiction: NAM-US-US+MA
  LIST_topics:
    - HO-02-00-00-00
  form_numbers:
    - SP-6A
---
question: What is your name?
fields:
  - First name: users[0].name.first
"""

SECONDARY_YAML = """\
---
metadata:
  title: Notice of Appeal
---
question: Notice
"""


def make_docx(path, paragraphs):
    body = "".join(f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>" for text in paragraphs)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("word/document.xml", f'<?xml version="1.0"?><w:document><w:body>{body}</w:body></w:document>')


def make_repo(tmp_path):
    pkg = tmp_path / "docassemble" / "MotionToStayEviction" / "data"
    (pkg / "questions").mkdir(parents=True)
    (pkg / "templates").mkdir(parents=True)
    (pkg / "questions" / "NOA.yml").write_text(SECONDARY_YAML, encoding="utf-8")
    (pkg / "questions" / "SP6A.yml").write_text(MAIN_YAML, encoding="utf-8")
    make_docx(pkg / "templates" / "motion.docx", ["Plaintiff: {{ users[0].name.full() }}", "{%p if stay %}Stay{%p endif %}"])
    (tmp_path / "README.md").write_text("# Motion to stay\n", encoding="utf-8")
    return tmp_path


def test_docx_text_keeps_jinja_and_unescapes(tmp_path):
    path = tmp_path / "t.docx"
    make_docx(path, ["Hola {{ user.name }}", "a &amp; b &lt;c&gt;"])
    assert docx_text(path) == "Hola {{ user.name }}\na & b <c>"


def test_docx_text_tolerates_invalid_file(tmp_path):
    path = tmp_path / "broken.docx"
    path.write_bytes(b"not a zip")
    assert docx_text(path) == ""


def test_extract_metadata_prefers_richest_block():
    meta = extract_metadata([SECONDARY_YAML, MAIN_YAML])
    assert meta["title"] == "Motion to Stay Eviction"
    assert meta["LIST_topics"] == ["HO-02-00-00-00"]


def test_classify_area():
    assert classify_area("docassemble-AssemblyLine", "", []) == "framework"
    assert classify_area("docassemble-Foo", "", ["FA-07-00-00-00"]) == "familia"
    assert classify_area("docassemble-Foo", "", ["WO-01"]) == "laboral"
    assert classify_area("docassemble-TenantRepair", "", []) == "vivienda"
    assert classify_area("docassemble-Misc", "Something", []) == "sin-clasificar"
    assert classify_area("docassemble-LITLabTheme", "", []) == "framework"
    assert classify_area("docassemble-MATC1AUncontestedDivorce", "", []) == "familia"
    assert classify_area("docassemble-NoticeOfAppealInternalForm", "", []) == "procesal-general"
    assert classify_area("docassemble-VTCertificateOfService", "", []) == "procesal-general"
    assert classify_area("docassemble-VTFeedback", "", []) == "framework"


def test_build_package_renders_markdown(tmp_path):
    repo = RepoInfo(org="SuffolkLITLab", name="docassemble-MotionToStayEviction",
                    url="https://github.com/SuffolkLITLab/docassemble-MotionToStayEviction", license="MIT")
    summary, markdown = build_package(repo, make_repo(tmp_path))

    assert summary.title == "Motion to Stay Eviction"
    assert summary.area == "vivienda"
    assert summary.form_numbers == ["SP-6A"]
    assert len(summary.interviews) == 2
    assert markdown.startswith("# Motion to Stay Eviction\n")
    assert "`docassemble.MotionToStayEviction`" in markdown
    assert "## YAML: docassemble/MotionToStayEviction/data/questions/SP6A.yml" in markdown
    assert "/blob/main/docassemble/MotionToStayEviction/data/questions/SP6A.yml" in markdown
    assert "{{ users[0].name.full() }}" in markdown
    assert "Ley 820/2003" in markdown


def test_render_catalog_lists_excluded(tmp_path):
    repo = RepoInfo(org="o", name="docassemble-MotionToStayEviction", url="u", license="MIT")
    summary, _ = build_package(repo, make_repo(tmp_path))
    from scripts.cosechar_suffolk import PackageSummary

    excluded = PackageSummary(repo=RepoInfo(org="o", name="docassemble-Private", url="v"), included=False,
                              exclusion_reason="sin licencia declarada")
    catalog = render_catalog([summary, excluded])
    assert "## vivienda (1)" in catalog
    assert "`docassemble-Private` (v): sin licencia declarada" in catalog
