"""Container packaging guards for runtime configuration dependencies."""

from pathlib import Path


def test_docker_image_includes_runtime_configs_and_demo_research() -> None:
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY config ./config" in dockerfile
    assert "COPY data ./data" in dockerfile
    assert Path("config/intake/northstar-requirements.json").is_file()
    assert Path("config/pilot/northstar-fictional-pilot-policy-v1.json").is_file()
    assert Path("data/research/northstar-research-v1.json").is_file()
