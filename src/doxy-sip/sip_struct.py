# SPDX-License-Identifier: BSD-3-Clause

# Copyright (c) 2026 C. Savergne <csavergne@yahoo.com>


import os
from sipbuild.generator.outputs.formatters import (
    fmt_class_as_type_hint, fmt_argument_as_type_hint,
    fmt_signature_as_type_hint, fmt_scoped_py_name)
from sipbuild.generator.specification import (
    AccessSpecifier, ArgumentType, ArrayArgument, CachedName,
    Docstring, EnumBaseType, PyQtMethodSpecifier, PySlot, Signature)
from sipbuild.generator.python_slots import is_number_slot, reflected_slot
from sipbuild.generator.scoped_name import STRIP_NONE, STRIP_GLOBAL
from sipbuild import AbstractProject
from sipbuild.version import SIP_VERSION
from sipbuild.generator import parse, resolve


class SIP_Constructor:

    def __init__(self, spec, klass, ctor):
        self._spec = spec

        self.cpp_arg_signature = signature_as_cpp_declaration(spec, ctor.cpp_signature)
        self.py_signature = ctor.py_signature
        self.docstring = ctor.docstring.text if ctor.docstring is not None else None
        self.has_method_code = ctor.method_code is not None
        self.is_default = klass.default_ctor is ctor


    def py_declaration(self):
        arg_decl = fmt_signature_as_type_hint(self._spec,
                                              self.py_signature,
                                              need_self=True,
                                              defined=None)

        decl = f'__init__{arg_decl}'
        return decl


class SIP_Overload:

    def __init__(self, spec, ovr):
        self._spec = spec

        self.py_name = ovr.common.py_name.name
        self.cpp_name = ovr.cpp_name
        self.is_const = ovr.is_const
        self.is_static = ovr.is_static
        self.is_deprecated = ovr.deprecated
        self.is_reflected = ovr.is_reflected
        self.is_virtual = ovr.is_virtual
        self.is_abstract = ovr.is_abstract
        self.py_slot = ovr.common.py_slot
        self.result_type = argument_as_cpp_type(spec, ovr.cpp_signature.result)
        self.cpp_arg_signature = signature_as_cpp_declaration(spec, ovr.cpp_signature)
        self.py_signature = ovr.py_signature
        self.docstring = ovr.docstring
        self.has_method_code = ovr.method_code is not None


    def py_declaration(self):
        if self.py_slot:
            if self.py_slot in (PySlot.EQ, PySlot.NE):
                arg_decl = '(self, other: object)'

            elif is_number_slot(self.py_slot):
                # Use the reflected name if appropriate.
                if self.is_reflected:
                    py_name = reflected_slot(self.py_slot)

                # A global slot will still have both arguments so pick the relevant
                # one.
                py_signature = self.py_signature
                if len(py_signature.args) > 1:
                    if self.is_reflected:
                        arg = py_signature.args[0]
                    else:
                        arg = py_signature.args[1]

                    py_signature = Signature(args=[arg], result=py_signature.result)

                arg_decl = fmt_signature_as_type_hint(self._spec,
                                                  py_signature,
                                                  need_self=True,
                                                  defined=None)

            else:
                arg_decl = fmt_signature_as_type_hint(self._spec,
                                                      self.py_signature,
                                                      need_self=not self.is_static,
                                                      defined=None)

        else:

            arg_decl = fmt_signature_as_type_hint(self._spec,
                                                  self.py_signature,
                                                  need_self=not self.is_static,
                                                  defined=None)

        decl = (f'{self.py_name}{arg_decl}')

        return decl


class SIP_Callable:

    def __init__(self, spec, klass, member):
        self.name = member.py_name.name

        is_eq_slot = member.py_slot in (PySlot.EQ, PySlot.NE)

        # Filter and order overloads (non-reflected first)
        nonreflected_overloads = []
        reflected_overloads = []
        first_eq_slot = True
        for overload in klass.overloads:
            if overload.access_specifier is AccessSpecifier.PRIVATE: continue
            if overload.common is not member: continue
            if overload.pyqt_method_specifier is PyQtMethodSpecifier.SIGNAL: continue

            if is_eq_slot:
                if not first_eq_slot: break
                first_eq_slot = False

            if is_number_slot(overload.common.py_slot) and overload.is_reflected:
                reflected_overloads.append(overload)
            else:
                nonreflected_overloads.append(overload)

        declared_overloads = nonreflected_overloads + reflected_overloads

        #Create the SIP_Overload object for each overload
        self.overloads = []
        for overload in declared_overloads:
            doc_ovr = SIP_Overload(spec, overload)
            self.overloads.append(doc_ovr)


