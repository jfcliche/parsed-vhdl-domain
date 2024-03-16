# parsed-vhdl-domain


`parsed-vhdl-domain` is a [sphinx](https://www.sphinx-doc.org/) domain extension that can be used to create rich VHDL project documentation
by combining the flexibility of Sphinx with a VHDL parser in order to automatically extract as much documentation as possible
from the VHDL source code.

This extension uses the parser from the `vhdl-style-guide`  to extract the code structure and the comments comments from VHDL files,
and provides directives to insert the code information in the Sphinx RestrucuredText documents.

Features:
  - Extracts header comments and trailing comments and associates them with their elements
  - Automatically document entities, with their generic and port lists
  - Allow integrating any comment block in the VHDL source files, including markdown tables
  - Supports VHDL2008


See also `sphinx-vhdl` which is also an independently created package that also provides directives to auto-document VHDL files.
(https://cesnet.github.io/sphinx-vhdl/)

## Usage

The python package must be installed with
```shell
######pip3 install sphinx-vhdl
```

The usage of this extension requires Python >= 3.6 and Sphinx >= 4.0.0.

## Configuration

In your sphinx `conf.py` file add

```python
extensions = ['parsed_vhdl_domain']
```

## Repository maintainer

 - JF Cliche, vhdl@jfcliche.com
