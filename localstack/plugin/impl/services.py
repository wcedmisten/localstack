import importlib
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

from localstack.plugin import Plugin, PluginLifecycleListener, PluginSpec
from localstack.plugin.manager import PluginManager

SERVICES: List[str]


class Service:
    pass


class AwsServicePlugin(Plugin):
    service_name: str
    provider_name: str
    module: str

    def should_load(self) -> bool:
        if not self.service_name:
            return False
        return self.service_name in SERVICES

    def load(self) -> Service:
        importlib.import_module(self.module)
        return Service()


AwsServicePluginClass = Type[AwsServicePlugin]


class DynamicServiceRegistry(PluginLifecycleListener):
    def __init__(self):
        self.loader = PluginManager("localstack.aws.services", listener=self)

        self.service_plugins: Dict[str, str] = dict()

        for spec in self.loader.list_imported_specs():
            spec.type.service_name

    def get_service(self, name: str) -> Service:
        if name not in self.service_plugins:
            raise ValueError("no plugin found for service %s" % name)

        if name in self.service_plugin_specs:
            return self.loader.load()
        specs = self.loader.list_imported_specs()

        for spec in specs:
            spec.service_name == name
            return


## concrete services


class S3MotoPlugin(AwsServicePlugin):
    service_name = "s3"
    provider_name = "s3"
    module = "localstack.services.s3"


def AwsProviderSpec(service, *args, **kwargs):
    return PluginSpec(f"localstack.aws.providers.{service}", *args, **kwargs)


def MotoPluginSpec(service, provider, plugin_type):
    return AwsProviderSpec(
        f"localstack.aws.providers.{service}", provider, plugin_type, ["moto-ext"]
    )


class PluginLoader:
    def should_load(self) -> bool:
        return True

    def load(self, *args, **kwargs):
        raise NotImplementedError


class Plugin:
    spec: PluginSpec
    loader: Optional[PluginLoader]
    object: Any
    is_loaded: bool

    @property
    def name(self):
        return self.spec.name

    @property
    def namespace(self):
        return self.spec.name

    def loader_type(self):
        pass


SqsMoto = MotoPluginSpec("sqs", "moto", S3MotoPlugin)
SqsElasticMq = AwsProviderSpec("sqs", "elasticmq", S3MotoPlugin)
