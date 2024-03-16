"""
VHDLDomain Sphinx class implementation

"""
import os

from docutils import nodes, utils
from docutils.parsers.rst import directives
from docutils.utils.code_analyzer import Lexer, LexerError
from docutils.statemachine import ViewList

from sphinx import addnodes
from sphinx.roles import XRefRole
# from sphinx.locale import l_, _
from sphinx.domains import Domain, ObjType
from sphinx.domains.std import Target
from sphinx.directives import ObjectDescription
from sphinx.util import ws_re
from sphinx.util.nodes import clean_astext, make_refnode, nested_parse_with_titles
from sphinx.util.docfields import Field, GroupedField, TypedField

from .vhdl_parser import VHDLFiles

__version__ = '1.0'



class VHDLObjectDirectiveBase(ObjectDescription):  # which inherits from docutil's Directive
    """
    A generic directive that is to be used as a base class for directives documenting VHDL elements such as Entity. Architecture etc.
    This class offers:

        - x-ref directive registered with Sphinx.add_object_type().

    Usage:
        DomainObject = type('DomainObject', (GenericObject, object), dict(
            domain = 'my-domain-name'))

        DomainObject = type('DomainObject', (GenericObject, object), dict(
            domain = 'my-domain-name', indextemplate=(

        class MyDescriptionObject(GenericObject):

    """
    indextemplate = '%s; entity'
    # parse_node = None
    domain = 'vhdl'
    required_arguments = 1
    has_content = True

    def get_signatures(self):
        """
        Retrieve the signatures to document from the directive arguments.  By
        default, signatures are given as arguments, one per line.

        Returns a list of signatures
        """
        return self.arguments

    def handle_signature(self, sig, signode):
        signode += nodes.paragraph('', '%s %s' % (self.objtype.upper(), sig))
        return sig.lower()  # make all references lowercase so we we are not case sensitive


    def add_target_and_index(self, name, sig, signode):
        """
        Arguments:
            name : value returned by handle_signature()
            sig: signature item obtained from get_signature()
            signode: signature node being populated
        References:
            self.objtype (str): the type of object (entity, architecture etc.) to be used to crate the entry in the cross reference table.
            self.link_to_top (boolean): if true, the ling will point to the top of the page, otherwise it will point to this entry
            self.domain (str): the current domain name (e.g. VHDL)
            self.env.domaindata[self.domain]['objects']: The cross_reference dictionary for this domain, indexed by (type,name), pointing to (document_name, target_name)
        """
        self.link_to_top = True
        if self.link_to_top:
            targetname = 'top'
        else:
            targetname = '%s-%s' % (self.objtype, name)
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
        objects = self.env.domaindata[self.domain]['objects']
        print(('VHDL Domain: add_target_and_index: adding', self.objtype, name, self.env.docname, targetname))
        objects[self.objtype, name] = self.env.docname, targetname

    def run(self):
        # Extract the domain name (e.g. VHDL) and the object type from the complete directive name
        if ':' in self.name:
            self.domain, self.objtype = self.name.split(':', 1)
        else:
            self.domain, self.objtype = '', self.name
        # Remove a leading `auto` from the directive name to get the real type
        if self.objtype.startswith('auto'):
            self.objtype = self.objtype[4:]

        # print dir(self.state.document.settings.env)
        # self.env = self.state.document.settings.env  # now included in SphinxDirective since 1.8.0
        self.indexnode = addnodes.index(entries=[])

        # Create a container node desc() to contain the whole contents of this directive.
        # This node has no text by itself. All the text is contained by children.
        node = addnodes.desc()
        node.document = self.state.document
        node['domain'] = self.domain
        # 'desctype' is a backwards compatible attribute
        node['objtype'] = node['desctype'] = self.objtype
        node['noindex'] = noindex = ('noindex' in self.options)

        self.names = []
        for sig in self.get_signatures():
            # add a signature node for each signature in the current unit
            # and add a reference target for it
            signode = addnodes.desc_signature(sig, '', classes=['vhdl_entity_title'])
            signode['first'] = False
            node.append(signode)
            try:
                # name can also be a tuple, e.g. (classname, objname);
                # this is strictly domain-specific (i.e. no assumptions may
                # be made in this base class)
                name = self.handle_signature(sig, signode) # populate the signature node, and return the name used to refer to it
            except ValueError:
                # signature parsing failed
                signode.clear()
                signode += addnodes.desc_name(sig, sig)
                continue  # we don't want an index entry here
            if name not in self.names:
                self.names.append(name)
                if not noindex:
                    # only add target and index entry if this is the first
                    # description of the object with this name in this desc block
                    self.add_target_and_index(name, sig, signode)

        contentnode = addnodes.desc_content()
        node.append(contentnode)
        # if self.names:
        #     # needed for association of version{added,changed} directives
        #     self.env.temp_data['object'] = self.names[0]
        # self.before_content()
        # self.state.nested_parse(self.content, self.content_offset, contentnode)
        # DocFieldTransformer(self).transform_all(contentnode)
        # self.env.temp_data['object'] = None
        # self.after_content()
        n = self.add_contents(contentnode)  # use self.names to know the names of objects
        return [self.indexnode, node] + n

    def add_contents(self, contentnode):
        """ Add the contents to the directive output. To be overriden by the object-specific directive"""
        return []


