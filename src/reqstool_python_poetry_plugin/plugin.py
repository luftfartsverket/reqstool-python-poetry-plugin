# Copyright © LFV


from cleo.io.io import IO
from poetry.plugins.plugin import Plugin
from poetry.poetry import Poetry
from reqstool_python_decorators.processors.decorator_processor import DecoratorProcessor


class DecoratorsPlugin(Plugin):
    def activate(self, poetry: Poetry, io: IO):
        io.write_line("INSIDE ACTIVATE IN DECORATORSPLUGIN")

        pythonpath_from_pyproject_toml = (
            poetry.pyproject.data.get("tool").get("pytest").get("ini_options").get("pythonpath")
        )

        filtered_pythonpaths = [path for path in pythonpath_from_pyproject_toml if path != "."]

        generate_yaml_from_process_decorator(paths=filtered_pythonpaths)


def generate_yaml_from_process_decorator(paths):
    process_decorator = DecoratorProcessor()
    process_decorator.process_decorated_data(path_to_python_files=paths)
