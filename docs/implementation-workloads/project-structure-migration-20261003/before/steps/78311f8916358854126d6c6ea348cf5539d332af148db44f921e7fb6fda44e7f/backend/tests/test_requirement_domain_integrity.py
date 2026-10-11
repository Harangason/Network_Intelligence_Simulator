"""Industry identity must come from the requirement or an explicit selection."""
import pytest

from backend.engineering.requirement_expansion_modules.resolution import choose_domain
from backend.engineering.agent_tools.generation import expand
from backend.engineering.agent_tools.generation import functions


@pytest.mark.parametrize('requirement', [
    'Drei Temperatursensoren und Raspberry Pi', 'Motor mit Drucksensor',
    'Kameras mit Ethernet', 'CAN-FD für Positionsdaten',
])
def test_general_components_are_not_evidence_of_automotive(requirement):
    assert choose_domain(requirement, None) == 'Generic'
    assert choose_domain(requirement, 'custom') == 'Generic'


@pytest.mark.parametrize('domain, expected', [
    ('embedded_systems', 'Generic'), ('industrial_automation', 'Industrial'),
    ('automotive', 'Automotive'), ('aerospace_defense', 'Aerospace'),
])
def test_explicit_industry_is_not_overridden_by_component_words(domain, expected):
    assert choose_domain('Fahrzeug Kamera Motor Temperatur Ethernet', domain) == expected


def test_missing_domain_can_be_inferred_from_explicit_industry_words():
    assert choose_domain('Automotive Fahrzeugprojekt', None) == 'Automotive'
    assert choose_domain('Industrial PLC project', None) == 'Industrial'


@pytest.mark.parametrize('text', ['Kein Fahrzeug, drei Sensoren.', 'Nicht Automotive sondern Embedded.',
    'Not automotive. Raspberry Pi with sensors.', 'Automotive ist ausgeschlossen.',
    'ECU mit Netz und Power Management', 'Eine Anlage zur Temperaturmessung'])
def test_negated_industry_and_generic_infrastructure_do_not_select_a_template(text):
    assert choose_domain(text, None) == 'Generic'


def test_selected_building_context_and_conflicting_industries_are_not_overwritten():
    assert choose_domain('Motor CAN Fahrzeug Steuerung', 'building_automation') == 'Generic'
    assert choose_domain('Automotive oder Industrial, noch unklar', None) == 'Generic'
    assert choose_domain('Nicht Automotive sondern Industrial', None) == 'Industrial'


def test_public_generator_does_not_supply_an_automotive_default():
    result = expand({'prompt': 'Drei Temperatursensoren mit Raspberry Pi'})
    assert result['interpretation']['resolved_domain'] == 'Generic'


def test_function_request_without_hardware_does_not_invent_a_controller():
    with pytest.raises(ValueError, match='Welcher Controller'):
        functions({'prompt': 'Eine Funktion zur Temperaturüberwachung erstellen.'})


def test_new_controller_requires_explicit_connection_and_timing():
    with pytest.raises(ValueError, match='Anschlusstechnologie und Statuszyklus'):
        functions({'prompt': 'Eine Funktion zur Temperaturüberwachung erstellen.',
                   'new_hardware': {'name': 'Regelung', 'device_type': 'EmbeddedController'}})
