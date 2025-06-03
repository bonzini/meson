# Mostly based on dacite
#
# Copyright (c) 2018 Konrad Hałas

from __future__ import annotations
import typing as T

from dataclasses import InitVar, is_dataclass
from functools import lru_cache

if T.TYPE_CHECKING:
    from .._typing import DataclassInstance

def extract_origin_collection(collection: T.Type) -> T.Type:
    try:
        return T.cast('T.Type', collection.__extra__)
    except AttributeError:
        return T.cast('T.Type', collection.__origin__)


def is_generic(type_: T.Type) -> bool:
    return hasattr(type_, "__origin__")


def is_union(type_: T.Type) -> bool:
    if is_generic(type_) and type_.__origin__ == T.Union:
        return True

    try:
        from types import UnionType

        return isinstance(type_, UnionType)
    except ImportError:
        return False


def is_tuple(type_: T.Type) -> bool:
    return is_subclass(type_, tuple)


def is_typed_dict(type_: T.Type) -> bool:
    return hasattr(type_, "__orig_bases__") and T.TypedDict in type_.__orig_bases__


def is_literal(type_: T.Type) -> bool:
    return is_generic(type_) and type_.__origin__ == T.Literal


def is_required(type_: T.Type) -> bool:
    return is_generic(type_) and type_.__origin__ == T.Required


def is_new_type(type_: T.Type) -> bool:
    return hasattr(type_, "__supertype__")


def extract_new_type(type_: T.Type) -> T.Type:
    return T.cast('T.Type', type_.__supertype__)


def is_init_var(type_: T.Type) -> bool:
    return isinstance(type_, InitVar) or type_ is InitVar


def extract_init_var(type_: T.Type) -> T.Union[T.Type, T.Any]:
    try:
        return type_.type
    except AttributeError:
        return T.Any


def is_generic_collection(type_: T.Type) -> bool:
    if not is_generic(type_):
        return False
    origin = extract_origin_collection(type_)
    try:
        return bool(origin and issubclass(origin, T.Collection))
    except (TypeError, AttributeError):
        return False


def extract_generic(type_: T.Type, defaults: T.Tuple = ()) -> T.Tuple:
    try:
        if getattr(type_, "_special", False):
            return defaults
        if type_.__args__ == ():
            return (type_.__args__,)
        return type_.__args__ or defaults
    except AttributeError:
        return defaults


def is_subclass(sub_type: T.Type, base_type: T.Type) -> bool:
    if is_generic_collection(sub_type):
        sub_type = extract_origin_collection(sub_type)
    try:
        return issubclass(sub_type, base_type)
    except TypeError:
        return False


def is_type(type_: T.Type) -> bool:
    try:
        return type_.__origin__ in (type, T.Type)
    except AttributeError:
        return False


def typeddict_validator(type_: T.Type) -> T.Callable[[object], bool]:
    required_keys = {k for k, v in T.get_type_hints(type_, include_extras=True).items()
                     if is_required(v)}
    hints = T.get_type_hints(type_)
    validators = {k: validator(hint) for k, hint in hints.items()}
    if type_.__total__:
        return lambda value: isinstance(value, T.Mapping) and \
            all(k in value for k in required_keys) and \
            all(k in validators and validators[k](v) for k, v in value.items())
    else:
        return lambda value: isinstance(value, T.Mapping) and \
            all(k in value for k in required_keys) and \
            all(k not in validators or validators[k](v) for k, v in value.items())


VALIDATORS: T.Dict[T.Type, T.Callable[[object], bool]] = dict()

def validator(type_: T.Type) -> T.Callable[[object], bool]:
    def get_validator(type_: T.Type) -> T.Callable[[object], bool]:
        if type_ == T.Any: # type: ignore
            return lambda value: True

        if is_union(type_):
            validators = [validator(t) for t in extract_generic(type_)]
            return lambda value: any(v(value) for v in validators)

        if is_typed_dict(type_):
            return typeddict_validator(type_)

        if is_new_type(type_):
            return validator(extract_new_type(type_))
        if is_literal(type_):
            generic = extract_generic(type_)
            return lambda value: value in generic
        if is_init_var(type_):
            return validator(extract_init_var(type_))

        if is_generic_collection(type_):
            origin = extract_origin_collection(type_)
            generic = extract_generic(type_)
            if not generic:
                return lambda value: isinstance(value, origin)

            if issubclass(origin, T.Mapping):
                key_type, val_type = extract_generic(type_, defaults=(T.Any, T.Any))
                kv = validator(key_type)
                vv = validator(val_type)
                return lambda value: isinstance(value, origin) and all(kv(k) and vv(v) for k, v in value.items())

            elif is_tuple(type_):
                if len(generic) == 1 and generic[0] == ():
                    return lambda value: isinstance(value, origin) and not value
                if len(generic) == 2 and generic[1] is ...:
                    v = validator(generic[0])
                    return lambda value: isinstance(value, origin) and all(v(item) for item in value)
                validators = [validator(t) for t in generic]
                return lambda value: \
                    isinstance(value, origin) and len(value) == len(validators) \
                    and all(v(item) for item, v in zip(value, validators))

            field_type = extract_generic(type_, defaults=(T.Any,))[0]
            v = validator(field_type)
            return lambda value: isinstance(value, origin) and all(v(item) for item in value)

        if is_type(type_):
            generic = extract_generic(type_)
            if not generic:
                return lambda value: isinstance(value, type)

            return lambda value: isinstance(value, type) and issubclass(value, generic[0])

        if is_dataclass(type_):
            return lambda value: isinstance(value, type_)

        if type_ is complex:
            return lambda value: isinstance(value, (int, float, complex))
        elif type_ is float:
            return lambda value: isinstance(value, (int, float))
        else:
            return lambda value: isinstance(value, type_)

    if type_ not in VALIDATORS:
        VALIDATORS[type_] = get_validator(type_)
    return VALIDATORS[type_]


@lru_cache(maxsize=None)
def dataclass_field_validators(type_: T.Type[DataclassInstance]) -> T.Dict[str, T.Callable[[object], bool]]:
    hints = T.get_type_hints(type_)
    return {k: validator(hint) for k, hint in hints.items()}
