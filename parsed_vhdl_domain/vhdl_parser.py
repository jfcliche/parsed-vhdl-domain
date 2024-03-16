
# Standard packages
import sys
import os
import time
import textwrap

# Pypi packages

import yaml
import vsg
from vsg import vhdlFile, token

# Local packages

from .xelement import XElement



# class Namespace(object):
#     """ Simple container to hold alll sort of data.
#     """
#     def __init__(self, **kwargs):
#         vars(self).update(**kwargs)

class Namespace(dict):
    """ Dict whose values can be accessed as attributes
    """
    def __getattr__(self,name): return self.get(name)
    def __setattr__(self,name,value): self[name]=value



# class VHDLParser(object):
#     """ Creates a parser that parses VHDL files into ElementTree from which any language constrict can be queried"""

#     commented_expr = ['entity_declaration', 'generic_element', 'interface_element', 'library_clause', 'use_clause']

#     def __init__(self):
#         """ Initializes the VHDL parser """
#         # Load and parse the VHDLsyntax file
#         # print('VHDL Parser: loading VHDL syntax file')
#         # vhdl_grammar_filename = os.path.join(os.path.dirname(__file__), 'vhdl_grammar.txt')
#         # with open(vhdl_grammar_filename) as f:
#         #     self.vhdl_grammar=f.read()
#         # self.vhdl_rules = None  # for now don't parse the rules, in case we don't need to
#         self._last_code = None


#     # def parse_to_node_tree(self, code, pos=0, rule_name='statements'):
#     #     #  if code hash not in cache, parse
#     #     self.parse_vhdl_syntax() # make sure the parser exist
#     #     return self.vhdl_rules[rule_name].parse(code, pos=pos)

#     # def parse(self, code=None, pos=None, line=None, rule_name='statements'):
#     #     """ Parse the VHDL code.

#     #     Parameters:

#     #         code (str): Code to parse

#     #         pos (int): position from which to parse in `code`. Zero-based. Default is zero if no
#     #             line number is specified.

#     #         line (int): line number from which to parse in `code`. leading spaces are skipped.
#     #             `line` **is zero-based**, unlike what editos show, but is consistent with the parser
#     #             reporting. Default is first line of `code` if no `pos` is specified.

#     #         rule_name(str): Name of the VHDL rule to parse with.

#     #     Returns:

#     #             An ElementTree of the parsed code, with comments fixed to be grouped with their proper
#     #         associated elements.

#     #     """
#     #     if code is None:
#     #         if self._last_code:
#     #             code = self._last_code
#     #         else:
#     #             raise ValueError('Please provide the soure code')
#     #     if line is None and pos is None:
#     #         pos = 0
#     #     elif line is not None:
#     #         # line -= 1
#     #         lines = code.splitlines(True)
#     #         pos = sum(len(t) for t in lines[:line])
#     #         pos += len(lines[line]) - len(lines[line].lstrip()) # skip whitespaces
#     #         print(('starting with text at pos %i:%r' % (pos, code[pos:pos+300])))
#     #     else:
#     #         raise TypeError('Cannot specify both pos and line arguments')

#     #     elem = self.node_to_element(self.parse_to_node_tree(code, pos=pos, rule_name=rule_name))

#     #     # fix empty tags
#     #     for e in elem.iter():
#     #         if not e.tag:
#     #             e.tag = 'tag'

#     #     # Fix comments (move surrounding comment lines back into their associated elements)
#     #     self.fix_comments(elem)


#     #     return elem


#     #def node_to_element_tree(self, node):
#     #    return self.node_to_element(node)


#     # create_comment_blocks(etc)

#     def move_header_comments(self, et):

#         for e in et.iter():
#             if e.tag in ('parser.whitespace', 'parser.comment', 'parser.carriage_return'):
#                 comment.append(e)


#     def fix_comments(self, elem):
#         """ Scan the parsed code and move block comments and trailing line comments back into the associated element.

#         Arguments:
#             elem (VHDLElement (ElementTree.Element)): The parsed tree to process

#         Returns:
#             Nothing. The Element Tree is modified in-place.

