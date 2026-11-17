from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[5]


def test_compose_uses_canonical_image_reference() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8"))
    service = compose["services"]["zeal8bit-dev-env"]

    assert "platform" not in service
    assert "platforms" not in service["build"]
    assert service["image"] == "${ZDE_IMAGE_REF:-docker.io/zoul0813/zeal-dev-environment:latest}"
    assert "userns_mode" not in service
    assert "user" not in service


def test_rootless_podman_override_preserves_host_ids_and_entrypoint_setup() -> None:
    compose = yaml.safe_load((REPO_ROOT / "docker-compose.podman.yml").read_text(encoding="utf-8"))
    assert compose["x-podman"]["in_pod"] is False
    assert compose["services"] == {
        "zeal8bit-dev-env": {
            "userns_mode": "keep-id:uid=${HOST_UID},gid=${HOST_GID}",
            "user": "0:0",
        }
    }


def test_setup_action_exports_pulled_image_reference() -> None:
    action_path = REPO_ROOT / "github" / "setup-zde" / "action.yml"
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))
    steps = {step["name"]: step for step in action["runs"]["steps"]}

    assert action["inputs"]["image"]["default"] == "docker.io/zoul0813/zeal-dev-environment:latest"
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
