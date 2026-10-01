# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>


import os
import weakref
from xml.dom.minidom import Element, parse as xml_parse
from sphinx.domains import Domain
from sphinx.util import logging

_LOGGER = logging.getLogger('dox_struct')


class DoxElement:

    def __init__(self, element: Element, index_root: Element):
        self._element = element
        self._index_root = index_root

    def find_children(self, tag:str):
        for n in self._element.childNodes:
            if n.nodeType == Element.ELEMENT_NODE and n.tagName == tag:
                yield DoxElement(n, self._index_root)

    def find_child(self, tag:str):
        for n in self._element.childNodes:
            if n.nodeType == Element.ELEMENT_NODE and n.tagName == tag:
                return DoxElement(n, self._index_root)
        return None

    def getElementsByTagName(self, tag:str):
        for n in self._element.getElementsByTagName(tag):
            yield DoxElement(n, self._index_root)

    def children(self):
        for n in self._element.childNodes:
            yield DoxElement(n, self._index_root)

    def parent(self):
        return DoxElement(self._element.parentNode, self._index_root)

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

    def index(self):
        return self._index_root

    def __getattr__(self, attr):
        return getattr(self._element, attr)


def _get_dox_dir(domain):
    dox_dir_conf = domain.env.app.config.sip_doxygen_project
    dox_dir = os.path.join(domain.env.app.confdir, dox_dir_conf)
    dox_dir = os.path.normpath(dox_dir)
    return dox_dir


#Cache for the XML file already loaded
_dox_file_cache = weakref.WeakValueDictionary()


def _get_dox_index(domain):
    dox_dir = _get_dox_dir(domain)

    dox_index = domain.data['sip_dox_index']
    if dox_index is None:
        index_path = os.path.join(dox_dir, 'index.xml')
        dox_index = xml_parse(index_path)
        domain.data['sip_dox_index'] = dox_index

    root = DoxElement(dox_index.documentElement, dox_index.documentElement)
    return root


def _load_dox_compound(domain, index, fn):
    if fn in _dox_file_cache:
        xmldoc = _dox_file_cache[fn]
    else:
        dox_dir = _get_dox_dir(domain)
        fp = os.path.join(dox_dir, fn + '.xml')
        xmldoc = xml_parse(fp)
        _dox_file_cache[fn] = xmldoc

    root_element = DoxElement(xmldoc.documentElement, index)
    return root_element.find_child('compounddef')


def get_dox_class(domain, name, kinds):
    dox_index = _get_dox_index(domain)
    for node in dox_index.find_children('compound'):
        if kinds and node.attr('kind') not in kinds: continue

        class_name = node.child_text('name')
        if class_name != name: continue

        refid = node.attr('refid')
        dox_klass = _load_dox_compound(domain, dox_index, refid)
        return dox_klass

    return None


def _find_member(domain, name, kind):
    dox_index = _get_dox_index(domain)

    if '::' in name:
        namespace, basename = name.rsplit('::', 1)
    else:
        namespace, basename = None, name

    cpd_id = None
    member_id = None
    cpd_kind = ''
    for index_cpd_node in dox_index.find_children('compound'):
        for index_member_node in index_cpd_node.find_children('member'):
            if index_member_node.attr('kind') != kind: continue
            if index_member_node.child_text('name') != basename: continue

            if namespace is not None:
                if index_cpd_node.child_text('name') == namespace:
                    cpd_id = index_cpd_node.attr('refid')
                    member_id = index_member_node.attr('refid')
                    break

            else:
                k = index_cpd_node.attr('kind')
                if k in ('class', 'struct', 'union', 'namespace'): continue
                if k == 'file' and cpd_kind and cpd_kind != 'file': continue

                cpd_id = index_cpd_node.attr('refid')
                member_id = index_member_node.attr('refid')

    if cpd_id is not None:
        cpd_root = _load_dox_compound(domain, dox_index, cpd_id)
        for n in cpd_root.getElementsByTagName('memberdef'):
            if n.attr('id') == member_id:
                return n

    return None


def get_dox_enum(domain, name):
    return _find_member(domain, name, 'enum')

def get_dox_variable(domain, name):
    return _find_member(domain, name, 'variable')


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
                    _LOGGER.warning("parse_dox_description() : unsupported section kind " + k)

            elif n.tagName == 'itemizedlist':
                lines.newline()
                lines.extend(_parse_dox_list(n))
                lines.newline()

            elif n.tagName == 'table':
                lines.newline()
                lines.extend(_parse_dox_table(n))
                lines.newline()

            elif n.tagName == 'linebreak':
                lines.newline()

            else:
                _LOGGER.warning("parse_dox_description() : unsupported tag " + n.tagName)

    return lines.clean_lines()


def _parse_dox_list(list_node):
    lines = []
    for item_node in list_node.find_children('listitem'):
        item_lines = parse_dox_description(item_node)
        lines.extend(('  ' if i else '- ') + item_line
                     for i, item_line in enumerate(item_lines))
        lines.append('')
    return lines


