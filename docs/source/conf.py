# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
import vhdl_sphinx_domain

# sys.path.insert(0, os.path.abspath('../../'))


# -- Project information -----------------------------------------------------

project = 'vhdl-sphinx-domain'
author = 'JF Cliche'
version = vhdl_sphinx_domain.__version__
print(f'version is {vhdl_sphinx_domain.__version__}')
# import setuptools_scm
# print(f'SCM version is {setuptools_scm.get_version()}')

# -- General configuration ---------------------------------------------------

#
# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinxcontrib.restbuilder',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    # 'autoapi.extension',
    'sphinx.ext.napoleon',
    'vhdl_sphinx_domain'
]

vhdl_root = os.path.abspath('.')  # starting path to find VHDL files relative to this config file

autosummary_generate = True
autoclass_content = 'class'
add_module_names = False

# autoapi_dirs = ['../../vhdl_sphinx_domain']
# autoapi_type = "python"
# autoapi_python_class_content = 'both'
# autoapi_python_use_implicit_namespace = True
# autoapi_keep_files = True

vhdl_autodoc_source_path = 'doc/source'


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = []


language = 'en'


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'sphinx_rtd_theme'

html_theme_options = {
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4
}


# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
# html_static_path = ['_static']

# JFC: Added primary_domain so we can using vhdl directives and roles without having to specify them explicitely
# primary_domain = 'vhdl'

