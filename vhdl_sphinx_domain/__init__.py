"""
"""

import os
from sphinx.util.fileutil import copy_asset_file

css_file = 'vhdl.css'

def setup(app):
    from .vhdl_domain import VHDLDomain
    print('VHDLDomain: Setting up VHDL Domain')
    app.add_domain(VHDLDomain)
    # Add stylesheet filepath so it will be copied to the build folder
    # css_file = os.path.join(os.path.dirname(__file__),'vhdl.css')
    print(f'VHDLDomain: adding stylesheet {css_file}')
    app.add_css_file(css_file)
    app.connect('build-finished', copy_asset_files)

    # get the VHDL source code root folder parameter from config file into the domain environment data
    app.add_config_value('vhdl_root', '', 'env')

def copy_asset_files(app,exc):
    """ Copy the assets from this package to the build folder
    """
    if app.builder.format == 'html' and not exc:

        # Copy .nojekyll file in the html root folder to prevent github pages from using jekyll to prcess the pages
        nojekyll_pathfile = os.path.join(os.path.dirname(__file__), '.nojekyll')
        copy_asset_file(nojekyll_pathfile, app.builder.outdir)

        # Copy the VHDL style sheet
        css_pathfile = os.path.join(os.path.dirname(__file__), css_file)
        staticdir = os.path.join(app.builder.outdir, '_static')
        print(f'VHDLDomain: copying stylesheet {css_pathfile} to {staticdir}')
        copy_asset_file(css_pathfile, staticdir)


