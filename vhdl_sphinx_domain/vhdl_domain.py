"""
Implements the Sphinx VHDL Domain and roles
"""

# System packages

import os

# Pypi packages

from docutils import nodes
from docutils.parsers.rst import directives
from docutils.utils.code_analyzer import LexerError

from sphinx.roles import XRefRole
from sphinx.domains import Domain, ObjType
from sphinx.directives import ObjectDescription
from sphinx.util.nodes import make_refnode

# Local packages

from .vhdl_parser import VHDLParser
from . import doc_utils


class VHDLDirective(ObjectDescription):  # which inherits from docutil's Directive
    """
    A generic directive that is to be used as a base class for directives documenting VHDL elements such as Entity, Architecture etc.
    This class offers:

    - x-ref directive registered with Sphinx.add_object_type().

    The following attributes are commonly used:

    - data (Object): The VHDLDomain associated data. Convenient shortcut for
      ``self.env.domaindata['vhdl']``. Initialized at instatiation. Must be picklable, as Sphinx
      saves it to disk for each processed file.

    - vhdl_parser (VHDLParser): Represent the VHDLDomain's VHDL parser object, which holds the
      results of all parsed files. Attribute initialized at instantiation.

    - name (str): full name of the directive (e.g. ``vhdl:autoentity``) (initialized by
      :meth:`run()`)

    - objtype (str): type of object being handled by the directive (entity, architecture etc),
      extracted from `name` (initialized by :meth:`run()`)

    - domain (str): name of the domain fir this directive. Extracted from `name`. (initialized by
      :meth:`run()`)
    """
    indextemplate = '%s; entity'
    # parse_node = None
    domain = 'vhdl'
    required_arguments = 1
    has_content = True


    def __init__(self, name, arguments, options, *args):
        """ Initializes the VHDL directive by creating the ``.data`` and ``.vhdl_parser`` attributes that point to the domain data nd parser respectively.

        Parameters:

            name (str): name of the directive
            argument (list): list of arguments following the directive
            options (dict): keyword options and values provided to the directive
            args (list): other arguments, passed to the class parent

        :meta no_show_inheritance:
        """

        super().__init__(name, arguments, options, *args)
        self.data = self.env.domaindata[VHDLDomain.name]
        self.vhdl_parser = self.env.domains[VHDLDomain.name].vhdl_parser
        self.verbose = 0

    def handle_signature(self, sig, signode):
        """Parse the signature `sig` into individual nodes and append them to
        `signode`.

        Parameters:

            sig (str): signature of the directive

            signode (list): list of nodes to which the signature should be added


        Returns:

            str: value that identifies the object, which will be passed to :meth:`add_target_and_index()`.
        """
        signode += nodes.paragraph('', f'{self.objtype.upper()} {sig}')
        if self.verbose:
            print(f'Processing signature {sig} into {signode}')
        return sig.lower()  # make all references lowercase so we we are not case sensitive


    def add_target_and_index(self, name, sig, signode):
        """
        Parameters:

            name : value that identifies the object. This is the value returned by handle_signature().

            sig (list): signatures (list of strings) obtained from get_signature().

            signode (list): signature node that we will be referring to

        Attributes used in this method:

        - self.objtype (str): the type of object (entity, architecture etc.) to be used to crate the entry in the cross reference table.
        - self.link_to_top (boolean): if true, the ling will point to the top of the page, otherwise it will point to this entry
        - self.domain (str): the current domain name (e.g. VHDL)
        - self.data['objects']: The cross_reference dictionary for this domain, indexed by (type,name), pointing to (document_name, target_name)
        """
        self.link_to_top = True
        if self.link_to_top:
            targetname = 'top'
        else:
            targetname = f'{self.objtype}-{name}'
            signode['ids'].append(targetname)
        self.state.document.note_explicit_target(signode)
        if self.indextemplate:
            colon = self.indextemplate.find(':')
            if colon != -1:
                indextype = self.indextemplate[:colon].strip()
                indexentry = self.indextemplate[colon+1:].strip() % (name,)
            else:
                indextype = 'single'
                indexentry = self.indextemplate % (name,)
            self.indexnode['entries'].append((indextype, indexentry,
                                              targetname, '', None)) # Added 5th element for Sphinx 1.8
        objects = self.data['objects']
        if self.verbose:
            print(f'VHDL Domain: add_target_and_index: adding object type {self.objtype} named {name}, docname={self.env.docname}, targetname={targetname}')
        objects[self.objtype, name] = self.env.docname, targetname


    def run(self):
        """ Process the directive.

        We update the name of the object by removing the `auto` prefix, run the parent :py:meth:`run()` method,  and then
        add additional contents provided by :py:meth:`add_contents()`.

            Attributes used in this method:

        - name (str): full name of the directive, with domain prefix (e.g. ``vhdl:autoentity``)
        """
        # Remove a leading `auto` from the directive name to get the real type
        self.name = self.name.replace(':auto',':')
        nodes = super().run()
        n = self.add_contents()  # use self.names to know the names of objects
        return nodes + n

    def add_contents(self):
        """ Appends content nodes to the directive output. To be overriden by the object-specific directive.

        This is `VHDLDirective`-specific method.


        Returns:

            list: list of docutils nodes to be appended to the output of `run()`.
        """
        return []