#Copied from sipbuild, because doxygen uses 'unsigned int' and not uint
def _fmt_argument_as_cpp_type(spec, arg, scope=None,
        strip=STRIP_NONE, make_public=False, use_typename=True, plain=False,
        no_derefs=False, as_xml=False):
    """ Return an argument as a C++ type. """

    original_typedef = arg.original_typedef
    nr_derefs = 0 if no_derefs else len(arg.derefs)
    is_const = arg.is_const and not plain
    is_reference = arg.is_reference and not plain

    s = ''

    if use_typename and original_typedef is not None and not original_typedef.no_type_name and arg.array is not ArrayArgument.ARRAY_SIZE:
        # Reverse the previous expansion of the typedef.
        if is_const and not original_typedef.type.is_const:
            s += 'const '

        nr_derefs -= len(original_typedef.type.derefs)

        if original_typedef.type.is_reference:
            is_reference = False

        s += original_typedef.fq_cpp_name.cpp_stripped(strip)

    else:
        # A function type is handled differently because of the position of the
        # name.
        if arg.type is ArgumentType.FUNCTION:
            s += _fmt_argument_as_cpp_type(spec, arg.definition.result,
                    scope=scope, strip=strip, as_xml=as_xml)

            s += ' (' + '*' * nr_derefs + name + ')('

            s += signature_as_cpp_declaration(spec, arg.definition)

            s += ')'

            return s

        if is_const:
            s += 'const '

        if arg.type in (ArgumentType.SBYTE, ArgumentType.SSTRING):
            s += 'signed char'

        elif arg.type in (ArgumentType.UBYTE, ArgumentType.USTRING):
            s += 'unsigned char'

        elif arg.type is ArgumentType.WSTRING:
            s += 'wchar_t'

        elif arg.type in (ArgumentType.BYTE, ArgumentType.ASCII_STRING, ArgumentType.LATIN1_STRING, ArgumentType.UTF8_STRING, ArgumentType.STRING):
            s += 'char'

        elif arg.type is ArgumentType.USHORT:
            s += 'unsigned short'

        elif arg.type is ArgumentType.SHORT:
            s += 'short'

        elif arg.type is ArgumentType.UINT:
            s += 'unsigned int'

        elif arg.type in (ArgumentType.INT, ArgumentType.CINT):
            s += 'int'

        elif arg.type is ArgumentType.HASH:
            s += 'Py_hash_t'

        elif arg.type is ArgumentType.SSIZE:
            s += 'Py_ssize_t'

        elif arg.type is ArgumentType.SIZE:
            s += 'size_t'

        elif arg.type is ArgumentType.ULONG:
            s += 'unsigned long'

        elif arg.type is ArgumentType.LONG:
            s += 'long'

        elif arg.type is ArgumentType.ULONGLONG:
            s += 'unsigned long long'

        elif arg.type is ArgumentType.LONGLONG:
            s += 'long long'

        elif arg.type is ArgumentType.STRUCT:
            s += 'struct ' + arg.definition.as_cpp

        elif arg.type is ArgumentType.UNION:
            s += 'union ' + arg.definition.as_cpp

        elif arg.type is ArgumentType.CAPSULE:
            nr_derefs = 1
            s += 'void'

        elif arg.type in (ArgumentType.FAKE_VOID, ArgumentType.VOID):
            s += 'void'

        elif arg.type in (ArgumentType.BOOL, ArgumentType.CBOOL):
            s += 'bool'

        elif arg.type in (ArgumentType.FLOAT, ArgumentType.CFLOAT):
            s += 'float'

        elif arg.type in (ArgumentType.DOUBLE, ArgumentType.CDOUBLE):
            s += 'double'

        elif arg.type is ArgumentType.DEFINED:
            # The only defined types still remaining are arguments to templates
            # and default values.
            if as_xml:
                s += arg.definition.as_py
            else:
                if spec.c_bindings:
                    s += 'struct '

                s += arg.definition.cpp_stripped(strip)

        elif arg.type is ArgumentType.MAPPED:
            s += _fmt_argument_as_cpp_type(spec, arg.definition.type,
                    scope=scope, strip=strip, as_xml=as_xml)

        elif arg.type is ArgumentType.CLASS:
            from sipbuild.generator.outputs.formatters.klass import fmt_class_as_scoped_name

            if spec.c_bindings:
                s += 'union ' if arg.definition.class_key is ClassKey.UNION else 'struct '

            s += fmt_class_as_scoped_name(spec, arg.definition, scope=scope,
                    strip=strip, make_public=make_public, as_xml=as_xml)

        elif arg.type is ArgumentType.TEMPLATE:
            from sipbuild.generator.outputs.formatters.template import fmt_template_as_cpp_type

            s += fmt_template_as_cpp_type(spec, arg.definition, strip=strip,
                    as_xml=as_xml)

        elif arg.type is ArgumentType.ENUM:
            from sipbuild.generator.outputs.formatters.enum import fmt_enum_as_cpp_type

            s += fmt_enum_as_cpp_type(arg.definition, make_public=make_public,
                    strip=strip)

        elif arg.type in (ArgumentType.PYOBJECT, ArgumentType.PYTUPLE, ArgumentType.PYLIST, ArgumentType.PYDICT, ArgumentType.PYCALLABLE, ArgumentType.PYSLICE, ArgumentType.PYTYPE, ArgumentType.PYBUFFER, ArgumentType.PYENUM, ArgumentType.ELLIPSIS):
            s += 'PyObject *'

    for i in range(nr_derefs):
        # Doxygen only puts a space before the first *
        if not i:
            s += ' '
        s += '*'

        if arg.derefs[i]:
            s += ' const'

    if is_reference:
        s += ' &'

    return s


