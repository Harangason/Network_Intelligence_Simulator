from backend.engineering.naming import concise_name, concise_bus_names


def test_concise_generated_names_keep_real_purpose():
    assert concise_name('Function', 'Allradsteuerung_Steuerung') == 'Allradsteuerung'
    assert concise_name('Interface', 'RearLeftBrakeTemperature_1') == 'RearLeftBrakeTemperature'
    assert concise_name('Message', 'FrontRightBrakeTemperatureSensorErfassungData') == 'Front Right Brake Temperature'
    assert concise_name('Message', 'FrontkameraUmfelderfassungData') == 'Frontkamera Umfelderfassung'


def test_bus_names_are_unique_stable_and_preserve_custom_labels():
    rows = [{'id': key, 'name': key} for key in ['Antriebsstrang_01-S01', 'Antriebsstrang_01-IO-abgasnachbehandlung-lin-S02']]
    rows.append({'id': 'custom', 'name': 'Testbus'})
    names = concise_bus_names(rows)
    assert len(set(names.values())) == 3
    assert names['custom'] == 'Testbus'
    assert set(names.values()) == {'Antrieb_01', 'Antrieb_02', 'Testbus'}
    assert concise_bus_names([{'id': key, 'name': name} for key, name in names.items()]) == names


def test_ethernet_names_use_context_reserve_custom_labels_and_are_stable():
    from backend.engineering.naming import ethernet_names
    rows = [{'id': 'Fahrerassistenz_05-IO-kameraverarbeitung-automotive-ethernet-S01', 'technology': 'ETHERNET'},
            {'id': 'Fahrerassistenz_05-S01', 'technology': 'ETHERNET'},
            {'id': 'custom', 'name': 'ETH_Fahrerassistenz_01', 'name_source': 'user', 'technology': 'Ethernet'},
            {'id': 'hash', 'name': 'hash', 'technology': 'automotive_ethernet'},
            {'id': 'other', 'name': 'Custom Ethernet', 'technology': 'ETHERNET'},
            {'id': 'can', 'name': 'can', 'technology': 'CAN_FD'}]
    named = ethernet_names(rows)
    assert named[rows[0]['id']]['name'] == 'ETH_Kameraverarbeitung_01'
    assert named[rows[1]['id']]['name'] == 'ETH_Fahrerassistenz_02'
    assert named['hash']['name'] == 'ETH_Netz_01'
    assert named['other'] == rows[4] and named['can'] == rows[5]
    assert ethernet_names(list(reversed(rows))) == named
    assert ethernet_names(list(named.values())) == named


def test_ethernet_uses_explicit_frame_owner_not_first_sensor_or_hash():
    from backend.engineering.naming import ethernet_names, new_bus_name
    topology = {'nodes': [
        {'id': 'sensor', 'name': 'Rotor 4', 'kind': 'sensor', 'systemOwnerId': 'owner', 'ports': [{'physicalNetworkId': 'hash'}]},
        {'id': 'control', 'engineeringId': 'owner', 'name': 'Flugregler', 'kind': 'ecu', 'ports': [{'physicalNetworkId': 'hash'}]},
    ]}
    named = ethernet_names([{'id': 'hash', 'technology': 'ETHERNET'}], topology=topology)
    assert named['hash']['name'] == 'ETH_Flugregler_01'
    assert new_bus_name('hash', [{'name': 'eth_tuer_links_01'}], technology='Ethernet', context='Tür links') == 'ETH_Tuer_links_02'


def test_agent_network_generator_uses_same_allocator(monkeypatch):
    from backend.engineering.agent_tools import generation, model
    monkeypatch.setattr(model, 'networks', lambda: [{'name': 'ETH_Kamera_01'}])
    monkeypatch.setattr(generation.proposals, 'create', lambda kind, changes, prompt: changes)
    changes = generation.network({'name': 'Kamera', 'technology': 'ETHERNET'})
    assert changes[0]['data']['name'] == 'ETH_Kamera_02'
    assert changes[0]['data']['name_source'] == 'generated'
