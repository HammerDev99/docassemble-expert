"""Plan de sincronización del vector store (sin llamar a OpenAI)."""
from scripts.crear_vector_store import plan_prune, plan_sync


def test_plan_sync_uploads_new_and_changed_and_skips_unchanged(tmp_path):
    same = tmp_path / "igual.md"
    same.write_text("abc", encoding="utf-8")
    changed = tmp_path / "cambiado.md"
    changed.write_text("nuevo contenido", encoding="utf-8")
    new = tmp_path / "nuevo.md"
    new.write_text("x", encoding="utf-8")
    remote = {"igual.md": ("file-1", 3), "cambiado.md": ("file-2", 4), "borrado.md": ("file-3", 9)}

    to_upload, to_replace, unchanged = plan_sync([same, changed, new], remote)

    assert to_upload == [changed, new]
    assert to_replace == ["file-2"]
    assert unchanged == 1


def test_plan_prune_only_removes_missing_harvested_packages(tmp_path):
    kept = tmp_path / "docassemble-Keep.md"
    kept.write_text("x", encoding="utf-8")
    remote = {
        "docassemble-Keep.md": ("file-1", 1),
        "docassemble-Gone.md": ("file-2", 5),
        "manual_oficial.pdf": ("file-3", 9),
        "inventario.json": ("file-4", 9),
    }
    assert plan_prune([kept], remote) == [("docassemble-Gone.md", "file-2")]
