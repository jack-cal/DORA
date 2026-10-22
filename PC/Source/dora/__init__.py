"""Compatibility imports for previously published SUMUWW programs."""
import importlib
import importlib.abc
import importlib.util
import sys
from sumuww import __version__

class _AliasLoader(importlib.abc.Loader):
    def __init__(self, canonical): self.canonical = canonical
    def create_module(self, spec): return importlib.import_module(self.canonical)
    def exec_module(self, module):
        original = getattr(module, '__getattr__', None)
        def legacy_attribute(name):
            current = name.replace('DORA', 'SUMUWW').replace('Dora', 'Sumuww').replace('dora', 'sumuww')
            if current != name and current in module.__dict__: return module.__dict__[current]
            if original is not None: return original(name)
            raise AttributeError(name)
        module.__getattr__ = legacy_attribute

class _AliasFinder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith('dora.') or fullname == 'dora.__main__': return None
        canonical = 'sumuww.' + fullname[5:]
        spec = importlib.util.find_spec(canonical)
        if spec is None: return None
        return importlib.util.spec_from_loader(fullname, _AliasLoader(canonical),
            is_package=spec.submodule_search_locations is not None)

sys.meta_path.insert(0, _AliasFinder())
