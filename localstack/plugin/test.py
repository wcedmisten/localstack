import re

import pkg_resources
from stevedore import ExtensionManager


class MyExtensionManager(ExtensionManager):
    def _load_one_plugin(self, ep, invoke_on_load, invoke_args, invoke_kwds, verify_requirements):
        ret = super()._load_one_plugin(
            ep, invoke_on_load, invoke_args, invoke_kwds, verify_requirements
        )
        print(">>> LOADING", ep.name)
        for m in ep.extras:
            extra = m.group()
            print(" >>require ", extra)
        return ret


def err(*args, **kwargs):
    print("ERROR", *args)


def main():
    print("CREATING EXTENSION MANAGER")
    mgr = MyExtensionManager(
        "localstack.mytest",
        invoke_on_load=True,
        on_load_failure_callback=err,
        verify_requirements=True,
    )
    for k, v in mgr.items():
        print(k, v)


if __name__ == "__main__":
    main()
