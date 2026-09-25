# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>

import dataclasses

from . import sip_struct
from . import dox_struct


def _get_dox_index(domain):
    dox_dir = domain.env.app.config.sip_doxygen_project
    dox_dir = os.path.abspath(dox_dir)

    dox_index = domain.data['sip_dox_index']
    if dox_index is None:
        index_path = os.path.join(dox_dir, 'index.xml')
        dox_index = xml_parse(index_path)
        domain.data['sip_dox_index'] = dox_index

    return dox_struct.DoxElement(dox_index.documentElement)


def find_dox_for_sip_class(spec, domain, sip_klass):
    dox_index = _get_dox_index(domain)

    if sip_klass.scope is None:
        for node in root.find_children('compound'):
            if sip_klass.class_key is None:
                if node.attr('kind') != 'namespace': continue
            else:
                if node.attr('kind') not in ('class', 'struct'): continue

        sip_scoped_name = sip_klass.iface_file.fq_cpp_name


        refid = node.attr('refid')
        fn = os.path.join(dox_dir, refid + '.xml')
        klass_xmldoc = xml_parse(fn)

        element = DoxElement(klass_xmldoc.documentElement)
        return element.find_child('compounddef')

    return None


def _find_dox_member_by_kind(dox_klass, kind, predicate=None):
    member = None
    if dox_klass is not None:
        for m in dox_klass.getElementsByTagName('memberdef'):
            if m.attr('kind') != kind: continue
            if predicate is not None and not predicate(m): continue
            #if member is not None:
            #    raise ValueError('Multiple member match')
            member = m

    return member



SLOT_MAPPING = {
    'or': '|',
    'and': '&',
    'xor': '^',
    'invert': '~',
    'add': '+',
    'sub': '-',
    'mul': '*',
    'truediv': '/',
    'mod': '%',
    'pos': '+',
    'neg': '-',
    'lshift': '<<',
    'rshift': '>>',
    'ior': '|=',
    'iand': '&=',
    'ixor': '^=',
    'iadd': '+=',
    'isub': '-=',
    'imul': '*=',
    'itruediv': '/=',
    'imod': '%=',
    'ilshift': '<<=',
    'irshift': '>>=',
    'call': '()',
    'getitem': '[]',
    'eq': '==',
    'ne': '!=',
    'lt': '<',
    'le': '<=',
    'gt': '>',
    'ge': '>=',
}

def _py_slot_to_cpp_name(py_slot_name):
    py_name = py_slot_name.strip('_')
    cpp_op = SLOT_MAPPING.get(py_name, None)
    if cpp_op is None:
        return None
    return 'operator' + cpp_op


_TAG_MARKER = '\\dox:'

def _parse_docstring(docstring):
    '''Parse the docstring and extract the marker if present and
    leave the rest of the docstring unchanged
    '''

    if docstring is None:
        return '', None

    if not docstring.text:
        return '', []

    tag = ''
    ds_lines = docstring.text.strip(' \t\r\n').split('\n')
    headlines = True
    textlines = []
    for line in ds_lines:
        if headlines and line.startswith(_TAG_MARKER):
            tag = line.replace(_TAG_MARKER, '').lstrip()
        else:
            headlines = False
            textlines.append(line)

    return tag, textlines


def merge_description(sip_docstring, dox_node):
    tag, sip_desc = _parse_docstring(sip_docstring)

    if dox_node is None:
        dox_desc = ''
    else:
        dox_desc = dox_struct.extract_description(dox_node)

    if sip_desc is None:
        if dox_desc:
            merged_desc = dox_desc
        else:
            merged_desc = None
    else:
        if dox_desc:
            if tag == 'prepend':
                merged_desc = dox_desc + [''] + sip_desc
            elif tag == 'append':
                merged_desc = sip_desc + [''] + dox_desc
            else: #discard
                merged_desc = sip_desc
        else:
            merged_desc = sip_desc

    return tag, merged_desc


@dataclasses.dataclass
class FunctionDeclaration:

    name: str|None = None #not for constructors
    signature: str = ''
    description: str|None = None
    arguments: list[tuple[str, str|None]] = dataclasses.field(default_factory=list)
    result: str|None = None
    default: bool = False #for constructors only

    @property
    def documented(self):
        return self.description is not None or \
               any(a[1] is not None for a in self.arguments) or \
               self.result is not None