class VHDLIncludeDirective(ObjectDescription):
    """ Includes a specified range of VHDL comment lines in this document as restructuredText or MarkDown

    Parameters:

        start_before (str): start including text from the comment line containing the specified string
        start_after (str): start including text from the comment line following the line containing the specified string
        start_before (str): stop including text before the comment line contining the specified string
        start_after (str): stop including text on the comment line contining the specified string

    ..VHDL:include: entity_name

    """
    required_arguments = 1
    has_content = False
    option_spec = {
        'start-before': lambda x: x,
        'start-after': lambda x: x,
        'end-before': lambda x: x,
        'end-after': lambda x: x,
    }

    def __init__(self,
                 directive,
                 arguments,  # arguments passed after the directive
                 options, # Additional keyword arguments
                 content, #
                 lineno,            # ignored
                 content_offset,    # ignored
                 block_text,        # ignored
                 state,
                 state_machine,     # ignored
                ):

        self.entity = arguments[0] # file name
        self.search_params = dict(
            start_before = options.get('start-before', None),
            start_after = options.get('start-after', None),
            end_before = options.get('end-before', None),
            end_after = options.get('end-after', None))
        self.state = state

    def run(self):

        lines = vhdl_parser.get_comments(self.entity, **self.search_params)
        if not lines:
            raise RuntimeError(f'Did not find any comment matching the search criteria in {self.entity}')
        return parse_comment_block(self.state, lines)

class VHDLParseDirective(ObjectDescription):
    """ Loads and parse the specified VHDL file.
    The parse results are stored in the `vhdl_parser` object for reference by other directives.
    """
    required_arguments = 1
    has_content = False

    def __init__(self, directive, arguments, options, content, lineno, content_offset, block_text,
                 state, state_machine):

        env = state.document.settings.env
        vhdl_root_folder = env.config.vhdl_root
        self.vhdl_filename = os.path.join(vhdl_root_folder, arguments[0])

    def run(self):
        vhdl_parser.parse_file(self.vhdl_filename)
        return []

def parse_rest(state, lines, class_dict={}):
    """ Parse a list of lines into a list of docutil nodes.
    Nodes are not part of a top object so sections found in the parsed text can be mede part of the parent hierarchy.
    User-specified classes can be applied to objects specified in `class_dict`.

    Parameters:

        state:

        lines (list of str): text to be parsed

        class_dict (dict): Dict in the format {object_type:class_name,...} or {object_type:[class_name, class_name...],...} that applies the specified ``class_name`` to the objects generated by the REST parser that have the tag ``object_type``

    Returns:
        - A list containing docutil nodes

    """
    if not lines: return []
    container_node = nodes.paragraph('','')
    nested_parse_with_titles(state, ViewList(lines, source=''), container_node)
    for n in container_node:
        if n.tagname in class_dict:
            # print '*** Updating class on object:', n.tagname
            if isinstance(class_dict[n.tagname], str):
                n['classes'].append(class_dict[n.tagname])
            else:
                n['classes'].extend(class_dict[n.tagname])
    return list(container_node)


