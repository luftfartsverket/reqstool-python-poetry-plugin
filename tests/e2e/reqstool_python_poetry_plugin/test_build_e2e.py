# Copyright © LFV
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

import pytest
from reqstool_python_decorators.decorators.decorators import SVCs

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "test_project"

EXPECTED_IN_TARBALL = [
    "reqstool_config.yml",
    "annotations.yml",
    "requirements.yml",
    "software_verification_cases.yml",
]


def _plugin_installed() -> bool:
    """Return True if the reqstool poetry plugin is registered as an application plugin."""
    from importlib.metadata import entry_points

    eps = entry_points(group="poetry.application.plugin")
    return any(ep.name == "reqstool" for ep in eps)


@pytest.mark.e2e
@pytest.mark.skipif(not shutil.which("poetry"), reason="poetry not on PATH")
@pytest.mark.skipif(not _plugin_installed(), reason="reqstool-python-poetry-plugin not installed in poetry")
@SVCs("SVC_POETRY_PLUGIN_001", "SVC_POETRY_PLUGIN_002")
def test_poetry_build_sdist_contains_reqstool_artifacts():
    """poetry build (sdist) triggers the reqstool plugin and bundles all artifacts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_project = Path(tmpdir) / "test_project"
        shutil.copytree(
            FIXTURE_DIR,
            tmp_project,
            ignore=shutil.ignore_patterns("dist", "build", "__pycache__", ".venv", "poetry.lock"),
        )

        result = subprocess.run(
            ["poetry", "build", "--format", "sdist"],
            cwd=tmp_project,
            capture_output=True,
            text=True,
            env={k: v for k, v in os.environ.items() if k != "POETRY_ACTIVE"},
        )
        assert result.returncode == 0, f"poetry build failed:\n{result.stderr}"

        tarballs = sorted((tmp_project / "dist").glob("mypackage-*.tar.gz"))
        assert tarballs, "No tarball found in dist/"

        with tarfile.open(tarballs[-1]) as tf:
            names = tf.getnames()
            for expected in EXPECTED_IN_TARBALL:
                assert any(
                    expected in n for n in names
                ), f"{expected!r} missing from {tarballs[-1].name};\ngot: {names}"
            # Verify annotations.yml content — confirms the decorator processor ran
            member = next(m for m in tf.getmembers() if "annotations.yml" in m.name)
            annotations_content = tf.extractfile(member).read().decode()

        assert "REQ_001" in annotations_content, "annotations.yml missing REQ_001"
        assert "SVC_001" in annotations_content, "annotations.yml missing SVC_001"
