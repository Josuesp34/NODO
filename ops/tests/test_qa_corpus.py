import importlib.util
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "qa_corpus.py"
spec = importlib.util.spec_from_file_location("qa_corpus", path)
corpus = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corpus)


def test_corpus_guard_requires_both_flags(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("NODO_SYNTHETIC_QA", "1")
    with pytest.raises(SystemExit):
        corpus.guard()
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.delenv("NODO_SYNTHETIC_QA")
    with pytest.raises(SystemExit):
        corpus.guard()
    monkeypatch.setenv("NODO_SYNTHETIC_QA", "1")
    corpus.guard()


def test_fixture_shape_and_hash_are_reproducible():
    first, first_hash = corpus.read_config(corpus.CONFIG)
    second, second_hash = corpus.read_config(corpus.CONFIG)
    assert first == second and first_hash == second_hash
    assert first["athletes"] * first["weeks"] * 7 == 5880
    assert set(first["sports"]) == {"running", "cycling", "swimming", "triathlon"}
    assert len(first["timezones"]) == 4
    assert len(corpus.prescription("swimming")[0]) == 1
    assert corpus.prescription("swimming")[0][0]["steps"][0]["target"]["unit"] == "sec_per_100m"
    assert corpus.prescription("running")[0][0]["steps"][0]["target"]["unit"] == "sec_per_km"


def test_benchmark_rejects_remote_api_before_network():
    config, fingerprint = corpus.read_config(corpus.CONFIG)
    with pytest.raises(SystemExit):
        corpus.benchmark(config, fingerprint, "https://production.example.com/api/v1", 8, 2)
