
import hashlib
from pathlib import Path

from v26r2_file_hash_verifier import summarize, verify_hashes


def test_hash_verifier_reports_match(tmp_path):
    target = tmp_path / "docs/example.txt"
    target.parent.mkdir(parents=True)
    target.write_text("hello\n", encoding="utf-8")
    expected = {"docs/example.txt": hashlib.sha256(b"hello\n").hexdigest()}
    results = verify_hashes(tmp_path, expected)
    summary = summarize(results)
    assert summary["all_present"] is True
    assert summary["all_hashes_match"] is True
    assert summary["missing_paths"] == []
    assert summary["mismatched_paths"] == []


def test_hash_verifier_reports_missing(tmp_path):
    results = verify_hashes(tmp_path, {"missing.txt": "0" * 64})
    summary = summarize(results)
    assert summary["all_present"] is False
    assert summary["all_hashes_match"] is False
    assert summary["missing_paths"] == ["missing.txt"]


def test_hash_verifier_reports_mismatch(tmp_path):
    target = tmp_path / "file.txt"
    target.write_text("actual\n", encoding="utf-8")
    results = verify_hashes(tmp_path, {"file.txt": hashlib.sha256(b"expected\n").hexdigest()})
    summary = summarize(results)
    assert summary["all_present"] is True
    assert summary["all_hashes_match"] is False
    assert summary["mismatched_paths"] == ["file.txt"]
