# VHDL-sphinx-domain


`vhdl-sphinx-domain` (VSD) is a [sphinx](https://www.sphinx-doc.org/) domain extension that can be used to create rich VHDL project documentation
by combining the flexibility of Sphinx with a VHDL parser in order to automatically extract as much documentation as possible
from the VHDL source code.

This extension uses the parser from the `vhdl-style-guide`  to extract the code structure and the comments comments from VHDL files,
and provides directives to insert the code information in the Sphinx RestrucuredText documents.

Features:
  - Extracts header comments and trailing comments and associates them with their elements
  - Automatically document entities, with their generic and port lists
  - Allow integrating any comment block in the VHDL source files, including markdown tables
  - Supports VHDL2008

## Documentation

Online documentation can be found in https://jfcliche.github.io/vhdl-sphinx-domain/

## Installation

The python package must be installed with
```shell
    pip install git+https://github.com/jfcliche/vhdl-sphinx-domain.git
```
The usage of this extension requires Python >= 3.6 and Sphinx >= 4.0.0.

## Usage

In your sphinx `conf.py` file add

```python
  extensions = ['vhdl_sphinx_domain']
```

## Repository maintainer

 - JF Cliche, vhdl@jfcliche.com


## Similar projects

 *  `sphinx-vhdl` (https://cesnet.github.io/sphinx-vhdl/):  provides directives to auto-document VHDL files.
 * `VHDLDomain` (https://cesnet.github.io/sphinx-vhdl/): Uses pyGHDL as a parser
