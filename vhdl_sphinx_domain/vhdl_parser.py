""" Provides the  :class:`VHDLParser` class that is used to load and parse VHDL files,
and extract the key information (entities, ports etc.) in an easy to use structure.
"""

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



class Namespace(dict):
    """ Dict whose values can be accessed as attributes
    """
    def __getattr__(self,name): return self.get(name)
    def __setattr__(self,name,value): self[name]=value


class VHDLParser(XElement):
    """ ElementTree object representing a set of VHDL files and allows loading and parsing VHDL files, and provides direct access to entity, architectures,
    variables etc across the project


    """

    def __init__(self):
        """ Creates a new parser object
        """
        super().__init__('project')
        # self.vhdl_parser = VHDLParser()
        self.files = {}
        self.entities = Namespace()
        self.labels = {}  # Contains a dict of all labeled objects defined in various namespaces. { (namespace, label_name): labeled_object}

    def token_list_to_element_tree(self, token_list):
        """ Convert VSG token list representing the content of a VHDL file into an hierarchichal XElement tree.

        This method converts each token of `token_list` into an Xelement that is added as children
        to the parent Xelement with the text of the original token. The row and column where each
        element appears is stored as an Xelement attribute to facilitate processing.

        The ``enter_prod`` and ``leave_prod`` attributes of the tokens are used to determine
        when we are entering and leaving a hiearchy level. When a level is entered, a new parent
        Xelement is created tagged with the name of the production we entered, and all subsequent
        tokens are assigned to that parent until we exit that hierarchy level. This is repeated
        recursively.

        The top (i.e root) Xelement represents the VHDL files from which the tagged list was
        revived,  and is tagged with the ``filename`` attribute containing the full file path and
        name of the source file, as provided by the parameter `filename`.

        The parent nodes do not have associated text. The overall text represented by the top
        Xelement and recursively by all its children is identical to the original text reprented by the VSG token
        list.


        All tokens

        Parameters:

            token_list (list): list of tokens produced by VSG. The first element of the list shall
                have the ``filename`` attribute that described the path to the source file from
                which the tokens were parsed.

        Returns:

            A XElement tree representing the VHDL file.

        """

        root = XElement('file', filename=token_list[0].filename)
        elem = [root]
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
        return root


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
        if filename in self.files:
            print("Warning: File '{filename}' has already been parsed. Ignoring." )
            return self.files[filename]
        # Load the VHDL file
        with open(filename, 'r') as file:
            lines = file.readlines()

        # Parse the file using VSG
        if verbose:
            print(f'Parsing the VHDL file {filename} into a token list using VSG')
        vf = vhdlFile.vhdlFile(lines, sFilename=filename)

        # Process the token list from VSG extract the hierarchy
        if verbose:
            print(f'Converting the {filename} token list into an Element tree')
        file_element = self.token_list_to_element_tree(vf.lAllObjects)

        # Group comments in blocks and move those header/trailer comment blocks within their associated productions when appropriate
        if verbose:
            print(f'Processing comments in {filename}')
        self.group_and_move_comments(file_element, recurse=recurse)

        self.append(file_element)
        self.files[filename] = file_element

        # Update the quick-access tables that allows us to easily access the main language elements of the file.
        self.entities.update(self.analyze_entities(file_element))

        return file_element


    def add_label(self, namespace, labels, obj):
        """ Adds one or labels pointing to the object `obj` to the global label dict under the namespace `namespace`

        Parameters:

            namespace (str): namespace ('libraries', 'entities' etc) to which the label(s) are associated with.

            labels (str or list): label strings or list of label strings that contain the label name.

            obj: element associated with the label.

        """
        if not isinstance(labels, list):
            labels = [labels]
        for label in labels:
            if (namespace, label) in self.labels:
                raise ValueError(f"Label {(namespace, label)} is already defined")
            self.labels[(namespace, label)] = obj

    def get_head_and_tail_comments(self, node, verbose=0):
        """ Return the head and tail comment node of the object described by `node`.

        Essentially returns the first and last ``comment_block`` Element  of `node`.

        Parameters:

            node (Xelement): Xelement node from which the comments are to be extracted

            verbose (int): When non-zero, prints debugging messages.

        Returns:

         tuple (head_comment, tail_comment) providing the head and tail comment nodes. Each of these
            elements can be `None` if unavailable.

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


    def analyze_libraries(self, top_elem, filename):
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
                self.add_label('library', lib_name, lib_info)
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

    def analyze_entities(self, top_elem):
        """ Extracts useful information about all entities in the file.

        Parameters:

            top_elem (XElement): file element to analyze

            label_list (): List of all encountered labels, to be updated with labels encountered in the analysis

        Returns:

            Namespace: containsthe following information::

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
            self.add_label('entity', entity_name, entity_info)
            for port in ports:
                self.add_label(f'entity[{entity_name}].port{port.names}', port.names, port)
            for gen in generics:
                self.add_label(f'entity[{entity_name}].generic{port.names}', gen.names, port)
        return entities

    def replace(self, s, substrings, replacement_string):
        """ Replace all occurences of the substrings in string ``s`` by ``replacement_string``
        """
        for ss in substrings:
            s = s.replace(ss,replacement_string)
        return s

    def is_fence(self, s):
        r""" Returns True if the string is a valid RestructuredText fence line.

        A valid fence line contains **only** a consecutive series of three or more fence characters preceded and succeded by spaces.
        The string such as ``=== New Function``  or  ``--- Function below ---``  return False.

        Parameters:

            s (str): string to be tested

        Returns:

            bool: True if the string is a valid RestructuredText fence.

        """
        s = s.strip()
        if not s:
            return False
        return s[0] in "*=-#%^" and s.startswith(s[0]*3) and s != s[0] * len(s)

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
            if self.is_fence(line):
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
        if entity_name.lower() in self.entities:
            return self.entities[entity_name.lower()]
        raise RuntimeError(f'Could not find entity {entity_name} in the current file set. '
                           f"Known entities are {','.join(self.entities.keys())}. Was the VHDL file parsed?")

    def get_file_with_entity(self, name):
        """Returns the file node than contains the entity `name`
        """
        name = name.lower()
        if name in self.entities:
            return self.entities[name].file_node
        print(f'Cannot find {name} in {list(self.entities.keys())}')


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
    """ Pretty-print the Xelement
    """
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
    v = VHDLParser()
    # v = VHDLParser()
    print(('parsing %s'% sys.argv[1]))
    p=v.parse_file(sys.argv[1])
    e = v.get_entity('GPIO')
    # f = v.get_file_with_entity('FFT')