from __future__ import annotations

import builtins
import importlib
import json
import sys
from pathlib import Path

import pytest

from mods import catalog


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def test_default_dep_path_uses_core_home_and_non_core_extras() -> None:
    core = {"id": "Org/tool", "metadata": {"category": ["core"]}}
    non_core = {"id": "demo-pack", "metadata": {"category": ["demo"]}}
    assert catalog._default_dep_path(core) == "home/tool"
    assert catalog._default_dep_path(non_core) == "extras/demo-pack"


def test_filter_zde_visible_deps_skips_only_explicit_false() -> None:
    deps = [
        {"id": "a"},
        {"id": "b", "zde": True},
        {"id": "c", "zde": False},
        "invalid-entry",
    ]
    assert [dep["id"] for dep in catalog.filter_zde_visible_deps(deps)] == ["a", "b"]


def test_load_deps_yaml_applies_defaults(tmp_path: Path) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(
        deps_file,
        """
        dependencies:
          - id: org/core-tool
            repo: https://example.invalid/core-tool.git
            metadata:
              category: core
          - id: extras-tool
            repo: https://example.invalid/extras-tool.git
        """,
    )
    deps = catalog.load_deps_yaml(deps_file)
    assert deps[0]["path"] == "home/core-tool"
    assert deps[1]["path"] == "extras/extras-tool"
    assert deps[1]["metadata"]["category"] == ["Other"]


@pytest.mark.parametrize(
    ("yaml_text", "match"),
    [
        (
            """
            dependencies:
              - id: dep-a
                repo: x
              - id: dep-a
                repo: y
            """,
            "Duplicate dependency id",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                aliases: [dep-b]
              - id: dep-b
                repo: y
            """,
            "conflicts with alias",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                depends_on: [dep-missing]
            """,
            "depends on unknown id",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                depends_on: [dep-a]
            """,
            "cannot depend on itself",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  tool: ninja
            """,
            "build.tool must be one of",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                env:
                  - name: BAD
                    add_to_path: "not-a-list"
            """,
            "invalid env.add_to_path",
        ),
    ],
)
def test_load_deps_yaml_validates_invalid_shapes(tmp_path: Path, yaml_text: str, match: str) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(deps_file, yaml_text)
    with pytest.raises(RuntimeError, match=match):
        catalog.load_deps_yaml(deps_file)


def test_merge_deps_lists_enriches_existing_and_keeps_primary_fields() -> None:
    primary = [
        {
            "id": "dep-a",
            "repo": "primary",
            "path": "home/a",
            "metadata": {"category": ["Core"], "name": "Primary Name"},
            "aliases": ["a"],
        }
    ]
    secondary = [
        {
            "id": "dep-a",
            "repo": "secondary",
            "branch": "main",
            "metadata": {"category": ["Demo"], "summary": "from secondary"},
            "aliases": ["A", "alpha"],
        },
        {
            "id": "dep-b",
            "repo": "secondary-b",
            "path": "extras/dep-b",
            "metadata": {"category": ["Other"]},
        },
    ]
    merged = catalog.merge_deps_lists(primary, secondary)
    dep_a = next(dep for dep in merged if dep["id"] == "dep-a")
    dep_b = next(dep for dep in merged if dep["id"] == "dep-b")

    assert dep_a["repo"] == "primary"
    assert dep_a["branch"] == "main"
    assert dep_a["metadata"]["name"] == "Primary Name"
    assert dep_a["metadata"]["summary"] == "from secondary"
    assert dep_a["metadata"]["category"] == ["Core", "Demo"]
    assert dep_a["aliases"] == ["a", "alpha"]
    assert dep_b["repo"] == "secondary-b"


def test_order_deps_by_dependency_topological_order_and_cycle_error() -> None:
    ordered = catalog.order_deps_by_dependency(
        [
            {"id": "app", "depends_on": ["lib", "tool"]},
            {"id": "tool", "depends_on": ["lib"]},
            {"id": "lib"},
        ]
    )
    ordered_ids = [dep["id"] for dep in ordered]
    assert ordered_ids.index("lib") < ordered_ids.index("tool")
    assert ordered_ids.index("tool") < ordered_ids.index("app")

    with pytest.raises(RuntimeError, match="Dependency cycle detected"):
        catalog.order_deps_by_dependency(
            [
                {"id": "a", "depends_on": ["b"]},
                {"id": "b", "depends_on": ["a"]},
            ]
        )


def test_repo_name_from_id_without_namespace() -> None:
    assert catalog._repo_name_from_id("plain-id") == "plain-id"


def test_declared_categories_non_string_or_list_returns_empty() -> None:
    dep = {"id": "dep", "metadata": {"category": 123}}
    assert catalog._default_dep_path(dep) == "extras/dep"


@pytest.mark.parametrize(
    ("dep", "match"),
    [
        ({"id": "dep-a", "env": "bad"}, "invalid env list"),
        ({"id": "dep-a", "env": [""]}, "invalid env entry"),
        ({"id": "dep-a", "env": [123]}, "invalid env entry"),
        ({"id": "dep-a", "env": [{"name": ""}]}, "invalid env.name"),
        ({"id": "dep-a", "env": [{"name": "A", "path": ""}]}, "invalid env.path"),
        ({"id": "dep-a", "env": [{"name": "A", "add_to_path": [""]}]}, "invalid env.add_to_path"),
    ],
)
def test_validate_dep_env_error_branches(dep: dict[str, object], match: str) -> None:
    with pytest.raises(RuntimeError, match=match):
        catalog._validate_dep_env(dep)  # type: ignore[arg-type]


def test_validate_dep_env_accepts_non_empty_string_entry() -> None:
    catalog._validate_dep_env({"id": "dep-a", "env": ["DEP_A"]})


def test_load_deps_yaml_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="Missing dependency catalog"):
        catalog.load_deps_yaml(tmp_path / "missing.yml")


def test_load_deps_yaml_yq_fallback_when_pyyaml_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps_file = tmp_path / "deps.yml"
    deps_file.write_text("ignored\n", encoding="utf-8")

    monkeypatch.setattr(catalog, "yaml", None)
    monkeypatch.setattr(catalog, "process_run", lambda *args, **kwargs: 0)
    payload = json.dumps([{"id": "dep-a", "repo": "x", "metadata": {"category": ["Other"]}, "path": "extras/dep-a"}])
    monkeypatch.setattr(catalog, "process_run_capture", lambda *args, **kwargs: payload)
    deps = catalog.load_deps_yaml(deps_file)
    assert deps[0]["id"] == "dep-a"


def test_load_deps_yaml_requires_pyyaml_or_yq(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    deps_file = tmp_path / "deps.yml"
    deps_file.write_text("ignored\n", encoding="utf-8")
    monkeypatch.setattr(catalog, "yaml", None)
    monkeypatch.setattr(catalog, "process_run", lambda *args, **kwargs: 1)
    with pytest.raises(RuntimeError, match="PyYAML or yq is required to parse deps.yml"):
        catalog.load_deps_yaml(deps_file)


def test_catalog_module_handles_yaml_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("forced missing yaml")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("mods.catalog", None)
    imported = importlib.import_module("mods.catalog")
    try:
        assert imported.yaml is None
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        sys.modules.pop("mods.catalog", None)
        importlib.import_module("mods.catalog")


@pytest.mark.parametrize(
    ("yaml_text", "match"),
    [
        (
            """
            dependencies: {}
            """,
            "top-level 'dependencies' list",
        ),
        (
            """
            dependencies:
              - 123
            """,
            "Each dependency entry must be a map",
        ),
        (
            """
            dependencies:
              - repo: x
            """,
            "missing required string field: id",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: ''
            """,
            "missing required string field: repo",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                path: ''
            """,
            "missing required string field: path",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                required: 1
            """,
            "non-boolean required flag",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                zde: 1
            """,
            "non-boolean zde flag",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                commit: ''
            """,
            "invalid commit value",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                branch: ''
            """,
            "invalid branch value",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                tag: ''
            """,
            "invalid tag value",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                tag: 123
            """,
            "invalid tag value",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                metadata: 1
            """,
            "non-map metadata",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                metadata:
                  category: ''
            """,
            "invalid metadata.category",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                metadata:
                  category:
                    - ok
                    - ''
            """,
            "invalid metadata.category list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                metadata:
                  category: 123
            """,
            "invalid metadata.category",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                aliases: bad
            """,
            "invalid aliases list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                depends_on: bad
            """,
            "invalid depends_on list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build: bad
            """,
            "invalid build config",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  commands: []
            """,
            "invalid build.commands list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  args: bad
            """,
            "invalid build.args list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  artifacts: bad
            """,
            "invalid build.artifacts list",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  root: ''
            """,
            "invalid build.root",
        ),
        (
            """
            dependencies:
              - id: dep-a
                repo: x
                build:
                  stage: bad
            """,
            "invalid build.stage",
        ),
    ],
)
def test_load_deps_yaml_additional_validation_branches(tmp_path: Path, yaml_text: str, match: str) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(deps_file, yaml_text)
    with pytest.raises(RuntimeError, match=match):
        catalog.load_deps_yaml(deps_file)