def _combine_arguments(sip_signature, dox_member, discard_no_desc):
    #Extract the argument declared names from the param nodes
    if dox_member is not None:
        dox_arg_declnames = [ n.child_text('declname') for n in dox_member.find_children('param')]

        #Extract the argument name and description node from the \param tags in the comment
        dox_arg_desc_map = {}
        for n_arg_list in dox_member.getElementsByTagName('parameterlist'):
            if n_arg_list.attr('kind') != 'param': continue
            for n_arg_name, n_arg_desc in zip(n_arg_list.getElementsByTagName('parameternamelist'),
                                              n_arg_list.getElementsByTagName('parameterdescription'),
                                              strict=True):
                name = n_arg_name.child_text('parametername')
                dox_arg_desc_map[name] = n_arg_desc

    else:
        dox_arg_declnames = []
        dox_arg_desc_map = {}

    #Combine the argument metadata from sip and dox into arg_descriptions
    arg_descriptions = []
    for ix, sip_arg in enumerate(sip_signature.args):
        #Replace the argument name in SIP if it's empty
        if sip_arg.name is not None:
            arg_name = sip_arg.name.name
        elif ix < len(dox_arg_declnames):
            arg_name = dox_arg_declnames[ix]
            if arg_name is not None:
                #Modify the signature to let the name appear
                sip_arg.name = sip_struct.CachedName(arg_name)
        else:
            arg_name = None

        if arg_name is not None:
            dox_arg_desc_node = dox_arg_desc_map.get(arg_name, None)
            if dox_arg_desc_node is not None:
                arg_desc = dox_struct.extract_single_line_description(dox_arg_desc_node)
                arg_descriptions.append((arg_name, arg_desc))
            elif not discard_no_desc:
                arg_descriptions.append((arg_name, None))

    return arg_descriptions


def combine_constructors(sip_spec, sip_klass, dox_klass):

    klass_name = sip_klass.py_name.name

    def ctor_match(ctor, m):

        if m.child_text('name') != dox_klass.child_text('compoundname'):
            return False

        dox_args = ', '.join(dox_struct.get_stripped_type(param_node.find_child('type'))
                             for param_node in m.find_children('param'))
        if ctor.cpp_arg_signature != dox_args:
            return False

        return True

    ctor_decl_list = []
    for sip_ctor in sip_klass.ctors:
        if sip_ctor.access_specifier is sip_struct.AccessSpecifier.PRIVATE: continue

        ctor = sip_struct.SIP_Constructor(sip_spec, sip_klass, sip_ctor)

        ctor_decl = FunctionDeclaration()

        #Find the corresponding member node
        dox_ctor = _find_dox_member_by_kind(dox_klass, 'function', lambda m: ctor_match(ctor, m))

        #Description for the overload
        tag, merged_description = merge_description(ctor.docstring, dox_ctor)
        ctor_decl.description = merged_description

        #Try to fill in the missing argument name and description using Doxygen
        #Skip it if there is a docstring with a 'discard' tag
        ctor_decl.arguments = _combine_arguments(ctor.py_signature,
                                                 dox_ctor if tag != 'discard' else None,
                                                 ctor.docstring is not None)

        arg_sig = sip_struct.fmt_signature_as_type_hint(sip_spec,
                                                        ctor.py_signature,
                                                        need_self=False,
                                                        defined=None)
        ctor_decl.signature = f'{klass_name}{arg_sig}'
        ctor_decl.default = ctor.is_default
        ctor_decl_list.append(ctor_decl)

    return ctor_decl_list


