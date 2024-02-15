
[![Commit Activity](https://img.shields.io/github/commit-activity/m/Luftfartsverket/reqstool-python-poetry-plugin?label=commits&style=for-the-badge)](https://github.com/Luftfartsverket/reqstool-python-poetry-plugin/pulse)
[![GitHub Issues](https://img.shields.io/github/issues/Luftfartsverket/reqstool-python-poetry-plugin?style=for-the-badge&logo=github)](https://github.com/Luftfartsverket/reqstool-python-poetry-plugin/issues)
[![License](https://img.shields.io/github/license/Luftfartsverket/reqstool-python-poetry-plugin?style=for-the-badge&logo=opensourceinitiative)](https://opensource.org/license/mit/)
[![Build](https://img.shields.io/github/actions/workflow/status/Luftfartsverket/reqstool-python-poetry-plugin/build.yml?style=for-the-badge&logo=github)](https://github.com/Luftfartsverket/reqstool-python-poetry-plugin/actions/workflows/build.yml)
[![Static Badge](https://img.shields.io/badge/Documentation-blue?style=for-the-badge&link=docs)](https://luftfartsverket.github.io/reqstool-python-poetry-plugin/reqstool-python-poetry-plugin/0.0.2/index.html)

# Reqstool Python Poetry Plugin

## Description

This provides a generic plugin for Poetry that runs during the build process.

What the plugin does is collect decorated code, formatting it and writing it to a yaml file saved to the `dist` folder, utilizing the `reqstool-decorators` package for the processing.



## Installation

### Plugin

The package name is `reqstool-poetry-plugin`.

* Using poetry:

```
$poetry add reqstool-poetry-plugin 
```

* pip install (unsure if working as intended):

```
$pip install reqstool-poetry-plugin
```

### Dependencies

#### reqstool-decorators

The plugin reads decorators available in the `reqstool-decorators` package.

```
$pip install reqstool-decorators
```

pyproject.toml

```
[tool.poetry.dependencies]
reqstool-decorators = "^0.1.5"
```

## Usage

### pyproject.toml

#### Paths

The plugin gets the paths where it will look for decorated code from ("." is filtered out):
```
[tool.pytest.ini_options]
pythonpath = [".", "src", "tests"]
```

So in this example all files in "src" and "tests", including subfolders, will be processed.

#### Poetry

This will be added when running `poetry add reqstool-poetry-plugin`

```
[tool.poetry.dependencies]
reqstool-poetry-plugin = "<version>"
```

### Decorators

Used to decorate your code as seen in the examples below, the decorator processing that runs during the build process collects data from the decorated code.

Import decorators:

```
from reqstool-decorators.decorators.decorators import Requirements, SVCs
```

Example usage of the decorators:

```
@Requirements(REQ_111, REQ_222)
def somefunction():
```

```
@SVCs(SVC_111, SVC_222)
def test_somefunction():
```

### Poetry build

When running `$poetry build` or `$poetry install` the plugin will run the `activate` function located inside `DecoratorsPlugin`, calling functions from the `reqstool-decorators` package and generate a yaml file in the `dist` folder containing formatted data on all decorated code found.



## License

This project is licensed under the MIT License - see the LICENSE.md file for details.
