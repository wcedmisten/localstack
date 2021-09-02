import abc
import inspect
from collections import defaultdict
from typing import Dict, List, NamedTuple

from .core import PluginSpec


class EntryPoint(NamedTuple):
    name: str
    value: str
    group: str


EntryPointDict = Dict[str, List[str]]


def to_entry_point_dict(eps: List[EntryPoint]) -> EntryPointDict:
    result = defaultdict(list)
    for ep in eps:
        result[ep.group].append("%s=%s" % (ep.name, ep.value))
    return result


def spec_to_entry_point(spec: PluginSpec) -> EntryPoint:
    module = inspect.getmodule(spec.factory)
    name = spec.factory.__name__
    path = f"{module}:{name}"
    return EntryPoint(group=spec.namespace, name=spec.name, value=path)


class PluginCollector(abc.ABC):
    def get_entry_points(self) -> EntryPointDict:
        """
        Creates a dictionary for the entry_points attribute of setuptools' setup(), where keys are
        stevedore plugin namespaces, and values are lists of "name = module:object" pairs.

        :return: an entry_point dictionary
        """
        return to_entry_point_dict([spec_to_entry_point(spec) for spec in self.collect_plugins()])

    def collect_plugins(self) -> List[PluginSpec]:
        raise NotImplementedError
