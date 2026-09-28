from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[5]


def test_compose_uses_canonical_image_reference() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["zeal8bit-dev-env"]

    assert service["image"] == "${ZDE_IMAGE_REF:-zoul0813/zeal-dev-environment:latest}"


def test_setup_action_exports_pulled_image_reference() -> None:
    action_path = REPO_ROOT / "github" / "setup-zde" / "action.yml"
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    steps = {step["name"]: step for step in action["runs"]["steps"]}

    assert 'docker pull "${{ inputs.image }}"' in steps["Pull ZDE image"]["run"]
    assert 'echo "ZDE_IMAGE_REF=${{ inputs.image }}" >> $GITHUB_ENV' in steps["Setup Environment"]["run"]


def test_setup_action_syncs_without_updating_pinned_checkout() -> None:
    action_path = REPO_ROOT / "github" / "setup-zde" / "action.yml"
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    steps = {step["name"]: step for step in action["runs"]["steps"]}
    install_script = steps["Install ZDE Dependencies"]["run"]

    assert "./zde sync" in install_script
    assert "./zde update" not in install_script
    assert 'zde_head="$(git rev-parse HEAD)"' in install_script
    assert 'if [ "$(git rev-parse HEAD)" != "$zde_head" ]; then' in install_script