def parse_markdown_table(state, rows, pos):
    """ Attempts to decode a block of text as a markdown table

    Returns:

        (tuple or None):
            (new position, docutils_table_node) if a markdown table was found
            `None` if there is no markdown table at this location.
    """

    # Define some helper functions first
    def split_row(rows, pos):
        if pos >= len(rows):
            return []
        e = [s.strip() for s in rows[pos].strip().split('|')]
        if len(e) < 2:
            return []
        if not e[0]:
            del e[0]
        if not e[-1]:
            del e[-1]
        return e

    def build_row(entries, alignment):
        # return nodes.row('', *[nodes.entry('', nodes.inline('', e)) for e in entries])
        node_list = []
        for i, e in enumerate(entries):
            n = parse_rest(state, [e])
            # print '********** Element node = ', n
            entry = nodes.entry('', *n)
            if i < len(alignment) and alignment[i]:
                entry['classes'].append(alignment[i])
            node_list.append(entry)
        return nodes.row('', *node_list)

    def max_column_widths(*rows):
        widths = [0] * max(len(r) for r in rows)
        for row in rows:
            for i, entry in enumerate(row):
                widths[i] = max(widths[i], len(entry))
        return widths

    # Parsing starts here
    # print 'parsing Markdown table'
    if rows[pos].strip().startswith('---'):  # if we have a top fence, skip it
        pos += 1
    headers = split_row(rows, pos)  # attempt to decode the header row
    if not headers:
        return # if unsuccessful, this is not a markdown table
    # print 'header=', headers
    pos += 1
    separators = split_row(rows, pos)
    if not separators:
        return  # bad separators = not a markdown table = give up
    # print 'separator=', separators
    pos += 1
    row_entries = []
    while pos < len(rows):
        entries = split_row(rows, pos)
        # print 'row=', entries
        if not entries:
            break
        row_entries.append(entries)
        pos += 1
    if not row_entries: return # no rows? give up, not a markdon table
    print(('We have %i header columns, %i separator coulmns, %s row columns' % (len(headers), len(separators), ','.join('%i' % len(r) for r in row_entries))))
    widths = max_column_widths(headers, separators, *row_entries)
    cols = len(widths)

    # print '*** widths=', widths

    table = nodes.table()
    tgroup = nodes.tgroup('', cols=cols)
    table += tgroup

    align = []
    for i, sep in enumerate(separators):
        if sep.startswith(':') and sep.endswith(':'):
            align.append('align-center')
        elif sep.startswith(':'):
            align.append('align-left')
        elif sep.endswith(':'):
            align.append('align-right')
        else:
            align.append(None)
        tgroup += nodes.colspec(colwidth=widths[i])

    thead = nodes.thead()
    tgroup += thead

    tbody = nodes.tbody()
    tgroup += tbody
    # print '*********** building table header'
    assert len(headers) == cols, 'Headers has invalid number of columns. We expected %i columns, but got got headers: %s' % (cols, ','.join(headers))
    thead += build_row(headers, align)
    for r in row_entries:
        assert len(r) == cols, 'Row has invalid number of columns'
        tbody += build_row(r, align)
    return pos, table

