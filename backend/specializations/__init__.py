"""Industry and technology specializations used by NIS.

Industry knowledge and transport technology stay intentionally independent.
They meet only in the generation policy and the canonical engineering model.
"""

from .catalog import INDUSTRY_SPECIALIZATIONS, TECHNOLOGY_SPECIALIZATIONS

__all__ = ["INDUSTRY_SPECIALIZATIONS", "TECHNOLOGY_SPECIALIZATIONS"]
