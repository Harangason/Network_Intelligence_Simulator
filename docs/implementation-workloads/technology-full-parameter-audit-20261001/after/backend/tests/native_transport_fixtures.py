"""Explicit qualified virtual fixture inputs; never production hardware defaults."""

def lin_design(rate=19200):
    return {
        'lin_edition': 'LIN_2_2A_2010', 'lin_physical_profile': 'LIN_2_2A_SINGLE_WIRE',
        'lin_node_role': 'COMMANDER', 'lin_frame_kind': 'UNCONDITIONAL', 'lin_bitrate_bps': rate,
        **{'lin_' + key: 'isolated-virtual-fixture:' + key for key in (
            'revision', 'device_source', 'binding_source', 'physical_source', 'ldf_source',
            'encoding_source', 'schedule_source', 'capacity_source', 'acceptance_source', 'commander_node_id')},
    }

def ethernet_mac():
    return {'eth_payload_layer': 'MAC_CLIENT', 'eth_upper_header_bytes': 0, 'eth_vlan_tags': 0,
            'mtu_bytes': 1500, 'eth_ifg_bits': 96, 'eth_frame_profile': 'BASIC_MAC', 'duplex': 'FULL',
            'eth_link_up': True, 'eth_pause_rx': False, 'eth_pause_tx': False, 'eth_eee_enabled': False}