#         Note:
#             The nodes of the element tree are moved in a way that the source code it represents is not modified.
#         """
#         print('VHDL Parser: Identifying block comments')
#         VHDLBlockCommentTransform(elem)
#         print('VHDL Parser: Assigning block comments to their associated VHDL elements')
#         VHDLMoveHeadComments(elem, self.commented_expr)
#         print('VHDL Parser: Assigning trailing end-of-line comments to their associated VHDL elements')
#         VHDLMoveTailComments(elem, self.commented_expr)
#         return




class VHDLFiles(XElement):
    """ ElementTree object representing a set of VHDL files and allows loading and parsing VHDL files, and provides direct access to entity, architectures,
    variables etc across the project


    """

    def __init__(self):
        super().__init__('project')
        # self.vhdl_parser = VHDLParser()
        self.summaries = {}
        self.entities = Namespace()
        self.labels = []
        # self.load_remap_table()


    def load_remap_table(self):
        """ Load and process the remap table.

        The remap table is a YAML file that list the VSG tokens that identify the first and  last token
        of each "production" (i.e. basic language elements). These tags are used to reconstruct a hiearchical version of the token list.

        This retagging won't be needed if VSG is mofified to perform the tagging as part of its token classification phase.
        """
        with open('remap.yaml', 'r') as file:
            self.remap_table = yaml.safe_load(file)

        # Recursively add the _name field to every dict and set it to the name of that dict in the yaml file
        # The _name will be used to set the name of the production.
        def add_names(d):
            for (k,v) in d.items():
                # print(f'{k}:{v}')
                if isinstance(v, dict):
                    v['_name'] = k
                    add_names(v)
        add_names(self.remap_table)
        self.remap_table['_name'] = 'file'
        print(self.remap_table)


    def tag_token_list(self, token_list):
        """ Add language production tags to the originally untagged VSG token list in order to provide hierarchy cues.

        VSG parser provides a flat token list that does not (yet) have tags that hint at the
        hiearchy of the language elements of the parsed file. This function uses a remap table to
        identify the boundaries of the language elemts and add those hierarchy tags to the tokens.

        Parameters:

            token_list (list): token list generated by VSG. Will be modified in-place.
        Returns:
            None. The provided `token_list` is modified in-place.

        """
        elem = [self.remap_table]  # current element being processed
        elem_update = True

        def ensure_tuple(v):
            return tuple() if v is None else v if isinstance(v, (tuple, list)) else (v, )
        i = 0
        while i < len(token_list):
            tn = token_list[i].get_unique_id('.')
            if elem_update:
                e = elem[-1]  # current language element, always at the end of the list
                en = e['_name'] # name of the curent language element
                # get the names of the boundary tokens for the current element
                end_at = ensure_tuple(e.get('_end_at'))
                end_before = ensure_tuple(e.get('_end_before'))
                start_at_dict = {ee.get('_start_at'):ee for en, ee in e.items() if '_start_at' in ee}
                start_after_dict = {ee.get('_start_after'):ee for en, ee in e.items() if '_start_after' in ee}

            if any(tn.endswith(s) for s in end_before):
                elem.pop()
                elem_update = True
                token_list[i-1].leave_classify.append(en)
                continue

            if r := [s for s in start_at_dict if tn.endswith(s)]:
                e = start_at_dict[r[0]]
                elem.append(e)
                elem_update = True
                token_list[i].enter_classify = e['_name']
                continue

            if any(tn.endswith(s) for s in end_at):
                elem.pop()
                elem_update = True
                token_list[i].leave_classify.append(e['_name'])
                continue
            # if t.sub_token not in ('whitespace'):
            #     path = ':'.join(ee['_name'] for ee in elem if not ee['_name'].startswith('_') )
            #     print(f"[{i}]{path}.{t.sub_token}: {t.get_value()}")

            i += 1
            if r := [s for s in start_after_dict if tn.endswith(s)]:
                e = start_at_dict[r[0]]
                elem.append(start_after_dict[r[0]])
                elem_update = True
                token_list[i].leave_classify.append(e['_name'])
                continue


            # t0 = time.time()
            # print(('VHDL Parser: loading %s' % os.path.abspath(filename)))
            # with open(filename) as f:
            #     code = f.read()
            # load_time = time.time() - t0
            # t0 = time.time()
            # self._last_code = code  # save for debugging
            # print(('VHDL Parser: parsing %s' % filename))
            # nodes = self.parse(code)
            # parsing_time = time.time() - t0
            # print(('VHDL Parser: Finished processing %s. Loading took %0.3f s, parsing took %0.3f s.' % (filename, load_time, parsing_time)))
            # return nodes

    def token_list_to_element_tree(self, filename, token_list):
        """ Convert VSG token list representing the content of a VHDL file into an XElement tree


        Parameters:

            filename (str): value of the attribute ``filename`` applied to the top element

            token_list (list): list of tokenes processed by VSG

        Returns:

            A XElement  tree containing the hierarchical version of the VHDL file.

        """

        et = XElement('file', filename=filename)
        elem = [et]
        col = 0
        line = 0
        for t in token_list:
            for prod in t.enter_prod:
                ne = XElement(prod, col=col, line=line)
                elem[-1].append(ne)
                elem.append(ne)
            # if 1 or t.sub_token not in ('whitespace'):
            #     print(f"[{i}]{hier!s}({t.sub_token}): {t.get_value()}")
            ne = XElement(t.get_unique_id('.'), col=col, line=line)
            ne.text = t.value
            elem[-1].append(ne)
            col += len(ne.text)
            if ne.tag == 'parser.carriage_return':
                col = 0
                line += 1
            for prod in t.leave_prod:
                elem.pop()
        return et


    def group_and_move_comments(self, etc, recurse=True, verbose=0):
        """ Scan the Element tree and group comments into 'comment_block' elements, and move those
        elements within the entity they precede or trail.
        """
        comment_group= []  # accumulated comment lines
        comment_group_col = None # column number of the first comment of the group
        comment_line = []  # used to accumulate whitespce and comments before potentiallly writing those to the group if they qualify
        comment_line_col = None
        delimited_comment = False
        last_prod = None   # last production
        def process_comment_group(e):
            nonlocal comment_line, comment_line_col, comment_group, comment_group_col, last_prod

            if not comment_group:
                return
            if verbose:
                print(f'Grouping comments {comment_group}. e={e}')
            cg = etc.group(comment_group, 'comment_block')
            comment_group = []
            comment_group_col = None

            # If we are trailing a production element, move comment grup and any post-production items into it
            if last_prod is not None:
                if verbose:
                    print(f'Moving trailing comment {cg} into prod {last_prod}')
                for ee in list(etc.iterbetween(start_after=last_prod, stop_before=cg, recurse=False)):
                    if verbose:
                        print(f'... moving {ee}')
                    etc.remove(ee)
                    last_prod.append(ee)
                if verbose:
                        print(f'Moving {cg} from {list(etc)}')
                etc.move(cg, last_prod)
                last_prod = None
            # Otherwise, if we are on a production element, move the comment group and trailing blanks into it
            elif len(e):
                if verbose:
                    print(f'Moving header comment {cg} into prod {e} with line {comment_line}')
                etc.move(cg, e, 0)
                etc.move(comment_line, e, 1)
                comment_line.clear()
                comment_line_col = None

        for e in list(etc): # make a copy so we can safely modify the tree
            if verbose:
                print(f"Processing {e.tag} '{e.text!r}' @ line {e.get('line')} col {e.get('col')}, prod=(tag={last_prod})")
            # If we are in a comment block and get to the end
            if delimited_comment:
                comment_line.append(e)
                if e.tag == 'delimited_comment.ending':
                    delimited_comment = False
                elif e.tag == 'parser.carriage_return':
                    comment_group.extend(comment_line)
                    comment_line.clear()
                    if comment_group_col is None:
                        comment_group_col = comment_line_col
            elif e.tag == 'delimited_comment.beginning':
                comment_line.append(e)
                delimited_comment = True
                comment_line_col = e.col  # replace with real column
            elif e.tag in ('parser.whitespace', 'parser.blank_line'):
                comment_line.append(e)
            elif e.tag == 'parser.comment':
                comment_line.append(e)
                comment_line_col = e.col # replace with real column
            elif e.tag == ('comment_block', 'blank_line'):
                pass
            elif e.tag == 'parser.carriage_return':
                if verbose:
                    print(f'carriage_return, e=(tag={e.tag}, text={e.text!r}), group=(len={len(comment_group)},col={comment_group_col}), line=(len={len(comment_line)}, col={comment_line_col})')
                comment_line.append(e)

                # If we have the end of a comment that is indented the same or to the right of the existing comment, add it to the group
                if comment_line_col is not None and (not comment_group or comment_group_col is None or comment_line_col >= comment_group_col):
                    if verbose:
                        print(f'   Appending line to comment group')
                    comment_group.extend(comment_line)
                    comment_line.clear()
                    comment_line_col = None
                # if we detect the comment end (non-blank or non-comment element, empty line, comment with change of indentation,
                # create an comment block element with the current comment group
                else:
                    if verbose:
                        print(f'   Blank or left indented comment line')
                    process_comment_group(e)
                    last_prod = None
                    if comment_line:
                        if comment_line_col is None:
                            if comment_line[0].get('col') == 0:
                                etc.group(comment_line, 'blank_line')
                        else:
                            comment_group.extend(comment_line)
                            comment_group_col = comment_line_col
                    comment_line.clear()
                    comment_line_col = None
            else: # We have a non-comment token
                if verbose:
                    print(f'others, e=(tag={e.tag}, text={e.text!r}), group=(len={len(comment_group)},col={comment_group_col}), line=(len={len(comment_line)}, col={comment_line_col})')
                process_comment_group(e)
                comment_line.clear()
                comment_line_col = None
                if len(e):
                    last_prod = e
                elif e.text != ';':
                    last_prod = None

        # process comments in sub-nodes
        if recurse:
            for e in list(etc):
                if len(e) and e.tag not in ('comment_block','blank_line'):
                    self.group_and_move_comments(e)

    def parse_file(self, filename, recurse=True, verbose=1):
        """ Parse and analyze the specified VHDL file and add the resulting info to th

        Parameters:

            filename (str): filename of the VHDL file to be parsed


        Returns:

            XElement(tag='file', filename=<current_filename>') whose children describe the parsed file.
        """
        if filename in self.summaries:
            print(("Warning: File '%s' has already been parsed" % filename))
            # raise RuntimeError("File '%s' has already been parsed" % filename)

        # Load the VHDL file
        with open(filename, 'r') as file:
            lines = file.readlines()

        # Parse the file using VSG
        if verbose:
            print(f'Parsing the VHDL file {filename} into a token list using VSG')
        vf = vhdlFile.vhdlFile(lines)
        # Process the token list from VSG extract the hierarchy
        # self.remap_token_list(vf.lAllObjects)
        if verbose:
            print(f'Converting the {filename} token list into an Element tree')
        file_element = self.token_list_to_element_tree(filename, vf.lAllObjects)
        if verbose:
            print(f'Processing comments in {filename}')
        self.group_and_move_comments(file_element, recurse=recurse)
        self.append(file_element)


        self.entities.update(self.analyze_entities(file_element, self.labels))

        # Add summary info
        # self.summaries[filename] = summary

        # Add entities found in the summary to global entity list
        # for entity_key, entity in list(summary['entities'].items()):
        #     if entity_key in self.entities:
        #         print(("Entity '%s' has already been parsed" % entity.name))

        #         # raise RuntimeError("Entity '%s' has already been parsed" % entity['name'])
        #     self.entities[entity_key] = entity
        return file_element


    def add_label(self, label_list, typ, label, obj):
        if not isinstance(label, list):
            label = [label]
        for lab in label:
            if (typ, lab) in label_list:
                raise ValueError("%s label '%s' is already defined" % (typ, lab))
            label_list[(typ, lab)] = obj

    def get_head_and_tail_comments(self, node, verbose=0):
        """ Return the head and tail comment node of the object described by `node`.

        Essentially returns the first and last ``comment_block`` Element  of `node`.


        Returns: (head_comment, tail_comment) tuple providing the head and tail comment nodes. These
            elements are `None` if unavailable.
        """
        block_comments = node.findall('comment_block')
        if verbose:
            print(f'block comments  are {block_comments}')
        n = len(block_comments)
        head_comments = tail_comments = None
        if n > 0:
            head_comments = block_comments[0]
        if n > 1:
            tail_comments = block_comments[-1]

        # head_comments = [n.text for n in node.findall('.//head_comment//comment_text')]
        # tail_comments = [n.text for n in node.findall('.//tail_comment//comment_text')]
        return (head_comments, tail_comments)



    # def analyze(self, top_elem, filename=''):
    #     """
    #     Process a parsed VHDL file and extract key information from it for easy access through
    #     standard namespace objects.

    #     Arguments:
    #         - elem (VHDLElement): The root node of the element tree containing the parsed VHDL

    #     Returns:
    #         Namespace object.


    #         labels:
    #             - {name, type, object}  # type= generic, port, signal, attribute, instance

    #         entities:
    #             generics:
    #                 - generic1 : {name: [], dir: str, type: str, default:str, pre_comment:str, post_comment: str}
    #             port:
    #                 -
    #             architecture:
    #                 signal:
    #                 constant:
    #                 attribute:
    #                 instances:
    #                 process:
    #                 variables:

    #         entity2:
    #     Note:
    #         The analysis code is dependent in the VHDL sytax definition file structure.

    #     """
    #     # summary = ElementTree.Element
    #     # def get_node(node, tag):
    #     #     n = node.find('tag')
    #     #     if not n:
    #     #         n = ElementTree.Element
    #     #         node.append(n)
    #     #     return n

    #     labels = {}
    #     libraries = self.analyze_libraries(top_elem, labels, filename=filename)
    #     entities = self.analyze_entities(top_elem, labels, filename=filename)

    #     return dict(libraries=libraries, entities=entities,  labels=labels)


    def analyze_libraries(self, top_elem, label_list, filename):
        # Analyze LIBRARY clauses
        libraries = {}  # get_node(summary, 'library')
        libraries['work'] = Namespace(name='work', use=[], block_comment=[], tail_comment=[], node=None, source_file='')

        for lib_node in top_elem.findall('.//library_clause'):
            for id_node in lib_node.findall('.//identifier'):
                lib_name = id_node.subtext
                lib_head_comments, lib_tail_comments = self.get_head_and_tail_comments(lib_node)
                lib_info = Namespace(name=lib_name,
                                     node=lib_node,
                                     use=[],
                                     source_file=filename,
                                     head_comments=lib_head_comments,
                                     tail_comments = lib_tail_comments)
                libraries[lib_name.lower()] = lib_info
                self.add_label(label_list, 'library', lib_name, lib_info)
                # print 'Added library', lib_name

        # Analyze USE clauses
        for use_node in top_elem.findall('.//use_clause'):
            for selected_name in use_node.findall('.//selected_name'):
                name_node = selected_name.find('.//name')
                use_head_comments, use_tail_comments = self.get_head_and_tail_comments(use_node)
                if name_node is None or len(name_node) < 2:
                    raise RuntimeError('Use clause must have a prefix and one or more suffixes')
                lib_name = name_node[0].subtext
                sel_name = ''.join(n.subtext for n in name_node[1:])
                use_info = Namespace(label=sel_name,
                                     node=use_node,
                                     head_comments=lib_head_comments,
                                     tail_comments = lib_tail_comments)
                # print 'Use lib', lib_name
                if lib_name.lower() not in libraries:
                    print(use_node.subtext)
                    raise RuntimeError("Use of library '%s' before it is defined" % lib_name);
                libraries[lib_name.lower()].use.append(use_info)

        return libraries

    def analyze_entity_interface(self, interface_nodes):
        """
        Extract port or generics information from an entity element `entity_elem`.

        Arguments:
            line_name (str): Xpath used to find the element list
            element_name (str): Xpath used to find the element within the list

        Return:
            (list): list of dicts containing:

                name_list (list of str): list of port/generic identifier names. Is empty if the entry is for an isolated (sectionning) comment.
                definition (str): rest of the port/generics definition
                comments (str): Single newline-separated string containing both the head and tail comment for that interface element
        """
        if not interface_nodes:
            return []
        # interface_list_node = entity_elem.find(list_name)
        # if interface_list_node is None: return []
        interface_list = []
        for elem in interface_nodes:
            # elif elem.tag == '_':
            #     comment_nodes = elem.findall('.//comment_text')
            #     if comment_nodes:
            #         comments = '\n'.join(e.subtext for e in comment_nodes)
            #         interface_list.append(Namespace(names=[], definition=None, comments=comments))
            # print(f'testing {elem.tag}={elem.text!r}')
            if elem.tag == 'interface_unknown_declaration':
                name_list = [ n.subtext for n in elem.findall('interface_unknown_declaration.identifier')]
                definition = elem.subtextbetween(start_after='interface_unknown_declaration.colon', end_before='comment_block')
                comments = ';'.join(n.subtext for n in elem.findall('comment_block'))
                interface_list.append(Namespace(names=name_list, definition=definition, comments=comments))
            elif elem.tag == 'comment_block':
                comments = elem.subtext
                interface_list.append(Namespace(names=[], definition=None, comments=comments))
        return interface_list

    def analyze_entities(self, top_elem, label_list):
        """ Extracts useful information about all entities in the file.

        Parameters:

            top_elem (XElement): file element to analyze
            label_list (): List of all encountered labels, to be updated with labels encountered in the analysis

        Returns:
            (Namespace): contains
                <entity_name_in_lowercase1>:
                    name: <entity_name>
                    ports: <list of ports>
                    generics: <list of generics>
                    brief: <brief description of entity>
                    details: <detailed description of entity
                    tail_comment: <tail comment after end of entity>
                    source_file: <name of the source filename>
                <entity_name_in_lowercase2>:
                    ...
        """
        # Analyze entities
        entities = Namespace()
        for entity_node in top_elem.findall('entity_declaration'):
            entity_name = entity_node.find('entity_declaration.identifier').subtext

            # Analyze ports and generics
            ports = self.analyze_entity_interface(entity_node.find('port_clause'))
            generics = self.analyze_entity_interface(entity_node.find('generic_clause'))
            # ports = self.analyze_entity_interface(entity_node, './/interface_list', 'interface_element')

            # Analyze entity comments
            #block_comment=textwrap.dedent('\n'.join(n.text for n in entity_node.findall('.//block_comment//comment_text'))).splitlines()

            head_comments, tail_comments = self.get_head_and_tail_comments(entity_node)
            brief, details = self.split_block_comments(head_comments)
            # tail_comment_block = entity_node[-1].text if entity_node[-1].tag == 'block_comment' else ''
            # entity_info = Namespace(name=entity_name, ports=ports, generics=generics, brief=brief, details=details, source_file=filename)
            entity_info = Namespace(name=entity_name,
                                    ports=ports,
                                    generics=generics,
                                    brief=brief,
                                    details=details,
                                    tail_comment=tail_comments,
                                    source_file=top_elem.filename,
                                    entity_node=entity_node,
                                    file_node=top_elem)
            entities[entity_name.lower()] = entity_info

            # Add labels to the label list
            # self.add_label(label_list, 'entity', entity_name, entity_info)
            # for port in ports:
            #     self.add_label(label_list, 'entity.port', port.names, port)
            # for gen in generics:
            #     self.add_label(label_list, 'entity.generic', gen.names, port)
        return entities

    def replace(self, s, substrings, replacement_string):
        """ Replace all occurences of the substrings in string ``s`` by ``replacement_string``
        """
        for ss in substrings:
            s = s.replace(ss,replacement_string)
        return s

    def is_header(self, s):
        if not s:
            return False
        c = s[0]
        return c in "*=-#%^" and s.startswith(c*3) and s != c*len(s)

    def dedent(self, s):
        return textwrap.dedent('\n'.join(s)).splitlines()

    def remove_comment_marks(self, lines, dedent=False):
        """ Remove leading and trailing comment marks, decorative headers as well as Doxygen markers.

        A decorative header is a repeated fence character (`-`,`*`, `#` etc) followed by some text (e.g. `### Example 1`, `------ Example 2 ---)`).
        """
        new_lines = []
        for line in lines:
            s = line.strip()
            # Discard decorative headers
            if self.is_header(line):
                continue
            # Remove leading comment marks
            for ss in ('/*', '--!', '--'):
                if s.startswith(ss):
                    s = s[len(ss):]
            # Remove trailing comment marks
            for ss in ('*/', ):
                if s.endswith(ss):
                    s = s[:-len(ss)]
            # Remove Doxygen markers
            for ss in ('@brief', '@details'):
                s = s.replace(ss, '')
            new_lines.append(s)
        if dedent:
            new_lines = self.dedent(new_lines)
        return new_lines

    def split_block_comments(self, block_comments, dedent_brief=True, dedent_details=True, verbose=0):
        """
        Split a comment block in two parts: the first paragraph is stripped of spaces and is return
        as a first list, while the rest of the comment block is in the second list and is dedented
        as a block.


        Returns:
            ``(brief, details)`` tuple where

                ``brief`` (list of str) is the lines of the first paragraph of the first comment block

                ``details`` (list of str) is the dedented lines of the subsequent blocks
        """
        if not block_comments:
            return ([], [])
        brief = []
        details = []
        is_brief = True

        # for block in block_comments:
        # lines = self.replace(block_comments.subtext, ('/*', '*/', '--!', '--', '@brief', '@details'), '')
        lines = self.remove_comment_marks(block_comments.subtext.splitlines())
        if verbose:
            print(f'lines = {lines}')
        for line in lines:
            # stripped_line = line.strip()
            # if  self.is_header(line):
            #     continue
            if verbose:
                print(f'sl={line!r}')
            if is_brief and brief and not line: # is en empty line once we have a brief
                is_brief = False
                continue # don't store the empty line
            if is_brief:
                brief.append(line.strip())
            else:
                details.append(line)
        if dedent_brief:
            brief = self.dedent(brief)
        if dedent_details:
            details = self.dedent(details)
        return brief, details

    def get_entity(self, entity_name):
        # for entity_node in self.findall('.//entity_declaration'):
        #     if entity_node is not None and entity_node.findsubtext('identifier').upper() == name.upper():
        #         return entity_node
        if entity_name.lower() in self.entities:
            return self.entities[entity_name.lower()]
        raise RuntimeError(f'Could not find entity {entity_name} in the current file set. '
                           f"Known entities are {','.join(self.entities.keys())}. Was the VHDL file parsed?")

    def get_file_with_entity(self, name):
        """Returns the file node than contains the entity `name`
        """
        # entity = self.get_entity(entity_name)
        # return self.find(entity.source_file)
        # for file in self:
        #     if file.filename == name or file.findwithsubtext('.//entity_declaration/identifier', name, caseless=True) is not None:
        #         return file
        name = name.lower()
        if name in self.entities:
            return self.entities[name].file_node
        print(f'Cannot find {name} in {list(self.entities.keys())}')


    # def get_entity_summary(self, entity_name):
    #     return self.get_entity(entity_name)

    def get_comments(self, entity, start_before=None, start_after=None, end_before=None, end_after=None, dedent=True):
        def match(source, target):
            if not target: return False
            r = source.find(target)
            return r >= 0

        file = self.get_file_with_entity(entity)
        if file is None:
            raise ValueError(f'get_comments: Cannot find entity {entity}')
        matching_lines = []
        capture = False
        for bc in file.iterfind('.//comment_block'):
            lines = bc.subtext.splitlines()
            for s in lines:
                if match(s, start_before):
                    capture = True
                if match(s, end_before):
                    break
                if capture:
                    matching_lines.append(s)
                if match(s, start_after):
                    capture = True
                    print(f'Found match after {start_after}')
                if match(s, end_after):
                    break
            if matching_lines:  # stop at the end of this block if we found anything in it
                break
        # if not matching_lines:
        #     print(f"COuld not find '{start_after}'")
        # else:
        #     print(f"match={' '.join(matching_lines)}")
        return self.remove_comment_marks(matching_lines, dedent=dedent)

def pp(t, level=0, collapsed_expr=['target', 'name', 'expression', 'simple_expression', 'simple_name', '_']):
    skip = ((not t.expr_name or (t.expr_name.startswith('_') and 1)) and t.children) or not t.text
    collapsed =  t.expr_name in collapsed_expr
    #skip = bool(t.children) or not t.text
    #skip = False
    if not skip or collapsed:
        print('   '*level, '[%s] (%i-%i) %s' % (t.expr_name, t.start, t.end, ('=' + repr(t.text)) if (not t.children or collapsed) else ''))
    if not collapsed:
        for c in t.children:
            pp(c, (level+1) if not skip else level, collapsed_expr)



if __name__ == '__main__':
    v = VHDLFiles()
    # v = VHDLParser()
    print(('parsing %s'% sys.argv[1]))
    p=v.parse_file(sys.argv[1])
    e = v.get_entity('GPIO')
    # f = v.get_file_with_entity('FFT')