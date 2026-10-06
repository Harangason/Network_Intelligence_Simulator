"""Protect actual technology ownership, package retirement and legacy contracts."""
import ast
import importlib
import json
from pathlib import Path

from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.nis.compatibility import ALIASES

ROOT = Path(__file__).resolve().parents[2]


def test_native_format_functions_have_technology_owners():
    from backend.nis.traces.formats import common_trace
    from backend.nis.simulation import communication_generator as generator
    functions = {
        common_trace.build_can_trace:'can.formats.trace_model',
        common_trace.build_ethernet_trace:'ethernet.formats.trace_model',
        common_trace.crc8_autosar:'can.encoding',
        common_trace.build_someip_payload:'someip.encoding',
        common_trace.internet_checksum:'ip.encoding',
        generator.generate_blf:'can.formats.native_example',
        generator.build_restbus_routing_rows:'can.formats.restbus_example',
        generator.normalized_routing_row:'can.formats.routing',
    }
    for function, owner in functions.items():
        assert function.__module__ == 'backend.nis.communication.technologies.' + owner
    for path in ['backend/nis/traces/formats/common_trace.py', 'backend/nis/traces/formats/mdf_writer.py',
                 'backend/nis/simulation/port_load.py', 'backend/nis/simulation/Archiv/generate_realistic_can_blf.py']:
        tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
        assert not any(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) for node in tree.body), path
    assert generator.SignalDef is not common_trace.SignalDef  # Distinct historical mutable/frozen APIs.


def test_internal_consumers_import_actual_format_owners():
    violations = []
    for path in (ROOT / 'backend/nis').rglob('*.py'):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            if isinstance(node,ast.ImportFrom) and node.module == 'backend.nis.traces.formats.common_trace':
                violations.append((str(path),node.lineno))
    assert not violations


def test_registered_scheduling_and_parameter_rules_have_one_owner():
    from backend.nis.engineering.capacity import service, dimensioning, transmission
    from backend.nis.traces import universal_trace
    from backend.nis.simulation import communication_simulator, port_load
    for key in ('can','can_fd','ethernet','lin','i2c','spi'):
        assert registry.scheduling_implementation(key).__name__ == f'backend.nis.communication.technologies.{key}.scheduling'
    for key in ('can_fd','lin','i2c','spi'):
        assert registry.capacity_parameter_implementation(key).__name__ == f'backend.nis.communication.technologies.{key}.parameters'
    assert registry.timing_implementation('unknown') is None
    assert universal_trace._add_restbus_sessions.__module__ == 'backend.nis.communication.technologies.ethernet.restbus'
    assert communication_simulator._native_configuration.__module__ == 'backend.nis.communication.technologies.can.formats.native_configuration'
    assert port_load.ethernet_port_load.__module__ == 'backend.nis.communication.technologies.ethernet.runtime'
    # Protocol comparisons belong to selected owner implementations; shared
    # assessment and release orchestration may still aggregate their evidence.
    protocols = {'CAN','CAN_FD','LIN','ETHERNET','I2C','SPI','AUTOMOTIVE_ETHERNET'}
    for module in (service,dimensioning,transmission):
        tree = ast.parse(Path(module.__file__).read_text(encoding='utf-8'))
        comparisons = [node.lineno for node in ast.walk(tree) if isinstance(node, (ast.Compare,ast.IfExp))
                       and any(isinstance(value,ast.Constant) and value.value in protocols for value in ast.walk(node))]
        assert not comparisons, (module.__name__, comparisons)


def test_removed_physical_technology_aliases_still_import_same_owner():
    checked = 0
    for old, canonical in ALIASES.items():
        if not old.startswith(('backend.communication.technologies.','backend.specializations.technologies.')):
            continue
        assert importlib.import_module(old) is importlib.import_module(canonical), old
        checked += 1
    assert checked >= 100
    for folder in ['backend/communication/technologies','backend/specializations/technologies']:
        assert not (ROOT / folder).exists(), folder


def test_placeholder_packages_are_retired_without_invented_implementations():
    from backend.nis.agent.generators import BaseGenerator
    for name in ('fault','interface','message','routing','scenario'):
        canonical = 'backend.nis.agent.generators.' + name
        old = importlib.import_module(canonical)
        assert getattr(old,name.title() + 'Generator') is BaseGenerator
        namespace = {}
        exec('from ' + canonical + ' import *', namespace)
        assert namespace[name.title() + 'Generator'] is BaseGenerator
        assert not (ROOT / canonical.replace('.','/')).exists()
    for name in ('documentation','interface','message','network','parameter','routing','signal','simulation','trace','validation'):
        canonical = 'backend.nis.agent.handlers.' + name
        assert importlib.import_module(canonical) is importlib.import_module('backend.nis.agent.handlers')
        assert not (ROOT / canonical.replace('.','/')).exists()
    assert not (ROOT / 'backend/nis/physics').exists()
    for path in ['frontend/src/app/layout-check','frontend/src/app/__layout-check']:
        assert not (ROOT / path).exists()
    # A one-file package may expose real metadata; it is not an empty scaffold.
    from backend.nis.automation import CAPABILITY
    from backend.nis.workflow.stages.stage_01_engineering_model import STAGE
    assert CAPABILITY and STAGE


def test_runtime_timestamps_and_packet_encoding_contracts():
    from backend.nis.communication.technologies.ethernet.runtime import serialize_event
    from backend.nis.communication.technologies.lin.runtime import next_poll_start
    from backend.nis.communication.technologies.ip.encoding import packet_header
    from backend.nis.communication.technologies.can.encoding import set_unsigned_le, set_unsigned_le_strict
    assert next_poll_start(.013, {'period_ms':20,'offset_ms':5}) == .025
    assert packet_header(bytes([192,0,2,1]),bytes([192,0,2,2]),4,17,8,3).hex() == '4500001c000340004011b6cac0000201c0000202'
    event = {'network':'n','time_s':0,'base_transmission_time_s':.00012345,'status':'transmitted',
             'sender_hardware':'a','sender_port':'p','configured_latency_ms':0,
             'ethernet':{'destinations':[{'hardware_id':'b','port_id':'q'}]}}
    serialize_event(event,{},0,{},0,'n',.00012345)
    assert event['timestamp_utc'] == '1970-01-01T00:00:00.000247Z'
    # Preserve both old overflow contracts while sharing their technology owner.
    set_unsigned_le(bytearray(1), 8, 1, 1)
    import pytest
    with pytest.raises(IndexError):
        set_unsigned_le_strict(bytearray(1), 8, 1, 1)
