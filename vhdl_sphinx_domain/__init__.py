""" VHDL Domain for Sphinx
"""
import os
from sphinx.util.fileutil import copy_asset_file
from docutils import nodes

# Try to get the version number from git first for in the case where we are working out of
# an editable install (-e), in which case the version file might be stale unless we manally
# reinstall periodically. If we are not in a git repo, which is the case when the installer moved the file in the package folder,
# use the version that is saved in the version file during install.
try:
    from setuptools_scm import get_version
    __version__ = get_version(root='..', relative_to=__file__)
except (ImportError, LookupError):
    try:
        from ._version  import version as __version__
    except (ImportError):
        raise RuntimeError('Cannot determine version')


css_file = 'vhdl.css'

def setup(app):
    """ Initializes this Sphinx extension.

    Parameters:

        app (Sphinx): Sphinx application object

    """
    from .vhdl_domain import VHDLDomain
    print('VHDLDomain: Setting up VHDL Domain')
    app.add_domain(VHDLDomain)
    # Add stylesheet filepath so it will be copied to the build folder
    # css_file = os.path.join(os.path.dirname(__file__),'vhdl.css')
    print(f'VHDLDomain: adding stylesheet {css_file}')
    app.add_css_file(css_file)
    app.connect('build-finished', add_css_files)
    app.connect('build-finished', add_nojekyll)
    app.connect('autodoc-process-docstring', autodoc_process_docstring)
    app.connect('builder-inited', builder_inited)
    app.connect('doctree-resolved', doctree_resolved)

    # get the VHDL source code root folder parameter from config file into the domain environment data
    app.add_config_value('vhdl_root', '', 'env')

def add_css_files(app, exc):
    """ Copy the assets from this package to the build folder.

    This function is an event handler meant to be registered through ``app.connect()``.

    Parameters:

        app (Sphinx): Sphinx application object

        exc: Exception

    Returns: result

    """
    if app.builder.format == 'html' and not exc:

        # Copy the VHDL style sheet
        css_pathfile = os.path.join(os.path.dirname(__file__), css_file)
        staticdir = os.path.join(app.builder.outdir, '_static')
        print(f'VHDLDomain: copying stylesheet {css_pathfile} to {staticdir}')
        copy_asset_file(css_pathfile, staticdir)



def builder_inited(app):

        ONLINE_SKIN_JS = "https://wavedrom.com/skins/default.js"
        ONLINE_WAVEDROM_JS = "https://wavedrom.com/wavedrom.min.js"

        app.add_js_file(ONLINE_SKIN_JS)
        app.add_js_file(ONLINE_WAVEDROM_JS)

def doctree_resolved(app, doctree, _fromdocname):
    """
    When the document, and all the links are fully resolved, we inject one
    raw html element for running the command for processing the wavedrom
    diagrams at the onload event.
    """
    text = """
    <script type="text/javascript">
        function init() {
            WaveDrom.ProcessAll();
        }
        window.onload = init;
    </script>"""
    doctree.append(nodes.raw(text=text, format='html'))


def add_nojekyll(app,exc):
    """ Create a ``.nojekyll`` file in the html root folder to prevent github pages from using jekyll
    to process the pages

    This function is an event handler meant to be registered through ``app.connect()``.

    Parameters:

        app (Sphinx): Sphinx application object

        exc: Exception

    Returns: result


    """
    with open(os.path.join(app.builder.outdir, '.nojekyll'), 'w') as f:
        pass

def autodoc_process_docstring(app, what, name, obj, options, lines):
    """ Adds a horizontal line at the end of of each  autodoc section to separate it from the members.
    """
    if lines:
        lines.append('')
        lines.append('.. raw:: html')
        lines.append('')
        lines.append('   <hr>')  # using '----' causes problems
        lines.append('')
    # if what=='class':
    #     print(f'{what} {name}, {obj}, {options=}')