import inspect
import logging
import threading
from typing import Any, Callable, Dict, List, Tuple, TypeVar, Union

from stevedore import ExtensionManager

from .core import Plugin, PluginLifecycleListener, PluginSpec

LOG = logging.getLogger(__name__)

T = TypeVar("T")


def _call_safe(func: Callable, args: Tuple, exception_message: str):
    """
    Call the given function with the given arguments, and if it fails, log the given exception_message.
    If loggin.DEBUG is set for the logger, then we also log the traceback.

    :param func: function to call
    :param args: arguments to pass
    :param exception_message: message to log on exception
    :return: whatever the func returns
    """
    try:
        return func(*args)
    except Exception as e:
        if LOG.isEnabledFor(logging.DEBUG):
            LOG.exception(exception_message)
        else:
            LOG.error("%s: %s", exception_message, e)


class PluginLifecycleNotifierMixin:
    """
    Mixin that provides functions to dispatch calls to a PluginLifecycleListener in a safe way.
    """

    listener: PluginLifecycleListener

    def _fire_on_resolve_after(self, plugin_spec):
        _call_safe(
            self.listener.on_resolve_after,
            (plugin_spec,),  #
            "error while calling on_import_after",
        )

    def _fire_on_resolve_exception(self, namespace, entrypoint, exception):
        _call_safe(
            self.listener.on_resolve_exception,
            (namespace, entrypoint, exception),
            "error while calling on_resolve_exception",
        )

    def _fire_on_init_after(self, plugin):
        _call_safe(
            self.listener.on_init_after,
            (plugin,),  #
            "error while calling on_init_after",
        )

    def _fire_on_init_exception(self, plugin_spec, exception):
        _call_safe(
            self.listener.on_init_exception,
            (plugin_spec, exception),
            "error while calling on_init_exception",
        )

    def _fire_on_load_before(self, plugin, load_args, load_kwargs):
        _call_safe(
            self.listener.on_load_before,
            (plugin, load_args, load_kwargs),
            "error while calling on_load_before",
        )

    def _fire_on_load_after(self, plugin, result):
        _call_safe(
            self.listener.on_load_after,
            (plugin, result),
            "error while calling on_load_after",
        )

    def _fire_on_load_exception(self, plugin, exception):
        _call_safe(
            self.listener.on_load_exception,
            (plugin, exception),
            "error while calling on_load_exception",
        )


class ManagedPlugin:
    """
    Object to pass around the plugin state inside a PluginLoader.
    """

    lock: threading.Lock
    plugin_spec: PluginSpec
    plugin: Plugin = None
    load_value: Any = None
    is_loaded: bool = False


class PluginSpecResolver:

    def resolve(self, source: Any) -> PluginSpec:
        """
        Tries to create a PluginSpec from the given source.
        :param source: anything that represents a PluginSpec
        :return: a PluginSpec instance
        """
        if isinstance(source, PluginSpec):
            return source

        if inspect.isclass(source):
            if issubclass(source, Plugin):
                return PluginSpec(source.namespace, source.name, source)
            # TODO: check for @spec wrapper

        if inspect.ismethod(source):
            spec = source()
            if isinstance(spec, PluginSpec):
                return spec

        raise ValueError("cannot resolve plugin specification from %s" % source)


class PluginManager(PluginLifecycleNotifierMixin):
    """
    Manages Plugins discovered from importlib EntryPoints using stevedore.ExtensionManager.
    """

    namespace: str

    load_args: Union[List, Tuple]
    load_kwargs: Dict[str, Any]
    listener: PluginLifecycleListener

    def __init__(
            self,
            namespace: str,
            load_args: Union[List, Tuple] = None,
            load_kwargs: Dict = None,
            listener: PluginLifecycleListener = None,
    ):
        self.namespace = namespace

        self.load_args = load_args or list()
        self.load_kwargs = load_kwargs or dict()
        self.listener = listener or PluginLifecycleListener()
        self._plugins: Dict[str, ManagedPlugin] = self._import_plugins()
        self.spec_resolver = PluginSpecResolver()

    @property
    def imported(self) -> List[PluginSpec]:
        return [holder.plugin_spec for holder in self._plugins.values()]

    @property
    def imported_names(self) -> List[str]:
        return [holder.plugin_spec.name for holder in self._plugins.values()]

    def exists(self, name: str) -> bool:
        return name in self._plugins

    def is_loaded(self, name: str) -> bool:
        return self._require_plugin(name).is_loaded

    def map_load(self, func: Callable[[ManagedPlugin], T]) -> List[T]:
        return [func(plugin) for plugin in self.load_all()]

    def load(self, name: str) -> ManagedPlugin:
        holder = self._require_plugin(name)

        if not holder.is_loaded:
            self._load_plugin(holder)

        if holder.is_loaded:
            return holder

        # FIXME: this API is awkward, since it returns None if the plugin exists but wasn't loaded. however raising
        #  an exception would also be weird, as the lifecycle listener already takes care of that, and it would be
        #  completely different behavior from load_all

    def load_all(self) -> List[ManagedPlugin]:
        plugins = list()

        for name, holder in self._plugins.items():
            if not holder.is_loaded:
                self._load_plugin(holder)

            if holder.is_loaded:
                plugins.append(holder)

        return plugins

    def _require_plugin(self, name: str) -> ManagedPlugin:
        if name not in self._plugins:
            raise ValueError("no plugin named %s in namespace %s" % (name, self.namespace))
        return self._plugins[name]

    def _load_plugin(self, holder: ManagedPlugin):
        with holder.lock:
            if holder.plugin is None:
                # instantiate Plugin from spec
                try:
                    LOG.debug("instantiating plugin %s", holder.plugin_spec)
                    holder.plugin = holder.plugin_spec.factory()
                    self._fire_on_init_after(holder.plugin)
                except Exception as e:
                    if LOG.isEnabledFor(logging.DEBUG):
                        LOG.exception("error instantiating plugin %s", holder.plugin_spec)
                    self._fire_on_init_exception(holder.plugin_spec, e)
                    return

            plugin = holder.plugin

            if plugin.should_load():
                LOG.debug("not loading deactivated plugin %s", holder.plugin_spec)
                return

            args = self.load_args
            kwargs = self.load_kwargs

            self._fire_on_load_before(plugin, args, kwargs)
            try:
                LOG.debug("loading plugin %s:%s", self.namespace, holder.plugin_spec.name)
                result = plugin.load(*args, *kwargs)
                self._fire_on_load_after(plugin, result)
                holder.load_value = result
                holder.is_loaded = True
            except Exception as e:
                if LOG.isEnabledFor(logging.DEBUG):
                    LOG.exception("error loading plugin %s", holder.plugin_spec)
                self._fire_on_load_exception(plugin, e)

    def _import_plugins(self) -> Dict[str, ManagedPlugin]:
        def on_load_failure_callback(_mgr, entrypoint, exception):
            self._fire_on_resolve_exception(self.namespace, entrypoint, exception)

        def ext_to_plugin(ext) -> ManagedPlugin:
            try:
                spec = self.spec_resolver.resolve(ext)
            except Exception as exception:
                self._fire_on_resolve_exception(self.namespace, ext.entrypoint, exception)
                return ManagedPlugin

            self._fire_on_resolve_after(spec)

            holder = ManagedPlugin()
            holder.lock = threading.Lock()
            holder.plugin_spec = spec

            return holder

        manager = ExtensionManager(
            self.namespace,
            invoke_on_load=False,
            on_load_failure_callback=on_load_failure_callback,
        )
        return manager.map(ext_to_plugin)
