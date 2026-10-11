"""Audited protocol-owned simulation examples, never installed device facts."""
import hashlib
import json
from pathlib import Path
import shutil

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
BASE = ROOT / 'backend/nis/communication/technologies'
SCENARIOS = {
    '5g': {'bitrate_bps': 100000000, 'nr_channel_bandwidth_mhz': 10},
    'can_aerospace': {'bitrate_bps': 500000, 'can_clock_hz': 40000000,
        'can_prescaler': 5, 'can_tseg1_tq': 13, 'can_tseg2_tq': 2,
        'can_sjw_tq': 2, 'sample_point_percent': 87.5},
    'ccp': {'bitrate_bps': 500000, 'can_dlc': 8, 'can_clock_hz': 40000000,
        'can_prescaler': 5, 'can_tseg1_tq': 13, 'can_tseg2_tq': 2,
        'can_sjw_tq': 2, 'sample_point_percent': 87.5},
    'can_xl': {'nominal_bitrate_bps': 500000, 'data_bitrate_bps': 10000000,
        'can_controller_profile': 'X_CAN_3_9', 'can_clock_hz': 80000000,
        'can_prescaler': 1, 'can_tseg1_tq': 127, 'can_tseg2_tq': 32,
        'can_sjw_tq': 32, 'sample_point_percent': 80,
        'can_xl_data_prescaler': 1, 'can_xl_data_tseg1_tq': 5,
        'can_xl_data_tseg2_tq': 2, 'can_xl_data_sjw_tq': 2,
        'can_xl_data_sample_point_percent': 75, 'can_xl_phy': 'CAN_SIC_XL',
        'can_xl_mode_switching': True, 'can_xl_transceiver_max_bps': 10000000},
    'generic_ethernet': {'eth_peer_rate_bps': 10000000},
    'goose': {'eth_peer_rate_bps': 10000000},
    'iec60870_5_101': {'iec101_implementation': 'ABB_COM600_5_1', 'iec101_baud_bps': 19200},
    'iec61162': {'iec61162_can_bitrate_bps': 250000, 'iec61162_ethernet_bitrate_bps': 100000000},
    'interbus': {'ib_pci_slave_bitrate_bps': 500000},
    'j1939': {'j39_data_bitrate_bps': 2000000},
    'knx_tp': {'ktp_host_bitrate_bps': 19200},
    'lonworks': {'lw_channel_profile': 'STD_XCVR_7_32_1_32', 'lw_channel': 'TP_FT_10',
        'lw_network_bitrate_bps': 78125, 'lw_neuron_interface_bps': 78125, 'lw_medium_nominal_bps': 78125},
    'lorawan': {'lr_fs_bitrate_bps': 50000},
    'lvds': {'lv_lane_bps': 100000000, 'lv_aggregate_bps': 100000000},
    'mipi_csi2': {'cs_device': 'LATTICE_SOFT', 'cs_direction': 'TX',
        'cs_lane_bitrate_bps': 160000000, 'cs_information_rate_bps': 160000000,
        'cs_aggregate_information_bps': 160000000, 'cs_max_capability_bps': 160000000},
    'mipi_dsi': {'ds_aggregate_bps': 80000000},
    'modbus_ascii': {'ma_tx_baud_bps': 19200},
    'most': {'mo_allocation_bps': 352800},
    'mvb': {'mv_measured_rate_bps': 1500000},
    'nfc': {'nf_host_clock_bps': 100000},
    'nmea0183': {'nt_rx_baud_bps': 4800},
    'obd2': {'o_host_baud': 38400},
    'one_wire': {'ow_host_i2c_bps': 100000},
    'rs422': {'rs422_device_max_bps': 10000000, 'rs422_peer_max_bps': 10000000, 'rs422_termination': 'PARALLEL'},
    'rs485': {'rs485_device_max_bps': 10000000, 'rs485_peer_max_bps': 10000000},
    'sampled_values': {'sv_proposal_mode': 'SOURCE_PROPOSALS', 'sv_link_bps': 100000000},
    'sercos_iii': {'sercos_proposal_mode': 'SOURCE_MINIMUM_PROPOSALS', 'sercos_link_bps': 100000000},
    'spacewire': {'spw_proposal_mode': 'SOURCE_BASELINE', 'spw_tx_bps': 10000000,
        'spw_rx_bps': 10000000, 'spw_local_receive_max_bps': 10000000,
        'spw_device_min_bps': 2000000, 'spw_device_max_bps': 10000000,
        'spw_peer_receive_max_bps': 10000000},
    'spi': {'spi_controller_max_bps': 10000000, 'spi_target_max_bps': 10000000,
        'spi_physical_max_bps': 10000000, 'spi_peripheral_clock_bps': 40000000,
        'spi_imx_pll_bps': 96000000},
    'tsn': {'tn_link_bps': 1000000000, 'tn_send_bps': -1000000000},
    'usb': {'ub_lane_bps': 1500000, 'ub_reverse_bps': 1500000},
    'wireless_m_bus': {'wm_data_bps': 16384},
}

def main():
    import sys
    apply = '--apply' in sys.argv
    workload_path = OUT / 'workload.json'
    work = json.loads(workload_path.read_text())
    changed = list(work['files_changed'])
    for tech, values in SCENARIOS.items():
        relative = f'backend/nis/communication/technologies/{tech}/profile.json'
        file = ROOT / relative
        profile = json.loads(file.read_text())
        schema = profile['parameter_schema']
        assert set(values) <= set(schema), (tech, set(values) - set(schema))
        for key, value in values.items():
            spec = schema[key]
            assert not spec.get('options') or value in spec['options'], (tech, key, value)
            assert spec.get('min') is None or value >= spec['min']
            assert spec.get('max') is None or value <= spec['max']
        if not apply:
            snapshot = OUT / 'before' / relative
            if not snapshot.exists():
                snapshot.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(file, snapshot)
            if relative not in changed:
                changed.append(relative)
        else:
            preset = profile.setdefault('simulation_defaults', {})
            preset.setdefault('values', {}).update(values)
            preset.setdefault('comparison_values', {}).update({key: {
                'technology': tech, 'value': value,
                'source': f'backend/nis/communication/technologies/{tech}/profile.json',
                'source_revision': 'NIS_PROTOCOL_COMPARISON_SCENARIO_V1',
                'purpose': 'Illustrative matching-protocol scenario within registered bounds; not universal rate or installed-device evidence',
                'registered_source': schema[key].get('source'),
            } for key, value in values.items()})
            file.write_text(json.dumps(profile, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if not apply:
        work['files_changed'] = changed
        work['revision_before'] = {key: hashlib.sha256((ROOT / key).read_bytes()).hexdigest()
                                  if (ROOT / key).is_file() else None for key in set(work['revision_before']) | set(changed)}
        work['implementation_plan'].append('Replace remaining meaningless rate minima with explicit owned-protocol comparison scenarios; preserve inactive zero reservations')
        workload_path.write_text(json.dumps(work, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'mode': 'apply' if apply else 'plan', 'protocols': len(SCENARIOS)}))

if __name__ == '__main__':
    main()
