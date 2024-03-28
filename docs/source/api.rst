:orphan:

This file is not included in any toctree, but is recognized by ``autosummary`` which executes the following directive to generate all the stubs files for the code. The index.rst file then points to the top stub file.

The ``:orphan:`` metadata field at the beginning of this file tells Sphinx not to generate a warning is this file is not in any toctree.

.. autosummary::
   :recursive:
   :toctree: _autosummaries
   :template: custom-module-template.rst

	vhdl_sphinx_domain



.. project-module.rst.jinja2

