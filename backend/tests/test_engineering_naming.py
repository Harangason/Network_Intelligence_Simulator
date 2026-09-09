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