class VHDLIncludeDirective(VHDLDirective):
    """ Includes a specified range of VHDL comment lines in this document as restructuredText or MarkDown

    Directive argument: The entity name in which file the comment lines will searched and extracted from

    Directive options:

    - start_before (str): start including text from the comment line containing the specified string
    - start_after (str): start including text from the comment line following the line containing the specified string
    - start_before (str): stop including text before the comment line contining the specified string
    - start_after (str): stop including text on the comment line contining the specified string

    Example::

        ..vhdl:include:: GPIO
            :start-after: Memory Map

    """
    required_arguments = 1
    has_content = False
    option_spec = {
        'start-before': lambda x: x,
        'start-after': lambda x: x,
        'end-before': lambda x: x,
        'end-after': lambda x: x,
    }

    def __init__(self, name, arguments, options, *args):
        """ Create and initialize a directive object instance.

        Parameters:

            name (str): name of the directive

            arguments (str): arguments passed after the directive (i.e. the signature, ``<directive_name>: <arguments>``)

            options (dict): options passed to the directive (i.e. ``:<option_name>: <option_value>``)

            *args: All other options passed to the parent's __init__
        """
        super().__init__(name, arguments, options, *args)
        self.verbose = 0

        if self.verbose:
            print(f'Creating directive object named {self.name}, arg={self.arguments}, opt={self.options}')
        # Store the arguments and options specified with the directive. Those will be used by run()
        self.entity = arguments[0] # file name
        self.search_params = dict(
            start_before = options.get('start-before', None),
            start_after = options.get('start-after', None),
            end_before = options.get('end-before', None),
            end_after = options.get('end-after', None))

    def run(self):
        if self.verbose:
            print(f'Running vhdl:include with domain = {self.domain}, data={self.env.domains}')
        # parser = self.env.domaindata[VHDLDomain.name]['parser']
        lines = self.vhdl_parser.get_comments(self.entity, **self.search_params)
        if not lines:
            raise RuntimeError(f'Did not find any comment matching the search criteria in {self.entity}')
        # print(f'** Inserting comment block for entity {self.entity}')
        # print('\n'.join(lines))
        # print('******* End of comment clock *****')
        return doc_utils.parse_comment_block(self.state, lines)

class VHDLParseDirective(VHDLDirective):
    """ Loads and parse the specified VHDL file.

    The parse results are stored in the `vhdl_parser` object for reference by other directives.

    Directive arguments: vhdl_file_name

    Directive options: None
    """
    required_arguments = 1
    has_content = False

    def __init__(self, name, arguments, options, *args):
        """ Initialize the directive by extracting the directive argument.
        """
        super().__init__(name, arguments, options, *args)

        # Store the full filename of the VHDL file given as a directive argument by prepending the
        # root VHDL folder found in the config file. This will be used in `run()`.
        vhdl_root_folder = self.config.vhdl_root
        self.vhdl_filename = os.path.join(vhdl_root_folder, arguments[0])

    def run(self):
        """ Executes the directive by parsing the specified filename and storing the result in the domain's parser object for future references.

        Returns:
            list: list of nodes to add to the document. In this case, this is an empty list.
        """
        # print(f'state={dir(self.state.document)}')
        # parser = self.env.domaindata[VHDLDomain.name]['parser']
        self.vhdl_parser.parse_file(self.vhdl_filename)
        return []


