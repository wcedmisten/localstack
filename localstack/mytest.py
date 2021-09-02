import inspect

from localstack.plugin import Plugin, PluginSpec


def plugin(namespace: str, name: str = None):
    def wrapper(cls):
        plugin_name = cls.__name__ if name is not None else name
        print("wrapping class", cls, namespace, plugin_name)
        return cls

    return wrapper


print("defining MySuper")


@plugin("localstack.plugins.cli", "super")
class MySuper:
    def __init__(self):
        print("initializing")

    def load(self):
        print("call mySuper")
        pass


print("defining MySub")


class MySub(MySuper):
    def __init__(self) -> None:
        super().__init__()
        self.foo = "subbed"


def load_cli_plugins(cli):
    manager = PluginManager("localstack.plugins.cli")

    commands = manager.load_all()
    for cmd in commands:
        cli.group.add_command(cmd)


class ServicePlugin(Plugin):
    def should_load(self) -> bool:
        return super().should_load()

    def load(self, *args, **kwargs):
        super().load(*args, **kwargs)


s3 = PluginSpec("localstack.aws.providers.s3", "s3_moto", ServicePlugin)


def main():
    print("now init")
    sub = MySub()

    print(type(sub))
    print(sub.load())
    print(sub.foo)

    fn = sub.load
    fn = fn

    print(inspect.getmodule(fn).__name__, ":", fn.__name__)


class Service:
    def run(self):
        pass


class ServiceProviderPlugin(Plugin):
    def __init__(self, service: str, provider: str, import_path: str):
        self.service = service
        self.provider = provider
        self.import_path = import_path

    def should_load(self) -> bool:
        from localstack import config

        return self.service in config.DEFAULT_SERVICE_PORTS

    def load(self, ctx):
        module = importlib.import_module(self.import_path)
        service_class = getattr(module, "Service")
        return service_class()


class KinesisMockPlugin(ServicePlugin):
    name = "kinesis_mock"
    namespace = "localstack.aws.providers.kinesis"
    pass


if __name__ == "__main__":
    main()
