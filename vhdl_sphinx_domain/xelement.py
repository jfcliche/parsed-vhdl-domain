""" Provides the XElement, which extends the ElementTree.Element functionalities
"""

# Standard packages

from xml.etree.ElementTree import Element


class XElement(Element):
    """ Extended ElementTree.Element with additional useful methods.
    """


    def __init__(self, tag, attrib={}, text=None, **extra):
        super().__init__(tag, attrib=attrib, **extra)
        if text is not None:
            self.text = text

    def __getattr__(self, name):
        if name in self.attrib:
            return self.attrib[name]
        elif len(self):
            return getattr(self[0], name)
        else:
            raise AttributeError(f'Element or leading subelement have no attribute {name}')

    def __setattr__(self, name, value):
        if name in self.attrib:
            self.attrib[name] = value
        else:
            super().__setattr__(name, value)

    # @property
    # def col(self):
    #     """Get the col attribute of this element or from the first element of a sub-(sub-...) element
    #     """
    #     if 'col' in self.attrib:
    #         return self.attrib['col']
    #     elif len(self):
    #         return self[0].col
    #     else:
    #         return None

    # @col.setter
    # def col(self, value):
    #     """ Sets the col attribute on this element (not the subelement).The subelement col attribute is no longer returned unless col is set to None.
    #     """
    #     self.attrib['col'] = value

    @property
    def subtext(self):
        """Return the text of this element and all its subelements."""
        return ''.join(t for t in self.itertext())


    # Do not define __eq__ or __ne__ to handle strings : this breaks elem.remove()

    # Some additional method that are specifically useful to query VHDL parse trees

    # def iterskip(self):
    #     for elem in self:
    #         skip = yield elem
    #         if not skip:
    #             # yield from elem.iterskip()  # in python 3.3

    #             g = elem.iterskip()
    #             s = None
    #             while True:
    #                 try:
    #                     s = yield g.send(s)
    #                 except StopIteration:
    #                     break

    def index(self, children):
        """ Returns the the index of a children within this element only (does not search into the children elements; see `findindex()` for this.)

        Parameters:

            children (Element): Element object for which we seek the index

        Returns:

            int: index of object.

        Exceptions:

            Raises a ValueError if the children cannot be found
        """
        return self._children.index(children)


    def findindex(self, elem_or_path):
        """ Like find(), looks recursively for an element, but returns both the parent and index of
        the element. Also can search for an object in addition to a tag or path.

        Parameters:

            elem_or_path (str or Element): element to search.

        """
        if isinstance(elem_or_path, str):
            child = self.find(elem_or_path)
        else:
            child = elem_or_path
        for parent in self.iter():
            if child in parent:
                return (parent, parent.index(child))

    def findsibling(self, elem_or_path, offset=1):
        (p,i) = self.findindex(elem_or_path)
        if i < len(p) - offset:
            return p[i + offset]

    def findwithtext(self,  text, path='.//*', caseless=False):
        if caseless:
            text = text.upper()
        for e in self.iterfind(path):
            if e.text and (e.text.upper() if caseless else e.text) == text:
                return e

    def findwithsubtext(self, path, text, caseless=False):
        if caseless:
            text = text.upper()
        for e in self.iterfind(path):
            if e.subtext and (e.subtext.upper() if caseless else e.subtext) == text:
                return e

    def findall(self, paths, namespaces=None):
        """ Extesion of findall to return a list of nodes matching one or multiple tag or Xpath strings.

        Parameters:

            paths (str or list of str): If `paths` is a string, search for the nodes with the tag or
                XPath it specifies. If `paths` is a list of strings, returns nodes matchin all the
                specified tags or Xpaths.

        Returns: list: list of nodes matching the specified tag(s) or Xpath(s). If multiple strings
            are provided, the same nodes may appear multiple times, and nodes are not listed in
            their order of appearance in the tree.

        """
        if isinstance(paths, str):
            return super().findall(paths, namespaces)
        else:
            return [self.findall(path, namespaces) for path in paths]

    def findallbetween(self, tag, start_at=None, start_after=None, stop_before=None, stop_at=None, recurse=True):
        return [e for e in self.iterbetween(start_at=start_at, start_after=start_after, stop_before=stop_before, stop_at=stop_at, recurse=recurse) if e.tag == tag]


    def iterbetween(self, start_at=None, start_after=None, stop_before=None, stop_at=None, recurse=True):
        """ Same as `iter()`, excepts this method yields only the elements between the specified starting and ending nodes.

        Parameters:

            start_at (str): Xpath describing the first element to be included
            start_after (str): Xpath describing the element after which the elements will be included
            stop_before (str): Xpath indicating the element before which the elements will be included.
            stop_at (str): Xpath indicating the last element to be included.

        Notes:

            - Both start options should not be provided. If so, start_after will takes precedence over start_at.
            - Both end options should not be provided. If so, stop_before will takes precedence over stop_at.
            - The end nodes should not appear before the start nodes
        """
        if start_at is None:
            start_at = tuple()
        elif not isinstance(start_at, (list, tuple)):
            start_at = (start_at,)
        start_at_nodes = [self.find(n) if isinstance(n, str) else n for n in start_at]

        if start_after is None:
            start_after = tuple()
        if not isinstance(start_after, (list, tuple)):
            start_after = (start_after,)
        start_after_nodes = [self.find(n) if isinstance(n, str) else n for n in start_after]

        if stop_at is None:
            stop_at = tuple()
        if not isinstance(stop_at, (list, tuple)):
            stop_at = (stop_at,)
        stop_at_nodes = [self.find(n) if isinstance(n, str) else n for n in stop_at]

        if stop_before is None:
            stop_before = tuple()
        if not isinstance(stop_before, (list, tuple)):
            stop_before = (stop_before,)
        stop_before_nodes = [self.find(n) if isinstance(n, str) else n for n in stop_before]

        started = not start_at and not start_after
        for e in self.iter() if recurse else self:
            if e in start_at_nodes:
                started = True
            if started and e in stop_before_nodes:
                break

            if started:
                yield e

            if e in start_after_nodes:
                started = True
            if started and e in stop_at_nodes:
                break

    def group(self, element_list, tag):
        """ Group the elements in `element_list` into a new XElement with tag `tag`.

        Parameters:

            element_list (list): List of XElements to group. If `element_list` is empty of is `None`, nothing is done.

            tag (str): Tag of the new parent Xelement that contains the specified elements
        """
        if not element_list:
            return
        for i,ee in enumerate(self):
            if ee is element_list[0]: break
        ne = XElement(tag)
        ne.extend(element_list)
        for ee in element_list:
            self.remove(ee)
        self.insert(i, ne)
        return ne

    def move(self, element, target_element, index=None):
        """ Move element(s) `element` into `target_element` at specified position.

        Parameters:

            element (list or XElement): Element(s) to move. If `element` is a list or tuple, move all the specified elements.

            target_element (XElement): Destination element

            index (int or None): If ``index = None`` or ``index = -1``, appends data to the target element. If ``index >= 0``, insert
                the elements starting at the specified index on the target element.
        """

        # make sure we have a list of elements
        if not isinstance(element, (list, tuple)):
            elements = list(element)
        else:
            elements =  element

        if index is None or index == -1:
            for ee in elements:
                self.remove(ee)
                target_element.append(ee)
        elif index >= 0:
            for ee in reversed(element):
                self.remove(ee)
                target_element.insert(index, ee)
        else:
            raise ValueError(f'Index must be either None, -1, or >= 0')

    def subtextbetween(self, start_at=None, start_after=None, end_before=None, end_after=None):
        """ Like `subtext()`, but only returns the contatenated text between the specified starting and ending elements, crossing hierarchy.
        """
        return ''.join(n.text or '' for n in self.iterbetween(start_at=start_at, start_after=start_after, stop_before=end_before, stop_at=end_after))

    def findsubtext(self, path, default=None, namespaces=None):
        """ Returns the combined text of the element specified by `path` and all its children, crossing all hierarchy levels
        """
        elem = self.find(path, namespaces)
        return default if elem is None else elem.subtext or default

    def pp(self, level=0, collapsed_expr=['comment', 'target', 'name', 'expression', 'simple_expression', 'simple_name',  'association_element', '_'], max_depth=0, width=80):
        """ Pretty printer for the XElement tree.
        """
        #skip = ((not t.expr_name or (t.expr_name.startswith('_') and 1)) and t.children) or not t.text
        collapsed =  self.tag in collapsed_expr or (max_depth and level>=max_depth)
        #skip = bool(t.children) or not t.text
        #skip = False
        #if not collapsed:
        print(('%s<%s>(%x) %s%s' % ('   '*level, self.tag, id(self), '(collapsed) ' if collapsed else '', ('' if len(self) and not collapsed else '='+repr(self.subtext) if collapsed else '='+repr(self.text))[:width])))

            #print  '%s%s' % ('   '*(level+1), )
        if not collapsed:
            for elem in self:
                elem.pp(level=(level+1), collapsed_expr=collapsed_expr, max_depth=max_depth)
