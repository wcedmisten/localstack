import abc
from typing import Any, Callable, Dict, List, Tuple, Type, TypeVar, Union


class Plugin(abc.ABC):
    """A generic LocalStack plugin.

    A Plugin's primary function is to make it easy to be discovered, and to defer code imports into the Plugin::load
    method. Abstract subtypes of plugins (e.g., a LocalstackCliPlugin) may hook into

    Internally a Plugin is a wrapper around a setuptools EntryPoint. An entrypoint is a tuple: name, module:object
    inside a namespace that can be loaded. The entrypoint object of a LocalStack Plugin should always point to
    Plugin.__init__ (the constructor of the Plugin). Meaning that, loading the entry point is equivalent to
    instantiating the Plugin. A PluginLoader will then run the Plugin::load method.
    """

    namespace: str
    name: str
    requirements: List[str]

    def is_active(self) -> bool:
        # FIXME: remove after release (would currently break localstack-ext)
        return self.should_load()

    def should_load(self) -> bool:
        return True

    def load(self, *args, **kwargs):
        """
        Called by a PluginLoader when it loads the Plugin.
        """
        return None


P = TypeVar("P", bound=Plugin)
PluginType = Type[Plugin]
PluginFactory = Callable[[], Plugin]


class PluginSpec:
    namespace: str
    name: str
    factory: PluginFactory
    metadata: Dict[str, Any]
    requirements: List[str]

    def __init__(
        self,
        namespace: str,
        name: str,
        factory: PluginFactory,
        metadata: Dict[str, Any] = None,
        requirements: List[str] = None,
    ) -> None:
        super().__init__()
        self.namespace = namespace
        self.name = name
        self.factory = factory
        self.requirements = requirements or []
        self.metadata = metadata or {}


class PluginLifecycleListener:
    def on_resolve_exception(self, namespace: str, entrypoint, exception: Exception):
        pass

    def on_resolve_after(self, plugin_spec: PluginSpec):
        pass

    def on_init_exception(self, plugin_spec: PluginSpec, exception: Exception):
        pass

    def on_init_after(self, plugin: Plugin):
        pass

    def on_load_before(self, plugin: Plugin, load_args: Union[List, Tuple], load_kwargs: Dict):
        pass

    def on_load_after(self, plugin: Plugin, load_result: Any = None):
        pass

    def on_load_exception(self, plugin: Plugin, exception: Exception):
        pass
