from backend.nis.agent.generators.base import BaseGenerator
from backend.nis.agent.generators.base import GeneratorResult

__all__ = ["BaseGenerator", "GeneratorResult"]

# Historical names are aliases of BaseGenerator, not separate implementations.
FaultGenerator = BaseGenerator
InterfaceGenerator = BaseGenerator
MessageGenerator = BaseGenerator
RoutingGenerator = BaseGenerator
ScenarioGenerator = BaseGenerator
