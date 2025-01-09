# Copyright © LFV

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Union

from cleo.io.io import IO
from poetry.plugins.plugin import Plugin
from poetry.poetry import Poetry
from reqstool_python_decorators.processors.decorator_processor import DecoratorProcessor
from ruamel.yaml import YAML


class ReqstoolPlugin(Plugin):

    CONFIG_SOURCES = "sources"
    CONFIG_DATASET_DIRECTORY = "dataset_directory"
    CONFIG_OUTPUT_DIRECTORY = "output_directory"
    CONFIG_TEST_RESULTS = "test_results"

    INPUT_FILE_REQUIREMENTS_YML: str = "requirements.yml"
    INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML: str = "software_verification_cases.yml"
    INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML: str = "manual_verification_results.yml"
    INPUT_FILE_JUNIT_XML: str = "build/junit.xml"
    INPUT_FILE_ANNOTATIONS_YML: str = "annotations.yml"
    INPUT_DIR_DATASET: str = "reqstool"

    OUTPUT_DIR_REQSTOOL: str = "build/reqstool"
    OUTPUT_SDIST_REQSTOOL_YML: str = "reqstool_config.yml"

    ARCHIVE_OUTPUT_DIR_TEST_RESULTS: str = "test_results"

    YAML_LANGUAGE_SERVER = "# yaml-language-server: $schema=https://raw.githubusercontent.com/Luftfartsverket/reqstool-client/main/src/reqstool/resources/schemas/v1/reqstool_config.schema.json\n"  # noqa: E501

    def activate(self, poetry: Poetry, cleo_io: IO) -> None:
        self._poetry = poetry
        self._cleo_io = cleo_io

        self._create_annotations_file(poetry=poetry)
        self._generate_reqstool_config(cleo_io=self._cleo_io, poetry=self._poetry)

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

    def _generate_reqstool_config(self, cleo_io: IO, poetry: Poetry) -> None:
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

        resources: dict[str, Union[str, list[str]]] = {}

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
            patterns = [
                str(pattern)
                for pattern in (
                    [test_result_patterns] if isinstance(test_result_patterns, str) else test_result_patterns
                )
            ]
            resources["test_results"] = patterns  # Now this should work with the updated type hint

        reqstool_yaml_data = {"language": "python", "build": "poetry", "resources": resources}
        yaml = YAML()
        yaml.default_flow_style = False

        # Get the project root directory and create the output path
        output_path = Path(str(poetry.package.root_dir)) / self.OUTPUT_SDIST_REQSTOOL_YML

        cleo_io.write_line(f"[reqstool] Final yaml data: {reqstool_yaml_data}")

        # Write the file directly to the project root
        with open(output_path, "w") as f:
            f.write(f"{self.YAML_LANGUAGE_SERVER}\n")
            f.write(f"# version: {poetry.package.version}\n")
            yaml.dump(reqstool_yaml_data, f)

        cleo_io.write_line(f"[reqstool] Created {self.OUTPUT_SDIST_REQSTOOL_YML} in project root")


def get_version() -> str:
    try:
        ver: str = f"{version('reqstool-python-hatch-plugin')}"
    except PackageNotFoundError:
        ver: str = "package-not-found"

    return ver


def normalize_package_name(name: str) -> str:
    return name.lower().replace("-", "_")