def argument_as_cpp_type(spec, arg):
    return _fmt_argument_as_cpp_type(spec, arg, strip=STRIP_GLOBAL)


def signature_as_cpp_declaration(spec, cpp_signature):
    args = [_fmt_argument_as_cpp_type(spec, arg, strip=STRIP_GLOBAL)
            for arg in cpp_signature.args]
    return ', '.join(args)


def signature_as_result_type_hint(spec, py_signature):
    '''Returns the signature type hint for the result
    Snippet from sipbuild's fmt_signature_as_type_hint()'''

    nr_out = sum(1 for arg in py_signature.args if arg.is_out)

    # Handle the output values.
    result = py_signature.result

    if result is None or (result.type is ArgumentType.VOID and len(result.derefs) == 0):
        is_result = False
    else:
        type_hints = result.type_hints

        # An empty type hint specifies a void return.
        if type_hints is not None and type_hints.hint_out is not None and type_hints.hint_out == '':
            is_result = False
        else:
            is_result = True

    if is_result or nr_out > 0:
        out_args = []

        if is_result:
            type_hint = fmt_argument_as_type_hint(spec, result, None)
            if type_hint:
                out_args.append(type_hint)

        for arg in py_signature.args:
            if arg.is_out:
                type_hint = fmt_argument_as_type_hint(spec, arg, None)
                if type_hint:
                    out_args.append(type_hint)

        results_s = ', '.join(out_args)

        if (is_result and nr_out > 0) or nr_out > 1: #needs_tuplr
            results_s = f'({results_s})'

        return results_s

    else:
        return 'None'


def get_sip_spec(domain, sip_module_name):
    specs = domain.data['sip_specs']

    if not domain.data['sip_project_loaded']:
        domain.data['sip_project_loaded'] = True

        sip_project_dir = domain.env.app.config.sip_toml_project
        sip_project_dir = os.path.abspath(sip_project_dir)

        oldcwd = os.getcwd()
        try:
            os.chdir(sip_project_dir)
        except FileNotFoundError:
            raise Exception("Cannot load SIP project from " + sip_project_dir + ' (' + oldcwd + ')')

        try:
            prj = AbstractProject.bootstrap('doc')
        finally:
            os.chdir(oldcwd)

        # Get the list of directories to search for .sip files.
        sip_include_dirs = list(prj.sip_include_dirs)
        if prj.sip_module:
            sip_include_dirs.append(prj.sip_files_dir)

        for bindings in prj.bindings.values():

            sip_file_path = os.path.join(sip_project_dir, bindings.sip_file)
            spec, modules, _ = parse(sip_file_path,
                                     SIP_VERSION,
                                     'UTF-8',
                                     prj.target_abi,
                                     bindings.tags,
                                     bindings.disabled_features,
                                     bindings.protected_is_public,
                                     sip_include_dirs,
                                     prj.sip_module)

            # Resolve the types.
            resolve(spec, modules)

            specs[spec.module.fq_py_name.name] = spec

    #Check if the specification is already loaded, it should be in the cache
    spec = specs.get(sip_module_name, None)
    if spec is None:
        raise ValueError('module name ' + sip_module_name + ' is unkown')

    return spec


def get_sip_klass(spec, klass_name):
    for k in spec.classes:
        if get_scoped_py_name(spec, k) == klass_name:
            return k
    return None


def get_sip_enum(spec, enum_name):
    for e in spec.enums:
        if get_scoped_py_name(spec, e) == enum_name:
            return e
    return None


def get_sip_class_property(spec, name):
    for k in spec.classes:
        for p in k.properties:
            if get_scoped_py_name(spec, k) + '.' + p.name.name == name:
                return k, p
    return None, None


def render_docstring(docstring):
    if docstring is None:
        return []
    s = docstring if isinstance(docstring, str) else docstring.text
    s = s.strip(' \n')
    return [s]


def render_superclasses(spec, klass):
    if klass.superclasses:
        return [ fmt_class_as_type_hint(spec, sc, None) for sc in klass.superclasses ]
    else:
        return []


def get_scoped_py_name(spec, klass):
    return fmt_scoped_py_name(klass.scope, klass.py_name.name)

