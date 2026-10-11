from edit_utils import read, write, apply

path = 'backend/nis/agent/generators/__init__.py'
source = read(path)
source += '\n__all__ += ["FaultGenerator", "InterfaceGenerator", "MessageGenerator", "RoutingGenerator", "ScenarioGenerator"]\n'
write(path,source)
path = 'backend/tests/test_structure_consolidation.py'
source = read(path)
marker = "        assert getattr(old,name.title() + 'Generator') is BaseGenerator"
source = source.replace(marker, marker + "\n        namespace = {}\n        exec('from ' + canonical + ' import *', namespace)\n        assert namespace[name.title() + 'Generator'] is BaseGenerator")
write(path,source)
apply('generator-wildcard-export-compatibility')
