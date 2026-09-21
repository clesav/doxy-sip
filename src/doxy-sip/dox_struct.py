# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>


import os
from xml.dom.minidom import Element, parse as xml_parse
from sphinx.domains import Domain


class DoxElement:

    def __init__(self, element: Element):
        self._element = element

    def find_children(self, tag:str):
        for n in self._element.childNodes:
            if n.nodeType == Element.ELEMENT_NODE and n.tagName == tag:
                yield DoxElement(n)

    def find_child(self, tag:str):
        for n in self._element.childNodes:
            if n.nodeType == Element.ELEMENT_NODE and n.tagName == tag:
                return DoxElement(n)
        return None

    def getElementsByTagName(self, tag:str):
        for n in self._element.getElementsByTagName(tag):
            yield DoxElement(n)

    def children(self):
        for n in self._element.childNodes:
            yield DoxElement(n)

    def attr(self, name:str):
        return self._element.getAttribute(name)

    def text(self):
        for n in self._element.childNodes:
            if n.nodeType == Element.TEXT_NODE:
                return n.nodeValue
        return None

    def child_text(self, tag:str):
        n = self.find_child(tag)
        if n is None:
            return None
        return n.text()

    def __getattr__(self, attr):
        return getattr(self._element, attr)


def _get_dox_index(domain):
    dox_dir = domain.env.app.config.sip_doxygen_project
    dox_dir = os.path.abspath(dox_dir)

    dox_index = domain.data['sip_dox_index']
    if dox_index is None:
        index_path = os.path.join(dox_dir, 'index.xml')
        dox_index = xml_parse(index_path)
        domain.data['sip_dox_index'] = dox_index

    root = DoxElement(dox_index.documentElement)
    return root


def _load_dox_compound(domain, fn):
    dox_dir = domain.env.app.config.sip_doxygen_project
    dox_dir = os.path.abspath(dox_dir)
    fp = os.path.join(dox_dir, fn + '.xml')
    xmldoc = xml_parse(fp)
    root_element = DoxElement(xmldoc.documentElement)
    return root_element.find_child('compounddef')


def get_dox_class(domain, name, kinds):
    root = _get_dox_index(domain)
    for node in root.find_children('compound'):
        if kinds and node.attr('kind') not in kinds: continue

        class_name_node = node.find_child('name')
        if class_name_node.text() != name: continue

        refid = node.attr('refid')
        dox_klass = _load_dox_compound(domain, refid)
        return dox_klass

    return None


def get_dox_enum(domain, name):
    dox_index = _get_dox_index(domain)

    if '::' in name:
        namespace, basename = name.rsplit('::', 1)
    else:
        namespace, basename = None, name

    for index_cpd_node in dox_index.find_children('compound'):
        for index_member_node in index_cpd_node.find_children('member'):
            if index_member_node.attr('kind') != 'enum': continue
            if index_member_node.child_text('name') != basename: continue
            if namespace is None:
                #Global enums belong to a 'file' compound
                if index_cpd_node.attr('kind') != 'file': continue
            else:
                if index_cpd_node.child_text('name') != namespace: continue

            cpd_refid = index_cpd_node.attr('refid')
            cpd_root = _load_dox_compound(domain, cpd_refid)
            for n in cpd_root.getElementsByTagName('memberdef'):
                if n.attr('kind') == 'enum' and n.child_text('name') == basename:
                    return n

    return None


#Mapping doxygen admonition -> sphinx admonition
#TODO: complete the list
_ADMONITIONS = {
    'note': 'note',
    'see': 'seealso',

}


class _LineList:

    def __init__(self):
        self._lines = []
        self._current_line = ''

    def __iadd__(self, text):
        self._current_line += text
        return self

    def flush(self):
        if self._current_line:
            self._lines.append(self._current_line)
            self._current_line = ''

    def newline(self):
        self.flush()
        self._lines.append('')

    def extend(self, lines):
        self.flush()
        self._lines.extend(lines)

    def clean_lines(self):
        self.flush()

        while self._lines and not self._lines[0].strip(' \n'):
            del self._lines[0]

        while self._lines and not self._lines[-1].strip(' \n'):
            del self._lines[-1]

        if self._lines:
            self._lines[0] = self._lines[0].lstrip()

        return self._lines


#This is messy and probably naive
def parse_dox_description(dox_node):
    lines = _LineList()
    for n in dox_node.children():

        if n.nodeType == Element.TEXT_NODE:
            text = n.nodeValue.strip(' \n')
            if text:
                lines += f' {text}'

        elif n.nodeType == Element.ELEMENT_NODE:
            if n.tagName == 'emphasis':
                text = n.text()
                lines += f' *{text}*'

            elif n.tagName == 'para':
                lines.newline()
                lines.extend(parse_dox_description(n))
                lines.newline()

            elif n.tagName == 'ref':
                text = n.text()
                if n.attr('kindref') == 'compound':
                    lines += f" :py:class:`{text}`"
                else:
                    lines += f' {text}'

            elif n.tagName == 'simplesect':
                k = n.attr('kind')
                if k in _ADMONITIONS:
                    rst_directive = '.. ' + _ADMONITIONS[k] + '::'
                    lines.extend(('', rst_directive, ''))
                    lines.extend('   ' + line for line in parse_dox_description(n))
                    lines.newline()
                elif k == 'return':
                    pass
                elif k == 'par':
                    lines.newline()
                    lines += n.child_text('title') + ':'
                    lines.extend('   ' + line for line in parse_dox_description(n.find_child('para')))
                    lines.newline()
                else:
                    raise ValueError('Unknown section kind: ' + k)

    return lines.clean_lines()


def extract_description(dox_node: DoxElement) -> list[str]:
    brief = parse_dox_description(dox_node.find_child('briefdescription'))
    detail = parse_dox_description(dox_node.find_child('detaileddescription'))
    if brief and detail:
        return brief + [''] + detail
    else:
        return brief + detail


def extract_single_line_description(dox_node: DoxElement) -> str:
    lines = parse_dox_description(dox_node)
    if len(lines) > 1:
        raise ValueError()
    return lines[0] if lines else None


def get_stripped_type(dox_type_node):
    t = []
    for n in dox_type_node.children():
        if n.nodeType == Element.TEXT_NODE:
            t.append(n.nodeValue)
        elif n.nodeType == Element.ELEMENT_NODE:
            if n.tagName == 'ref':
                t.append(n.text())

    s = ''.join(t)
    s = s.replace('constexpr', '').strip()
    return s

