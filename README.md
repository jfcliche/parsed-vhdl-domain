# VHDL-sphinx-domain


`vhdl-sphinx-domain` (VSD) is a [Sphinx](https://www.sphinx-doc.org/) domain extension that can be
used to create rich VHDL project documentation by combining the flexibility of the Sphinx
documentation system with a VHDL parser that can automatically extract the structure and
documentation from the VHDL source code.

Features:

  - Extracts header comments and trailing comments and associates them with their elements
  - Automatically document entities, with their generic and port lists
  - Allow integrating any comment block in the VHDL source files, including markdown tables
  - Supports VHDL2008

## Documentation

Online documentation can be found at https://jfcliche.github.io/vhdl-sphinx-domain/


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

## Similar projects

 *  `sphinx-vhdl` (https://cesnet.github.io/sphinx-vhdl/):  provides directives to auto-document VHDL files.
 * `VHDLDomain` (https://cesnet.github.io/sphinx-vhdl/): Uses pyGHDL as a parser