class VHDLEntityDirective(VHDLDirective):
    """ Insert the entity brief description, generics/ports table and long description

        Directive arguments: vhdl_entity_name

        Directive options: None
    """
    def add_contents(self):
        """ Adds the entity's short description, generics and port interface table, and long description nodes to the directive's output

        Returns:
            list: list of nodes to add
        """
        entity_name = self.names[0]  # value returned by handle_signature
        # parser = self.env.domaindata[VHDLDomain.name]['parser']
        # parser = self.env.domaindata[VHDLDomain.name]['parser']
        entity = self.vhdl_parser.get_entity(entity_name)
        brief_nodes = doc_utils.parse_comment_block(self.state, entity.brief, class_dict=dict(section='vhdl_entity_brief'))
        details_nodes = doc_utils.parse_comment_block(self.state, entity.details, class_dict=dict(section='vhdl_entity_details'))
        table_node = doc_utils.make_vhdl_entity_table(generics=entity.generics, ports=entity.ports)
        for n in brief_nodes + [table_node] + details_nodes:
            if '----' in n.astext():
                # print(n.astext(), end='')
                print(f'----------------Separator detected!----------------')
        return brief_nodes + [table_node] + details_nodes


class VHDLXRefRole(XRefRole):
    """ VHDL cross-reference role
    """
    pass

def vhdl_code_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    """ Define the ``vhdl`` role, which inserts the specified raw text as a literal block of text color-highlighted with Pygments for the VHDL syntax.

    Parameters:
        role: *unused*
        rawtext (str): raw text of the role
        text: text between the backticks
        lineno:
        inliner:
        options (dict):
        content (list):

    Returns:
        tuple: a (node_list, error_message_list) tuple
    """
    try:
        node = doc_utils.make_lexed_vhdl_node(text)
        return [node], []
    except LexerError as error:
        msg = inliner.reporter.warning(error)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]

vhdl_code_role.options = {'class': directives.class_option,
                     'language': directives.unchanged}

class VHDLDomain(Domain):
    """Class defining the VHDL Domain. Instance of this class holds the domain state, including the VHDLParser instance.
    """

    name = 'vhdl'
    label = 'VHDL'

    object_types = {
        'entity': ObjType('entity', 'entity'), # ObjType(type_name, role_name1, role_name 2..., attr1=value1, ...)
        'target': ObjType('target', 'target')
        }

    directives = {
         'autoentity': VHDLEntityDirective,
         'include-docs': VHDLIncludeDirective,
         'parse': VHDLParseDirective, # Includes a specified range of VHDL comment lines in this document as restructuredText or MarkDown ,
    }

    roles = {
        'entity': VHDLXRefRole(lowercase=True),
        'vhdl': vhdl_code_role,
    }

    initial_data = {
        'objects': {},      # (type, name) -> docname, labelid
        'parser' : None  # VHDL parser instance
    }

    dangling_warnings = {
    }


    def __init__(self, env):
        """ Create the VHDL domain instance, including a VHDLParser instance.

        Parameters:

            env (sphinx.BuildEnvironment): instance of the build environment object that will hold the list of objects created by this domain.

        """
        super().__init__(env)
        self.verbose = 0
        # self.data['parser'] = VHDLParser()

        # we create an instance of the parser within this domain instance.
        # In the directives, we access through the BuildEnvironment object as end.domains['vhdl].parser
        # We tried to put it in the data, but that gets pickled, and the pickle cannot digest the parser object.
        self.vhdl_parser = VHDLParser()
        if self.verbose:
            print(f'Created VHDL parser instance for domain {self.name} in environment {env}')

    def clear_doc(self, docname, verbose=0):

        if verbose:
            print(f'Clearing {self.name} domain data for docname={docname}')
        if 'objects' in self.data:
            for key, (fn, _) in list(self.data['objects'].items()):
                if fn == docname:
                    del self.data['objects'][key]

    def resolve_xref(self, env, fromdocname, builder,
                     typ, target, node, contnode):
        """
        """

        objects = self.data['objects']  # same as env.domaindata['vhdl']['objects']
        objtypes = self.objtypes_for_role(typ) or []
        # print '*** trying to resolve objtype', objtypes, 'typ=', typ, 'target=', target
        # print '*** Entries are:', self.data['objects']
        # print '***domaindata = ', env.domaindata['vhdl']
        for objtype in objtypes:
            if (objtype, target) in self.data['objects']:
                docname, labelid = self.data['objects'][objtype, target]
                break
        else:
            docname, labelid = '', ''
        if not docname:
            return None
        # print('resolve_xref:', contnode)
        new_contnode = nodes.strong('','', contnode)
        new_refnode = make_refnode(builder, fromdocname, docname,
                            labelid, new_contnode)
        # print('resolve_xref new refnode:', new_refnode)
        return new_refnode

    def get_objects(self):
        for (type, name), info in self.data['objects'].items():
            yield (name, name, type, info[0], info[1],
                   self.object_types[type].attrs['searchprio'])

    def get_type_name(self, type, primary=False):
        # never prepend "Default"
        return type.lname



