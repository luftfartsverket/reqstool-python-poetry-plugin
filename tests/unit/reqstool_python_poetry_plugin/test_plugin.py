# Copyright © LFV

from unittest.mock import MagicMock

import pytest
import tomlkit
from cleo.io.io import IO
from poetry.poetry import Poetry
from reqstool_python_decorators.decorators.decorators import SVCs
from ruamel.yaml import YAML

from reqstool_python_poetry_plugin.plugin import ReqstoolPlugin


def _make_plugin(root_dir, reqstool_config: dict | None = None) -> ReqstoolPlugin:
    plugin = ReqstoolPlugin()
    poetry = MagicMock(spec=Poetry)
    poetry.package.root_dir = root_dir
    poetry.package.version = "1.0.0"
    poetry.pyproject.data = {"tool": {"reqstool": reqstool_config or {}}}
    plugin._poetry = poetry
    plugin._cleo_io = MagicMock(spec=IO)
    return plugin


@SVCs("SVC_POETRY_PLUGIN_003")
def test_update_sdist_include_adds_reqstool_entries(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.poetry]\nname = "x"\n')

    plugin = _make_plugin(tmp_path)
    plugin._update_sdist_include()

    data = tomlkit.loads(pyproject_path.read_text())
    includes = list(data["tool"]["poetry"]["include"])
    assert "reqstool_config.yml" in includes
    assert "reqstool/**/*" in includes
    assert "build/reqstool/**/*" in includes


@SVCs("SVC_POETRY_PLUGIN_003")
def test_update_sdist_include_is_idempotent(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.poetry]\nname = "x"\ninclude = ["reqstool_config.yml"]\n')

    plugin = _make_plugin(tmp_path)
    plugin._update_sdist_include()
    plugin._update_sdist_include()

    data = tomlkit.loads(pyproject_path.read_text())
    includes = list(data["tool"]["poetry"]["include"])
    assert includes.count("reqstool_config.yml") == 1
    assert includes.count("reqstool/**/*") == 1
    assert includes.count("build/reqstool/**/*") == 1


@SVCs("SVC_POETRY_PLUGIN_003")
def test_update_sdist_include_honors_custom_directories(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.poetry]\nname = "x"\n')

    plugin = _make_plugin(
        tmp_path, reqstool_config={"dataset_directory": "custom_ds", "output_directory": "custom_out"}
    )
    plugin._update_sdist_include()

    data = tomlkit.loads(pyproject_path.read_text())
    includes = list(data["tool"]["poetry"]["include"])
    assert "custom_ds/**/*" in includes
    assert "custom_out/**/*" in includes


@SVCs("SVC_POETRY_PLUGIN_004")
def test_cleanup_post_build_removes_reqstool_config(tmp_path):
    config_file = tmp_path / "reqstool_config.yml"
    config_file.write_text("language: python\n")

    plugin = _make_plugin(tmp_path)
    plugin._cleanup_post_build()

    assert not config_file.exists()


@SVCs("SVC_POETRY_PLUGIN_004")
def test_cleanup_post_build_is_a_noop_when_no_config_file(tmp_path):
    plugin = _make_plugin(tmp_path)
    plugin._cleanup_post_build()

    plugin._cleo_io.write_line.assert_not_called()


@SVCs("SVC_POETRY_PLUGIN_005")
def test_cleanup_pyproject_strips_excess_blank_lines(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.poetry]\nname = "x"\n\n\n\ninclude = ["reqstool_config.yml"]\n')

    plugin = _make_plugin(tmp_path)
    plugin._cleanup_pyproject_install_after_install()

    assert pyproject_path.read_text() == '[tool.poetry]\nname = "x"\n\ninclude = ["reqstool_config.yml"]\n'


@SVCs("SVC_POETRY_PLUGIN_005")
def test_cleanup_pyproject_is_a_noop_without_excess_blank_lines(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    original = '[tool.poetry]\nname = "x"\n\ninclude = ["reqstool_config.yml"]\n'
    pyproject_path.write_text(original)

    plugin = _make_plugin(tmp_path)
    plugin._cleanup_pyproject_install_after_install()

    assert pyproject_path.read_text() == original


@SVCs("SVC_POETRY_PLUGIN_001")
def test_generate_reqstool_config_raises_when_requirements_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "reqstool").mkdir()

    plugin = _make_plugin(tmp_path)

    with pytest.raises(RuntimeError, match="requirements.yml"):
        plugin._generate_reqstool_config()


@SVCs("SVC_POETRY_PLUGIN_001")
def test_generate_reqstool_config_includes_only_existing_optional_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dataset_dir = tmp_path / "reqstool"
    dataset_dir.mkdir()
    (dataset_dir / "requirements.yml").write_text("requirements: []\n")
    (dataset_dir / "software_verification_cases.yml").write_text("software_verification_cases: []\n")

    plugin = _make_plugin(tmp_path)
    plugin._generate_reqstool_config()

    output = tmp_path / "reqstool_config.yml"
    data = YAML().load(output.read_text())
    resources = data["resources"]
    assert "requirements" in resources
    assert "software_verification_cases" in resources
    assert "manual_verification_results" not in resources
    assert "annotations" not in resources


@SVCs("SVC_POETRY_PLUGIN_001")
def test_generate_reqstool_config_normalizes_test_results_to_a_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    dataset_dir = tmp_path / "reqstool"
    dataset_dir.mkdir()
    (dataset_dir / "requirements.yml").write_text("requirements: []\n")

    plugin = _make_plugin(tmp_path, reqstool_config={"test_results": "build/junit.xml"})
    plugin._generate_reqstool_config()

    output = tmp_path / "reqstool_config.yml"
    data = YAML().load(output.read_text())
    assert data["resources"]["test_results"] == ["build/junit.xml"]
