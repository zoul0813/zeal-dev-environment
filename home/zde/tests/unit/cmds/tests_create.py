from __future__ import annotations

import json
from pathlib import Path

import pytest

from cmds import create


def test_create_refuses_existing_normalized_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "output"
    existing = output / "my-project"
    existing.mkdir(parents=True)
    protected = existing / "README.md"
    protected.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(create, "_create_out_dir", lambda: output)

    rc = create.main(["zealos-sdcc", "--name", "My Project"])

    assert rc != 0
    assert protected.read_text(encoding="utf-8") == "keep"


def test_create_refuses_existing_custom_template_destination(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    template = tmp_path / "template"
    project_template = template / "{{ cookiecutter.slug }}"
    project_template.mkdir(parents=True)
    (template / "cookiecutter.json").write_text(
        json.dumps({"name": "project", "slug": "generated-project"}),
        encoding="utf-8",
    )
    (project_template / "content.txt").write_text("generated", encoding="utf-8")

    output = tmp_path / "output"
    existing = output / "custom-output"
    existing.mkdir(parents=True)
    protected = existing / "content.txt"
    protected.write_text("keep", encoding="utf-8")
    monkeypatch.setattr(create, "_create_out_dir", lambda: output)

    rc = create.main(
        [str(template), "--name", "Raw Project Name", "slug=custom-output"]
    )

    assert rc != 0
    assert protected.read_text(encoding="utf-8") == "keep"
