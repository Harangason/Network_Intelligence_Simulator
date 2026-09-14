"""Skill metadata is a projection of registered tools, not executable domain logic."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SkillRegistry:
    entries: list[dict]
    tools: dict

    def contracts(self, permissions):
        return [{'skill_id': item['id'], 'version': '1', 'purpose': item['description'],
            'accepted_inputs': ['TEXT', 'FILE', 'SELECTION', 'MODEL_OBJECT', 'USER_DECISION'],
            'required_context': ['project_ref', 'model_revision'], 'required_capabilities': item['tools'],
            'outputs': ['PROPOSAL', 'FINDING', 'VALIDATION'] if item['id'] != 'port' else ['MODEL_CHANGE', 'VALIDATION', 'VISUALIZATION'],
            'validation': ['current_project', 'current_revision', 'domain_validation'],
            'failure_modes': ['NOT_SUPPORTED', 'PERMISSION_DENIED', 'CONFLICT', 'BLOCKED'],
            'available': all(name in self.tools and self.tools[name].permission in permissions for name in item['tools'])}
            for item in self.entries]