def parse_comment_block(state, lines, class_dict={}):
    """ Parse a block of ReStructuredText text potentially containing Markdown tables into a node list.

    Arguments:
        - state: parser state to be passed to the REST parser
        - lines (list of str): text to be parsed
        - class_dict (dict): classes to be applied to the REST blocks

    Returns:
        - Docutils node list
    """
    pos = 0
    rest_lines = []
    node_list =[]

    while pos < len(lines):
        markdown_table = parse_markdown_table(state, lines, pos)
        # print '*** Markdown table=', markdown_table
        if markdown_table:
            print('VHDL Domain: A Markdown table was detected, parsed and added')
            node_list += parse_rest(state, rest_lines, class_dict)
            rest_lines = []
            (next_pos, table_node) = markdown_table
            # print 'Markdown table nodes = ', table_node
            node_list.append(table_node)
            pos = next_pos
        else:
            rest_lines.append(lines[pos])
            pos += 1

    node_list += parse_rest(state, rest_lines, class_dict)
    return node_list


def make_vhdl_entity_table(generics, ports):
        """ Create a table that describes the ports and generics of a VHDL entity.

        Returns:

            a Docutils table.

        Notes:

            The table is structured as follows:

                table
                    -tgroup
                        -colspec
                        (-thead)
                        (   -row)
                        (       -entry)
                        -tbody
                            -row
                                -entry
                                -entry
                                -...
                            -row
                            -...
        """
        COLS = 2
        table = nodes.table(classes=['vhdl_entity'])
        colspec_nodes = [nodes.colspec(colwidth=0)]*(COLS-1) + [nodes.colspec(colwidth=1)]
        tgroup = nodes.tgroup('', *colspec_nodes, cols=len(colspec_nodes))
        table += tgroup
        tbody = nodes.tbody()
        tgroup += tbody

        def add_header(name, tbody=tbody):
            tbody += nodes.row('', nodes.entry('', nodes.paragraph('','', nodes.Text(name)), morecols=COLS-1), classes=['vhdl_entity_header'])

        def add_rows(interface_elements, tbody=tbody):
            """ Add a port/generic entries to `tbody` """
            for i, interface in enumerate(interface_elements):
                identifier = ','.join(interface.names)
                definition = interface.definition
                comments = interface.comments
                def_row_class = ('vhdl_entity_def_even', 'vhdl_entity_def_odd')[i & 1]
                comments_node = nodes.inline('',comments)
                # print repr(identifier), bool(identifier)
                if not identifier:  # if just a section separating comment
                    tbody += nodes.row('',
                        nodes.entry('', comments_node, morecols=1, classes=['vhdl_entity_sep']),
                        # nodes.entry(''), #
                        classes=[def_row_class])
                else: # if an actual port definition
                    identifier_node = make_lexed_vhdl_node(identifier + ':')
                    definition_node = make_lexed_vhdl_node(definition)
                    tbody += nodes.row('',
                        nodes.entry('', identifier_node, classes=['vhdl_entity_id']), #
                        nodes.entry('', definition_node, comments_node, classes=['vhdl_entity_def']), classes=[def_row_class])

        # print generics
        if generics:
            add_header('GENERICS')
            add_rows(generics)
            # print(f'Adding generics {generics}')
        if ports:
            add_header('PORTS')
            add_rows(ports)
        return table

class VHDLEntityDirective(VHDLObjectDirectiveBase):
    """ Insert the entity brief description, generics/ports table and long description"""
    def add_contents(self, node):
        entity_name = self.names[0]  # value returned by handle_signature
        entity = vhdl_parser.get_entity(entity_name)
        brief_nodes = parse_comment_block(self.state, entity.brief, class_dict=dict(section='vhdl_entity_brief'))
        details_nodes = parse_comment_block(self.state, entity.details, class_dict=dict(section='vhdl_entity_details'))
        table_node = make_vhdl_entity_table(generics=entity.generics, ports=entity.ports)
        return brief_nodes + [table_node] + details_nodes


