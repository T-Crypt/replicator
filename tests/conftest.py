import pytest


@pytest.fixture(autouse=True)
def _no_operator_services(tmp_path, monkeypatch):
    """Every test sees an empty services.json, never the machine's own engines, printers or keys."""
    from replicator import config
    monkeypatch.setattr(config, "PATH", tmp_path / "services.json")
    for k in ("REPLICATOR_LLM_URL", "REPLICATOR_LLM_MODEL", "REPLICATOR_LLM_KEY"):
        monkeypatch.delenv(k, raising=False)
