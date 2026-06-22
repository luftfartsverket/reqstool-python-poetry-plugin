# Copyright © LFV

from unittest.mock import MagicMock

import tomlkit
from reqstool_python_decorators.decorators.decorators import SVCs

from reqstool_python_poetry_plugin.plugin import ReqstoolPlugin


def _make_plugin(root_dir, reqstool_config: dict | None = None) -> ReqstoolPlugin:
    plugin = ReqstoolPlugin()
    poetry = MagicMock()
    poetry.package.root_dir = root_dir
    poetry.pyproject.data = {"tool": {"reqstool": reqstool_config or {}}}
    plugin._poetry = poetry
    plugin._cleo_io = MagicMock()
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

    data = tomlkit.loads(pyproject_path.read_text())
    includes = list(data["tool"]["poetry"]["include"])
    assert includes.count("reqstool_config.yml") == 1


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
    plugin._cleanup_post_build()  # must not raise


@SVCs("SVC_POETRY_PLUGIN_005")
def test_cleanup_pyproject_strips_excess_blank_lines(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    pyproject_path.write_text('[tool.poetry]\nname = "x"\n\n\n\ninclude = ["reqstool_config.yml"]\n')

    plugin = _make_plugin(tmp_path)
    plugin._cleanup_pyproject_install_after_install()

    assert "\n\n\n" not in pyproject_path.read_text()


@SVCs("SVC_POETRY_PLUGIN_005")
def test_cleanup_pyproject_is_a_noop_without_excess_blank_lines(tmp_path):
    pyproject_path = tmp_path / "pyproject.toml"
    original = '[tool.poetry]\nname = "x"\n\ninclude = ["reqstool_config.yml"]\n'
    pyproject_path.write_text(original)

    plugin = _make_plugin(tmp_path)
    plugin._cleanup_pyproject_install_after_install()

    assert pyproject_path.read_text() == original