class Test(ObjectDescription):
    """
    """
    required_arguments = 0
    has_content = True

    def build_table_from_list(self, table_data, col_widths, header_rows, stub_columns):
        table = nodes.table()
        tgroup = nodes.tgroup(cols=len(col_widths))
        table += tgroup
        for col_width in col_widths:
            colspec = nodes.colspec(colwidth=col_width)
            if stub_columns:
                colspec.attributes['stub'] = 1
                stub_columns -= 1
            tgroup += colspec
        rows = []
        for row in table_data:
            row_node = nodes.row()
            for cell in row:
                entry = nodes.entry()
                # cell = [nodes.paragraph(nodes.Text(str(cell)))]
                # cell = nodes.paragraph(str(cell), str(cell))
                # print 'cell is', cell
                # entry += nodes.paragraph(nodes.Text(str(cell)))
                entry += cell
                row_node += entry
            rows.append(row_node)
        if header_rows:
            thead = nodes.thead()
            thead.extend(rows[:header_rows])
            tgroup += thead
        tbody = nodes.tbody()
        tbody.extend(rows[header_rows:])
        tgroup += tbody
        return table

    def run(self):

        return [make_vhdl_entity_table([('adc_data_h_p', 'in std_logic_vector(7 downto 0)', 'long comment that dlkj sa salks l ask jdljsa lsdk jalsdkjsad sald sdlsdjs lkas als sakjsljsalj asld asldjas dljsad lsa dlsa djsa fdsiad f sa asof jsda fas fosa dfosa f saf saf dsao f ;asfd saod jfsa fd isadfi dsaof osa jfddsa f dsa ddsf oodsai osafd osadjf saofdj osa jfddlsa jd'), ('de', 'la', 'terre')], [('x','y','z')])]
        node = nodes.Element()          # anonymous container for parsing
        self.state.nested_parse(self.content, self.content_offset, node)
        table_data = [[item.children for item in row_list[0]]
                          for row_list in node[0]]
        # print repr(table_data)
        # table_data = [[1,2,3],[4,5,6]]
        table_node = self.build_table_from_list(table_data, [0, 0, .1], 0, False)
        table_node['classes'] += ['tab']
        self.add_name(table_node)


        return [table_node]

class VHDLXRefRole(XRefRole):
    pass


def make_lexed_vhdl_node(text, classes = ['highlight', 'highlight-vhdl'], options={}):
    tokens = Lexer(utils.unescape(text, 1), language='vhdl', tokennames='short')  # use 'short' object names so the Sphinx highlighting CSS rules will be found
    node = nodes.literal('', '', classes=classes)  # <code> element

    # analyze content and add nodes for every token
    for pygment_classes, value in tokens:
        node += nodes.inline(value, value, classes=pygment_classes)  # <span> element
    return node

def vhdl_code_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    try:
        node = make_lexed_vhdl_node(text)
        return [node], []
    except LexerError as error:
        msg = inliner.reporter.warning(error)
        prb = inliner.problematic(rawtext, rawtext, msg)
        return [prb], [msg]

vhdl_code_role.options = {'class': directives.class_option,
                     'language': directives.unchanged}

# register_canonical_role('code', code_role)

vhdl_parser = VHDLFiles()

class VHDLDomain(Domain):
    """
    Domain for all objects that don't fit into another domain or are added
    via the application interface.
    """

    name = 'vhdl'
    label = 'VHDL'


    object_types = {
        'entity': ObjType('entity', 'entity'), # ObjType(type_name, role_name1, role_name 2..., attr1=value1, ...)
        'target': ObjType('target', 'target')
        }

    directives = {
         # 'entity': VHDLTarget,
         # 'target': VHDLTarget,
         'autoentity': VHDLEntityDirective,
         'include-docs': VHDLIncludeDirective,
         'parse': VHDLParseDirective, # Includes a specified range of VHDL comment lines in this document as restructuredText or MarkDown ,
         'test': Test,
   }

    roles = {
        'entity': VHDLXRefRole(lowercase=True),
        'vhdl': vhdl_code_role,
    }

    initial_data = {
        'objects': {},      # (type, name) -> docname, labelid
    }

    dangling_warnings = {
    }

    def clear_doc(self, docname):
      if 'objects' in self.data:

        for key, (fn, _) in list(self.data['objects'].items()):
            if fn == docname:
                del self.data['objects'][key]

    def resolve_xref(self, env, fromdocname, builder,
                     typ, target, node, contnode):

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



