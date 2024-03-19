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
        raise AttributeError(f'Element has no attribute {name}')

    def __setattr__(self, name, value):
        if hasattr(self, name):
            super().__setattr__(name, value)
        else:
            self.attrib[name] = value



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

    # def iterbetween(self, start_at=None, start_after=None, end_before=None, end_after=None):
    #     if start_at is not None and start_after is not None:
    #         raise TypeError('Both start_at and start_after cannot be provided')
    #     elif start_at is not None:
    #         start = start_at
    #         is_start_after = False
    #     elif start_after is not None:
    #         start = start_after
    #         is_start_after = True
    #     else:
    #         is_start_after = False
    #         start = self

    #     if end_before is not None and end_after is not None:
    #         raise TypeError('Both end_before and end_after cannot be provided')
    #     elif end_before is not None:
    #         end = end_before
    #         is_end_before = True
    #     elif end_after is not None:
    #         end = end_after
    #         is_end_before = False
    #     else:
    #         is_end_before = False
    #         end = None

    #     if isinstance(start, str):
    #         start = self.find(start)
    #     if isinstance(end, str):
    #         end = self.find(end)

    #     it = self.iterskip()
    #     #print 'looking for start=', start
    #     for e in it:
    #         if e == start:
    #             #print 'found start'
    #             if is_start_after:
    #                 #print 'skipping', e
    #                 e = it.send(True) # skip this node and its children completely
    #             yield e
    #             for ee in it:
    #                 #print 'testing ', ee
    #                 if is_end_before and ee == end:
    #                     return
    #                 yield ee
    #                 if ee is end:
    #                     for eee in ee.iter():
    #                         yield eee
    #                     return

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
        start_at_node = self.find(start_at) if isinstance(start_at, str) else start_at
        start_after_node = self.find(start_after) if isinstance(start_after, str) else start_after
        stop_before_node = self.find(stop_before) if isinstance(stop_before, str) else stop_before
        stop_at_node = self.find(stop_at) if isinstance(stop_at, str) else stop_at

        started = False
        for e in self.iter() if recurse else self:
            if e is start_at_node:
                started = True
            if e is stop_before_node:
                break

            if started:
                yield e

            if e is start_after_node:
                started = True
            if e is stop_at_node:
                break

    def group( self, element_list, tag):
        for i,ee in enumerate(self):
            if ee is element_list[0]: break
        ne = XElement(tag)
        ne.extend(element_list)
        for ee in element_list:
            self.remove(ee)
        self.insert(i, ne)
        return ne

    def move(self, element, target_element, index=None):
        if isinstance(element, (list, tuple)):
            for ee in reversed(element):
                self.move(ee, target_element, index)
        else:
            self.remove(element)
            if index is None:
                target_element.append(element)
            else:
                target_element.insert(index, element)

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
