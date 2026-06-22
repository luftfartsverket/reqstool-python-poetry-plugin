# Copyright © LFV

import re
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import tomlkit
from cleo.events.console_command_event import ConsoleCommandEvent
from cleo.events.console_events import COMMAND, TERMINATE
from cleo.events.console_terminate_event import ConsoleTerminateEvent
from poetry.console.application import Application
from poetry.console.commands.build import BuildCommand
from poetry.console.commands.install import InstallCommand
from poetry.plugins.application_plugin import ApplicationPlugin
from reqstool_python_decorators.decorators.decorators import Requirements
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

    YAML_LANGUAGE_SERVER = "# yaml-language-server: $schema=https://raw.githubusercontent.com/reqstool/reqstool-client/main/src/reqstool/resources/schemas/v1/reqstool_config.schema.json\n"  # noqa: E501

    def activate(self, application: Application) -> None:
        self._poetry = application.poetry
        self._cleo_io = application._io  # type: ignore[attr-defined]

        self._cleo_io.write_line(f"[reqstool] plugin version {self.get_version()}")

        application.event_dispatcher.add_listener(COMMAND, self._on_poetry_command)
        application.event_dispatcher.add_listener(TERMINATE, self._on_build_terminate)

    def _on_poetry_command(self, event: ConsoleCommandEvent, event_name: str, dispatcher) -> None:
        command = event.command
        if isinstance(command, BuildCommand):
            self._create_annotations_file()
            self._generate_reqstool_config()
        elif isinstance(command, InstallCommand):
            self._update_sdist_include()
            self._cleanup_pyproject_install_after_install()

    def _on_build_terminate(self, event: ConsoleTerminateEvent, event_name: str, dispatcher) -> None:
        command = event.command
        if isinstance(command, BuildCommand):
            self._cleanup_post_build()

    @Requirements("POETRY_PLUGIN_004")
    def _cleanup_post_build(self) -> None:
        """Deletes reqstool_config.yml from project root after build."""
        config_file = self.get_reqstool_config_file(self._poetry)
        if config_file.exists():
            config_file.unlink()
            self._cleo_io.write_line(f"[reqstool] Removed {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML} from project root")

    @Requirements("POETRY_PLUGIN_005")
    def _cleanup_pyproject_install_after_install(self) -> None:
        """Strips excess blank lines from pyproject.toml after install."""
        pyproject_path = Path(str(self._poetry.package.root_dir)) / "pyproject.toml"
        if not pyproject_path.exists():
            return
        content = pyproject_path.read_text()
        cleaned = re.sub(r"\n{3,}", "\n\n", content)
        if cleaned != content:
            pyproject_path.write_text(cleaned)
            self._cleo_io.write_line("[reqstool] Cleaned up excess blank lines in pyproject.toml")

    @Requirements("POETRY_PLUGIN_003")
    def _update_sdist_include(self) -> None:
        """Adds reqstool files to [tool.poetry.include] in pyproject.toml."""
        pyproject_path = Path(str(self._poetry.package.root_dir)) / "pyproject.toml"
        if not pyproject_path.exists():
            return

        dataset_directory: str = (
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_DATASET_DIRECTORY, self.INPUT_DIR_DATASET)
        )
        reqstool_output_directory: str = (
            self._poetry.pyproject.data.get("tool", {})
            .get("reqstool", {})
            .get(self.CONFIG_TOML_OUTPUT_DIRECTORY, self.OUTPUT_DIR_REQSTOOL)
        )

        entries_to_add = [
            self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML,
            f"{dataset_directory}/**/*",
            f"{reqstool_output_directory}/**/*",
        ]

        with open(pyproject_path) as f:
            data = tomlkit.load(f)

        tool_poetry = data.get("tool", {}).get("poetry", {})
        existing_includes: list = list(tool_poetry.get("include", []))

        added = []
        for entry in entries_to_add:
            if entry not in existing_includes:
                existing_includes.append(entry)
                added.append(entry)

        if added:
            tool_poetry["include"] = existing_includes
            with open(pyproject_path, "w") as f:
                tomlkit.dump(data, f)
            for entry in added:
                self._cleo_io.write_line(f"[reqstool] Added to pyproject.toml include: {entry}")

    def get_reqstool_config_file(self, poetry) -> Path:
        return Path(str(poetry.package.root_dir)) / self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML

    @Requirements("POETRY_PLUGIN_002")
    def _create_annotations_file(self) -> None:
        """Generates the annotations.yml file by processing the reqstool decorators."""
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

    @Requirements("POETRY_PLUGIN_001")
    def _generate_reqstool_config(self) -> None:
        """Generates reqstool_config.yml in the project root for inclusion in the sdist."""
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
        test_result_patterns: list[str] = (
            self._poetry.pyproject.data.get("tool", {}).get("reqstool", {}).get(self.CONFIG_TOML_TEST_RESULTS, [])
        )

        requirements_file: Path = Path(dataset_directory, self.INPUT_FILE_REQUIREMENTS_YML)
        svcs_file: Path = Path(dataset_directory, self.INPUT_FILE_SOFTWARE_VERIFICATION_CASES_YML)
        mvrs_file: Path = Path(dataset_directory, self.INPUT_FILE_MANUAL_VERIFICATION_RESULTS_YML)
        annotations_file: Path = Path(reqstool_output_directory, self.INPUT_FILE_ANNOTATIONS_YML)

        resources: dict[str, str | list[str]] = {}

        if not requirements_file.exists():
            msg: str = f"[reqstool] missing mandatory {self.INPUT_FILE_REQUIREMENTS_YML}: {requirements_file}"
            raise RuntimeError(msg)

        resources["requirements"] = str(requirements_file)
        self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {requirements_file}")

        if svcs_file.exists():
            resources["software_verification_cases"] = str(svcs_file)
            self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {svcs_file}")

        if mvrs_file.exists():
            resources["manual_verification_results"] = str(mvrs_file)
            self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {mvrs_file}")

        if annotations_file.exists():
            resources["annotations"] = str(annotations_file)
            self._cleo_io.write_line(f"[reqstool] added to {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML}: {annotations_file}")

        if test_result_patterns:
            patterns = [
                str(pattern)
                for pattern in (
                    [test_result_patterns] if isinstance(test_result_patterns, str) else test_result_patterns
                )
            ]
            resources["test_results"] = patterns

        reqstool_yaml_data = {"language": "python", "build": "poetry", "resources": resources}
        yaml = YAML()
        yaml.default_flow_style = False

        output_path = self.get_reqstool_config_file(self._poetry)

        with open(output_path, "w") as f:
            f.write(f"{self.YAML_LANGUAGE_SERVER}\n")
            f.write(f"# version: {self._poetry.package.version}\n")
            yaml.dump(reqstool_yaml_data, f)

        self._cleo_io.write_line(f"[reqstool] Created {self.OUTPUT_SDIST_REQSTOOL_CONFIG_YML} in project root")

    @staticmethod
    def get_version() -> str:
        try:
            ver: str = version("reqstool-python-poetry-plugin")
        except PackageNotFoundError:
            ver = "package-not-found"
        return ver
