# Copyright © LFV

import gzip
import io
import os
import tarfile
import tempfile
from pathlib import Path
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from cleo.io.io import IO
from poetry.plugins.plugin import Plugin
from poetry.poetry import Poetry
from poetry.core.masonry.builders.wheel import WheelBuilder
from poetry.core.masonry.builders.sdist import SdistBuilder
from reqstool_python_decorators.processors.decorator_processor import DecoratorProcessor
from ruamel.yaml import YAML


class ReqstoolPlugin(Plugin):

    CONFIG_SOURCES = "sources"
    CONFIG_DATASET_DIRECTORY = "dataset_directory"
    CONFIG_OUTPUT_DIRECTORY = "output_directory"
    CONFIG_TEST_RESULTS: str = "test_results"

    INPUT_FILE_REQUIREMENTS_YML: str = "requirements.yml"
    INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML: str = "software_verification_cases.yml"
    INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML: str = "manual_verification_results.yml"
    INPUT_FILE_JUNIT_XML: str = "build/junit.xml"
    INPUT_FILE_ANNOTATIONS_YML: str = "annotations.yml"
    INPUT_DIR_DATASET: str = "reqstool"

    OUTPUT_DIR_REQSTOOL: str = "build/reqstool"
    OUTPUT_SDIST_REQSTOOL_YML: str = "reqstool_config.yml"

    ARCHIVE_OUTPUT_DIR_TEST_RESULTS: str = "test_results"

    YAML_LANGUAGE_SERVER = "# yaml-language-server: $schema=https://raw.githubusercontent.com/Luftfartsverket/reqstool-client/main/src/reqstool/resources/schemas/v1/reqstool_index.schema.json\n"  # noqa: E501

    def activate(self, poetry: Poetry, cleo_io: IO) -> None:
        self._poetry = poetry
        self._cleo_io = cleo_io
        cleo_io.write_line("INSIDE ACTIVATE IN POETRY-PLUGIN")

        # pythonpath_from_pyproject_toml = (
        #     poetry.pyproject.data.get("tool").get("pytest").get("ini_options").get("pythonpath")
        # )

        # filtered_pythonpaths: list[str] = [path for path in pythonpath_from_pyproject_toml if path != "."]

        self._create_annotations_file(poetry=poetry)
        # self._append_to_sdist_tar_gz(cleo_io=self._cleo_io, poetry=self._poetry)

    @property
    def post_build_handlers(self):
        return [self.handle_post_build]

    def handle_post_build(self, builder: Any, **kwargs: dict[str, Any]) -> None:
        if isinstance(builder, (WheelBuilder, SdistBuilder)):
            self._cleo_io.write_line("APPENDING TO TAR.GZ")

            self._append_to_sdist_tar_gz(cleo_io=self._cleo_io, poetry=self._poetry)

    def _create_annotations_file(self, poetry: Poetry) -> None:
        """
        Generates the annotations.yml file by processing the reqstool decorators.
        """
        sources = poetry.pyproject.data.get("tool", {}).get("reqstool", {}).get(self.CONFIG_SOURCES, ["src", "tests"])

        reqstool_output_directory: Path = Path(
            poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL)
        )
        annotations_file: Path = Path(reqstool_output_directory, self.INPUT_FILE_ANNOTATIONS_YML)

        decorator_processor = DecoratorProcessor()
        decorator_processor.process_decorated_data(path_to_python_files=sources, output_file=str(annotations_file))

    def _append_to_sdist_tar_gz(self, cleo_io: IO, poetry: Poetry) -> None:
        """
        Appends to sdist containing the annotations file and other necessary data.
        """
        dataset_directory: Path = Path(
            poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_DATASET_DIRECTORY, self.INPUT_DIR_DATASET)
        )
        reqstool_output_directory: Path = Path(
            poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL)
        )
        test_result_patterns: list[str] = (
            poetry.pyproject.data.get("tool", {}).get("reqstool", {}).get(self.CONFIG_TEST_RESULTS, [])
        )
        requirements_file: Path = Path(dataset_directory, self.INPUT_FILE_REQUIREMENTS_YML)
        svcs_file: Path = Path(dataset_directory, self.INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML)
        mvrs_file: Path = Path(dataset_directory, self.INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML)
        annotations_file: Path = Path(reqstool_output_directory, self.INPUT_FILE_ANNOTATIONS_YML)

        resources: dict[str, str] = {}

        if not os.path.exists(requirements_file):
            msg: str = f"[reqstool] missing mandatory {self.INPUT_FILE_REQUIREMENTS_YML}: {requirements_file}"
            raise RuntimeError(msg)

        resources["requirements"] = str(requirements_file)
        cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_YML}: {requirements_file}")

        if os.path.exists(svcs_file):
            resources["software_verification_cases"] = str(svcs_file)
            cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_YML}: {svcs_file}")

        if os.path.exists(mvrs_file):
            resources["manual_verification_results"] = str(mvrs_file)
            cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_YML}: {mvrs_file}")

        if os.path.exists(annotations_file):
            resources["annotations"] = str(annotations_file)
            cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_YML}: {annotations_file}")

        if test_result_patterns:
            resources["test_results"] = test_result_patterns
            cleo_io.write_line(
                f"[reqstool] added test_results to {self.OUTPUT_SDIST_REQSTOOL_YML}: {test_result_patterns}"
            )

        reqstool_yaml_data = {"language": "python", "build": "hatch", "resources": resources}

        yaml = YAML()
        yaml.default_flow_style = False
        reqstool_yml_io = io.BytesIO()
        reqstool_yml_io.write(f"{self.YAML_LANGUAGE_SERVER}\n".encode("utf-8"))
        reqstool_yml_io.write(f"# version: {poetry.package.version}\n".encode("utf-8"))

        cleo_io.write_line(f"[reqstool] reqstool config {reqstool_yaml_data}")

        yaml.dump(reqstool_yaml_data, reqstool_yml_io)
        reqstool_yml_io.seek(0)
        poetry.package.name
        # Path to the existing tar.gz file (constructed from metadata)
        original_tar_gz_file = os.path.join(
            str(poetry.package.root_dir),
            "dist",
            f"{normalize_package_name(poetry.package.name)}-{poetry.package.version}.tar.gz",
        )

        cleo_io.write_line(f"[reqstool] tarball: {original_tar_gz_file}")

        # Step 1: Extract the original tar.gz file to a temporary directory
        with tempfile.NamedTemporaryFile(delete=True) as temp_tar_file:

            temp_tar_file = temp_tar_file.name  # Get the name of the temporary file

            cleo_io.write_line(f"[reqstool] temporary tar file: {temp_tar_file}")

            # Extract the original tar.gz file
            with gzip.open(original_tar_gz_file, "rb") as f_in, open(temp_tar_file, "wb") as f_out:
                f_out.write(f_in.read())

            # Step 2: Open the extracted tar file and append the new file
            with tarfile.open(temp_tar_file, "a") as archive:
                file_info = tarfile.TarInfo(
                    name=f"{normalize_package_name(poetry.package.name)}-"
                    f"{poetry.package.version}/{self.OUTPUT_SDIST_REQSTOOL_YML}"
                )
                file_info.size = reqstool_yml_io.getbuffer().nbytes
                archive.addfile(tarinfo=file_info, fileobj=reqstool_yml_io)

            # Step 3: Recompress the updated tar file back into the original .tar.gz format
            with open(temp_tar_file, "rb") as f_in, gzip.open(original_tar_gz_file, "wb") as f_out:
                f_out.writelines(f_in)

        dist_dir: Path = Path(str(poetry.package.root_dir))
        cleo_io.write_line(
            f"[reqstool] added {self.OUTPUT_SDIST_REQSTOOL_YML} to "
            f"{os.path.relpath(original_tar_gz_file, dist_dir.parent)}"
        )


def get_version() -> str:
    try:
        ver: str = f"{version('reqstool-python-hatch-plugin')}"
    except PackageNotFoundError:
        ver: str = "package-not-found"

    return ver


def normalize_package_name(name: str) -> str:
    return name.lower().replace("-", "_")