def _parse_dox_table(table_node):

    class _Entry:
        def __init__(self, entry_node):
            self.content = parse_dox_description(entry_node)
            self.len = max((len(line) for line in self.content), default=0)
            self.rowspan = int(entry_node.attr('rowspan')) if entry_node.attr('rowspan') else 1
            self.colspan = int(entry_node.attr('colspan')) if entry_node.attr('colspan') else 1
            self.thead = (entry_node.attr('thead') == 'yes')

    class _Cell:
        def __init__(self, entry, rofs, cofs):
            self.entry = entry
            self.rofs = rofs
            self.cofs = cofs
            self.w = int((entry.len / entry.colspan) + (1 if (cofs < (entry.len % entry.colspan)) else 0))
            self.h = 1 if rofs else len(entry.content)
            #boolean indicating if the cell has a border
            self.bottom = (rofs == entry.rowspan - 1)
            self.right = (cofs == entry.colspan - 1)

    nrows = int(table_node.attr('rows'))
    ncols = int(table_node.attr('cols'))
    table = [None] * nrows
    for row in range(nrows):
        table[row] = [None] * ncols

    #parse the content of each cell into a list of list indexed by [row][col]
    for nrow, row_node in enumerate(table_node.find_children('row')):
        ncol = 0
        for entry_node in row_node.find_children('entry'):
            while table[nrow][ncol] is not None: ncol += 1
            entry = _Entry(entry_node)
            for r in range(entry.rowspan):
                for c in range(entry.colspan):
                    table[nrow + r][ncol + c] = _Cell(entry, r, c)
            ncol += entry.colspan

    col_widths = [ max(cell.w for cell in col) for col in zip(*table) ]
    row_heights = [ max(cell.h for cell in row) for row in table ]
    has_header = all(cell.entry.thead for cell in table[0])
    top_sep_line = '+' + '+'.join(('-' * (w + 2)) for w in col_widths) + '+'
    lines = [ top_sep_line ]
    for nrow, row in enumerate(table):
        for nsubrow in range(row_heights[nrow]):
            subrow_line = '|'
            for ncol, cell in enumerate(row):
                if not cell.cofs:
                    n = sum(col_widths[ncol + c] for c in range(cell.entry.colspan)) + 3 * (cell.entry.colspan - 1)
                    if nsubrow < cell.h and not cell.rofs:
                        subrow_line += ' ' + cell.entry.content[nsubrow].ljust(n + 1)
                    else:
                        subrow_line += ' ' * (n + 2)

                if cell.right:
                    subrow_line += '|'

            assert len(subrow_line) == len(top_sep_line)
            lines.append(subrow_line)

        sep_line = ''
        previous_cell_bottom = True
        row_sep = '=' if has_header and not nrow else '-'
        for ncol, cell in enumerate(row):
            sep_line += '+' if previous_cell_bottom or cell.bottom else ' '
            previous_cell_bottom = cell.bottom
            sep_line += (row_sep if cell.bottom else ' ') * (col_widths[ncol] + 2)

        sep_line += '+'
        assert len(sep_line) == len(top_sep_line)
        lines.append(sep_line)

    return lines


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


_ref_to_scoped_name_cache = {}

def _dox_ref_to_scoped_name(ref_node):
    ref_id = ref_node.attr('refid')

    result = _ref_to_scoped_name_cache.get(ref_id, None)
    if result is not None:
        return result

    dox_index = ref_node.index()
    result = None
    if ref_node.attr('kindref') == 'compound':
        for cpd_node in dox_index.find_children('compound'):
            if cpd_node.attr('refid') == ref_id:
                result = cpd_node.child_text('name')
                break
    else: #member search
        for cpd_node in dox_index.find_children('compound'):
            for mb_node in cpd_node.find_children('member'):
                if mb_node.attr('refid') == ref_id:
                    if cpd_node.attr('kind') in ('class', 'struct', 'union', 'namespace'):
                        result = cpd_node.child_text('name') + '::' + mb_node.child_text('name')
                    else:
                        result = mb_node.child_text('name')
                    break

    if result is None:
        result = ref_node.text()
    _ref_to_scoped_name_cache[ref_id] = result

    return result


def get_type_signature(dox_type_node):
    t = []
    for n in dox_type_node.children():
        if n.nodeType == Element.TEXT_NODE:
            t.append(n.nodeValue)
        elif n.nodeType == Element.ELEMENT_NODE:
            if n.tagName == 'ref':
                scoped_name = _dox_ref_to_scoped_name(n)
                t.append(scoped_name)

    s = ''.join(t)
    s = s.replace('constexpr', '')
    s = s.replace(' ', '')
    return s


def get_fct_arg_signature(dox_fct_node):
    return ','.join(get_type_signature(param_node.find_child('type'))
                    for param_node in dox_fct_node.find_children('param'))
