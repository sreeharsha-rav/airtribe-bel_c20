from pathlib import Path

import pytest

import fs_core
from config import settings


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_DIR", tmp_path)
    return tmp_path


def test_resolve_within_root_accepts_nested_relative_path(sandbox):
    (sandbox / "engineering").mkdir()
    (sandbox / "engineering" / "alice.txt").write_text("hi", encoding="utf-8")
    resolved = fs_core.resolve_within_root("engineering/alice.txt")
    assert resolved == sandbox / "engineering" / "alice.txt"


def test_resolve_within_root_rejects_absolute_path(sandbox):
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("/etc/passwd")


def test_resolve_within_root_rejects_dotdot_escape(sandbox):
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("../outside.txt")


def test_resolve_within_root_rejects_path_resolving_outside_root(sandbox, monkeypatch):
    # A syntactically clean relative path (no "..", not absolute) should still
    # be rejected if it resolves outside the sandbox root -- e.g. via a
    # symlink. Real symlinks are awkward to create reliably on Windows
    # without elevated privileges, so we monkeypatch Path.resolve to simulate
    # that outcome and exercise the post-resolve containment check directly.
    original_resolve = Path.resolve

    def fake_resolve(self, *args, **kwargs):
        if self == sandbox / "innocuous.txt":
            return Path("/definitely/outside")
        return original_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", fake_resolve)
    with pytest.raises(ValueError):
        fs_core.resolve_within_root("innocuous.txt")


def test_extract_text_reads_txt_file(sandbox):
    (sandbox / "note.txt").write_text("hello sandbox", encoding="utf-8")
    assert fs_core.extract_text(sandbox / "note.txt") == "hello sandbox"


def test_extract_text_reads_docx_and_pdf_fixtures():
    # Uses the real sample_data tree copied in Task 1 -- generating valid
    # .docx/.pdf bytes from scratch in a unit test isn't worth it.
    docx_path = settings.ROOT_DIR / "engineering" / "devops_bob.docx"
    pdf_path = settings.ROOT_DIR / "engineering" / "frontend_priya.pdf"
    assert fs_core.extract_text(docx_path).strip() != ""
    assert fs_core.extract_text(pdf_path).strip() != ""


def test_extract_text_rejects_unsupported_extension(sandbox):
    bad = sandbox / "resume.doc"
    bad.write_text("legacy format", encoding="utf-8")
    with pytest.raises(ValueError):
        fs_core.extract_text(bad)


def test_file_metadata_fields(sandbox):
    (sandbox / "note.txt").write_text("hi", encoding="utf-8")
    meta = fs_core.file_metadata(sandbox / "note.txt")
    assert meta["name"] == "note.txt"
    assert meta["path"] == "note.txt"
    assert meta["extension"] == ".txt"
    assert meta["size_bytes"] == 2
    assert "modified" in meta


def test_is_allowed_extension_and_exceeds_max_size(sandbox, monkeypatch):
    allowed = sandbox / "note.txt"
    allowed.write_text("hi", encoding="utf-8")
    disallowed = sandbox / "note.exe"
    disallowed.write_bytes(b"\x00")

    assert fs_core.is_allowed_extension(allowed) is True
    assert fs_core.is_allowed_extension(disallowed) is False

    monkeypatch.setattr(settings, "MAX_FILE_SIZE_BYTES", 1)
    assert fs_core.exceeds_max_size(allowed) is True
