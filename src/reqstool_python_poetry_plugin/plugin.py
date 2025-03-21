# Copyright © LFV

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Dict, List, Union

from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND, TERMINATE
from cleo.events.event_dispatcher import EventDispatcher
from cleo.io.io import IO
from poetry.console.application import Application
from poetry.console.commands.build import BuildCommand
from poetry.console.commands.install import InstallCommand
from poetry.plugins.application_plugin import ApplicationPlugin
from poetry.poetry import Poetry
from reqstool_python_decorators.processors.decorator_processor import DecoratorProcessor
from ruamel.yaml import YAML


class ReqstoolPlugin(ApplicationPlugin):

    CONFIG_TOML_SOURCES = "sources"
    CONFIG_TOML_DATASET_DIRECTORY = "dataset_directory"
    CONFIG_TOML_OUTPUT_DIRECTORY = "output_directory"
    CONFIG_TOML_TEST_RESULTS = "test_results"

    INPUT_FILE_REQUIREMENTS_YML: str = "requirements.yml"
    INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML: str = "software_verification_cases.yml"
    INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML: str = "manual_verification_results.yml"
    INPUT_FILE_JUNIT_XML: str = "build/junit.xml"
    INPUT_FILE_ANNOTATIONS_YML: str = "annotations.yml"
    INPUT_DIR_DATASET: str = "reqstool"

    OUTPUT_DIR_REQSTOOL: str = "build/reqstool"
    OUTPUT_SDIST_REQSTOOL_CONFIG_YML: str = "reqstool_config.yml"

    ARCHIVE_OUTPUT_DIR_TEST_RESULTS: str = "test_results"

    YAML_LANGUAGE_SERVER = "# yaml-language-server: $schema=https://raw.githubusercontent.com/Luftfartsverket/reqstool-client/main/src/reqstool/resources/schemas/v1/reqstool_config.schema.json\n"  # noqa: E501

    def activate(self, application: Application) -> None:
        """
        Activate the plugin and access the Poetry and IO objects.
        """

        # Access the Poetry object from the Application
        self._poetry: Poetry = application.poetry

        # Access IO from the Application
        self._cleo_io: IO = application._io

        self._cleo_io.write_line(f"[reqstool] plugin {ReqstoolPlugin.get_version()} loaded")

        # Register an event listener for the command execution event
        application.event_dispatcher.add_listener(COMMAND, self._on_poetry_command)

        # Register an event listener for the command execution event
        application.event_dispatcher.add_listener(TERMINATE, self._on_build_terminate)

    def _on_poetry_command(self, event: ConsoleCommandEvent, event_name: str, dispatcher: EventDispatcher) -> None:
        # if build command
        if isinstance(event._command, BuildCommand):
            # self._update_sdist_include()
            self._create_annotations_file()
            self._generate_reqstool_config()
            self._cleo_io.write_line("")
        # if install command
        if isinstance(event._command, InstallCommand):
            self._update_sdist_include()
            self._cleanup_pyproject_install_after_install()

    def _on_build_terminate(self, event: ConsoleCommandEvent, event_name: str, dispatcher: EventDispatcher) -> None:
        # if build command finished
        if isinstance(event._command, BuildCommand):
            self._cleo_io.write_line("")
            self._cleanup_post_build()

    # clean up pyproject.toml, removing empty lines
    def _cleanup_post_build(self) -> None:
        reqstool_config_file: Path = self.get_reqstool_config_file(self._poetry)

        if reqstool_config_file.exists():
            reqstool_config_file.unlink()

        self._cleo_io.write_line("[reqstool] Cleaning up")

    def _cleanup_pyproject_install_after_install(self) -> None:
        pyproject_path: Path = self._poetry.file.path
        with open(pyproject_path, "r") as f:
            content = f.read()

        cleaned_content = re.sub(r"\n{3,}", "\n\n", content)

        with open(pyproject_path, "w") as f:
            f.write(cleaned_content)

    def _update_sdist_include(self) -> None:

        self._cleo_io.write_line("[reqstool] SDIST INCLUDE")

        # Access the 'tool.poetry' section, initializing it if necessary
        tool_section = self._poetry.pyproject.data.get("tool", {})
        poetry_section = tool_section.get("poetry", {})

        # Retrieve the current 'include' list or initialize it
        include_list: List[Dict[str, str]] = poetry_section.get("include", [])

        new_includes: List[Dict[str, str]] = []

        existing_paths: set = set()

        new_includes.append({"path": "reqstool_config.yml", "format": "sdist"})

        new_includes.append(
            {
                "path": str(
                    Path(
                        self._poetry.pyproject.data.get("tool", {})
                        .get("reqstool", {})
                        .get(self.CONFIG_TOML_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL),
                        self.INPUT_FILE_ANNOTATIONS_YML,
                    )
                ),
                "format": "sdist",
            }
        )

        new_includes.append(
            {
                "path": self._poetry.pyproject.data.get("tool", {})
                .get("reqstool", {})
                .get(self.CONFIG_TOML_DATASET_DIRECTORY, self.INPUT_DIR_DATASET),
                "format": "sdist",
            }
        )

        test_result_patterns: List[str] = (
            self._poetry.pyproject.data.get("tool", {}).get("reqstool", {}).get(self.CONFIG_TOML_TEST_RESULTS, [])
        )

        for test_result_pattern in test_result_patterns:
            new_includes.append({"path": test_result_pattern, "format": "sdist"})

        # get paths of existing includes
        for item in include_list:
            if isinstance(item, dict) and "path" in item:
                existing_paths.add(item["path"])
            elif isinstance(item, str):
                existing_paths.add(item)

        # append new includes if missing
        for item in new_includes:
            if item["path"] not in existing_paths:
                include_list.append(item)

        # Update the 'include' list in the 'poetry' section
        poetry_section["include"] = include_list
        tool_section["poetry"] = poetry_section
        self._poetry.pyproject.data["tool"] = tool_section

        print(f"self._poetry.pyproject.data[tool] {self._poetry.pyproject.data['tool']}")

        # Save changes to pyproject.toml
        self._poetry.pyproject.save()

        self._cleo_io.write_line("[reqstool] Updated tool.poetry.include with reqstool_config.yml")

    def _create_annotations_file(self) -> None:
        """
        Generates the annotations.yml file by processing the reqstool decorators.
        """
        sources = (
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_SOURCES, ["src", "tests"])
        )

        reqstool_output_directory: Path = Path(
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL)
        )
        annotations_file: Path = Path(reqstool_output_directory, self.INPUT_FILE_ANNOTATIONS_YML)

        decorator_processor = DecoratorProcessor()
        decorator_processor.process_decorated_data(path_to_python_files=sources, output_file=str(annotations_file))

    def _generate_reqstool_config(self) -> None:
        """
        Appends to sdist containing the annotations file and other necessary data.
        """
        dataset_directory: Path = Path(
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_DATASET_DIRECTORY, self.INPUT_DIR_DATASET)
        )
        reqstool_output_directory: Path = Path(
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL)
        )
        test_result_patterns: List[str] = [
            str(test_result_pattern)
            for test_result_pattern in self._poetry.pyproject.data.get("tool", {})
            .get("poetry", {})
            .get(self.CONFIG_TOML_TEST_RESULTS, [])
        ]

        requirements_file: Path = Path(dataset_directory, self.INPUT_FILE_REQUIREMENTS_YML)
        svcs_file: Path = Path(dataset_directory, self.INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML)
        mvrs_file: Path = Path(dataset_directory, self.INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML)
        annotations_file: Path = Path(reqstool_output_directory, self.INPUT_FILE_ANNOTATIONS_YML)

        resources: dict[str, Union[str, list[str]]] = {}

        if not requirements_file.exists():
            msg: str = f"[reqstool] missing mandatory {self.INPUT_FILE_REQUIREMENTS_YML}: {requirements_file}"
            raise RuntimeError(msg)

        resources["requirements"] = str(requirements_file)
        # self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {requirements_file}")

        if svcs_file.exists():
            resources["software_verification_cases"] = str(svcs_file)
            # self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {svcs_file}")

        if mvrs_file.exists():
            resources["manual_verification_results"] = str(mvrs_file)
            # self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {mvrs_file}")

        if annotations_file.exists():
            resources["annotations"] = str(annotations_file)
            # self._cleo_io.write_line(f"[reqstool] added to
            # {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {annotations_file}")

        if test_result_patterns:
            resources["test_results"] = test_result_patterns

        reqstool_yaml_data = {"language": "python", "build": "poetry", "resources": resources}
        yaml = YAML()
        yaml.default_flow_style = False

        # self._cleo_io.write_line(f"[reqstool] Final yaml data: {reqstool_yaml_data}")

        reqstool_config_file: Path = self.get_reqstool_config_file(self._poetry)

        # Write the file directly to the project root
        with open(reqstool_config_file, "w") as f:
            f.write(f"{self.YAML_LANGUAGE_SERVER}\n")
            f.write(f"# version: {self._poetry.package.version}\n")
            yaml.dump(reqstool_yaml_data, f)

        self._cleo_io.write_line(f"[reqstool] Generated {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}")

    def get_reqstool_config_file(self, poetry: Poetry) -> Path:
        reqstool_config_file = Path(str(poetry.package.root_dir)) / self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML

        return reqstool_config_file

    @staticmethod
    def get_version() -> str:
        try:
            ver: str = f"{version('reqstool-python-poetry-plugin')}"
        except PackageNotFoundError:
            ver: str = "package-not-found"

        return ver


def normalize_package_name(name: str) -> str:
    return name.lower().replace("-", "_")