def combine_overload(sip_spec, overload, dox_klass):

    if overload.py_slot:
        sip_cpp_name = _py_slot_to_cpp_name(overload.py_name)
    else:
        sip_cpp_name = overload.cpp_name


    def overload_match(m):

        dox_name = m.child_text('name')
        if sip_cpp_name != dox_name:
            return False
        if overload.is_const != (m.attr('const') == 'yes'):
            return False
        if overload.is_static != (m.attr('static') == 'yes'):
            return False

        dox_result_type = dox_struct.get_stripped_type(m.find_child('type'))
        if overload.result_type != dox_result_type:
            return False

        dox_args = ', '.join(dox_struct.get_stripped_type(param_node.find_child('type'))
                             for param_node in m.find_children('param'))
        if overload.cpp_arg_signature != dox_args:
            return False

        return True

    #Find the corresponding member node
    dox_member = _find_dox_member_by_kind(dox_klass, 'function', overload_match)

    fct_decl = FunctionDeclaration(name=overload.py_name)

    #Description for the overload
    tag, overload_description = merge_description(overload.docstring, dox_member)
    fct_decl.description = overload_description

    #Find the argument and result descriptions. Skip if the tag is 'discard'
    if tag != 'discard':
        fct_decl.arguments = _combine_arguments(overload.py_signature,
                                                dox_member,
                                                overload.docstring is not None)
        if dox_member is not None:
            #Find the description of the return value
            for n in dox_member.getElementsByTagName('simplesect'):
                if n.attr('kind') != 'return': continue
                fct_decl.result = dox_struct.extract_single_line_description(n)
                break
    else:
        fct_decl.arguments = _combine_arguments(overload.py_signature, None, True)

    arg_sig = sip_struct.fmt_signature_as_type_hint(sip_spec,
                                                    overload.py_signature,
                                                    need_self=False,
                                                    defined=None)
    fct_decl.signature = f'{overload.py_name}{arg_sig}'

    return fct_decl


#==============================================================================

@dataclasses.dataclass
class EnumDeclaration:
    signature: str
    description: str|None
    members: list[tuple[str, str|None]]|None


def combine_enum(sip_enum, dox_enum):
    superclass = 'int'
    if sip_enum.base_type is sip_struct.EnumBaseType.ENUM:
        superclass = 'enum.Enum'
    elif sip_enum.base_type is sip_struct.EnumBaseType.FLAG:
        superclass = 'enum.Flag'
    elif sip_enum.base_type in (sip_struct.EnumBaseType.INT_ENUM, sip_struct.EnumBaseType.UINT_ENUM):
        superclass = 'enum.IntEnum'
    elif sip_enum.base_type is sip_struct.EnumBaseType.INT_FLAG:
        superclass = 'enum.IntFlag'

    sig = f'{sip_enum.py_name} ({superclass})'

    if dox_enum is None:
        enum_desc = None
    else:
        enum_desc = dox_struct.extract_description(dox_enum)

    members_decl = []
    for member in sip_enum.members:
        desc = None
        if dox_enum is not None:
            for dox_enum_value in dox_enum.find_children('enumvalue'):
                if dox_enum_value.child_text('name') == member.cpp_name:
                    desc = dox_struct.extract_description(dox_enum_value)
                    break
        members_decl.append((member.py_name.name, desc))

    return EnumDeclaration(sig, enum_desc, members_decl)


def combine_class_enum(sip_enum, dox_klass):
    enum_cpp_name = sip_enum.fq_cpp_name.base_name
    enum_match = lambda m : m.child_text('name') == enum_cpp_name
    dox_enum = _find_dox_member_by_kind(dox_klass, 'enum', enum_match)
    return combine_enum(sip_enum, dox_enum)


#==============================================================================

@dataclasses.dataclass
class PropertyDeclaration:
    name: str
    type: str|None
    description: str|None


def combine_property(sip_spec, sip_klass, sip_prop):
    getter_member = None
    for m in sip_klass.members:
        if m.py_name.name == sip_prop.getter:
            getter_member = m
            break

    #Infer the property type from the getter result type
    result_type = None
    if getter_member:
        c = sip_struct.SIP_Callable(sip_spec, sip_klass, getter_member)
        for ovr in c.overloads:
            if not len(ovr.py_signature.args):
                result_type = sip_struct.signature_as_result_type_hint(sip_spec, ovr.py_signature)
                break

    _, description = _parse_docstring(sip_prop.docstring)

    return PropertyDeclaration(sip_prop.name.name, result_type, description)


#==============================================================================


def combine_class_variable_declaration(sip_spec, sip_klass, dox_klass):
    klass_vars = [ v for v in sip_spec.variables
                   if v.module is sip_spec.module and v.scope is sip_klass ]

    klass_decl_list = []
    for v in klass_vars:
        var_py_name = v.py_name.name
        var_cpp_name = v.fq_cpp_name.base_name
        dox_var = _find_dox_member_by_kind(dox_klass, 'variable', lambda m: m.child_text('name') == var_cpp_name)

        var_type = sip_struct.fmt_argument_as_type_hint(sip_spec, v.type, None, None)

        if dox_var is not None:
            description = dox_struct.extract_description(dox_var)
        else:
            description = None

        klass_decl_list.append((var_py_name, var_type, description))

    return klass_decl_list