def test_load_deps_yaml_build_false_duplicate_path_branch(tmp_path: Path) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(
        deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            build: false
          - id: dep-a
            repo: y
        """,
    )
    with pytest.raises(RuntimeError, match="Duplicate dependency id"):
        catalog.load_deps_yaml(deps_file)


def test_load_deps_yaml_duplicate_inside_build_false_branch(tmp_path: Path) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(
        deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
          - id: dep-a
            repo: y
            build: false
        """,
    )
    with pytest.raises(RuntimeError, match="Duplicate dependency id"):
        catalog.load_deps_yaml(deps_file)


def test_alias_conflict_on_alias_owner_branch(tmp_path: Path) -> None:
    deps_file = tmp_path / "deps.yml"
    _write_yaml(
        deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            aliases: [shared]
          - id: dep-b
            repo: y
            aliases: [shared]
        """,
    )
    with pytest.raises(RuntimeError, match="Alias 'shared' on 'dep-b' conflicts with 'dep-a'"):
        catalog.load_deps_yaml(deps_file)


def test_merge_deps_lists_hits_alias_none_and_existing_category_continue_branch() -> None:
    primary = [
        {"id": "dep-a", "repo": "x", "metadata": {"category": ["Core"]}},
    ]
    secondary = [
        {
            "id": "dep-a",
            "repo": "y",
            "metadata": {"category": ["core", "Demo"]},
            "aliases": ["a"],
        }
    ]
    merged = catalog.merge_deps_lists(primary, secondary)
    dep_a = merged[0]
    assert dep_a["aliases"] == ["a"]
    assert dep_a["metadata"]["category"] == ["Core", "Demo"]
