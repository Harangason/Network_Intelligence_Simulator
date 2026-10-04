"""Canonical Network Simulator application namespace."""
def __getattr__(name):
    if name in ("CAPABILITIES", "architecture_catalog"):
        from . import catalog
        return getattr(catalog, name)
    raise AttributeError(name)
