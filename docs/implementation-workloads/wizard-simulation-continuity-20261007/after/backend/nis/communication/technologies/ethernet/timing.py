"""Technology-owned frame and timing implementation; preserved calculation semantics."""
from __future__ import annotations
from math import ceil, isfinite
from typing import Any
from backend.nis.communication.core.timing import FrameEstimate, _positive

def prepare_simulation_parameters(parameters):
    """Reconcile assumed PHY/layout with authoritative native network facts."""
    from .definition import PROFILE
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    aliases = PROFILE.get('parameter_aliases', {})
    assumed = {aliases.get(key, key) for key in parameters.get('_simulation_assumption_fields', [])}
    native = registry.normalize_parameters('ethernet', {
        key: value for key, value in parameters.items() if key in registry.parameter_keys('ethernet')})
    rate = native.get('bitrate_bps')
    if 'eth_phy' in assumed and rate is not None:
        choices = [rule['when']['eth_phy'] for rule in PROFILE.get('parameter_constraints', [])
                   if rule.get('parameter') == 'bitrate_bps' and rate in rule.get('allowed', [])
                   and set(rule.get('when', {})) == {'eth_phy'}]
        if choices and native.get('eth_phy') not in choices:
            native['eth_phy'] = choices[0]
    # The rate is the resolved network input, even if its original profile seed
    # was assumed. Never reverse a PHY constraint by replacing that input.
    fixed = (set(native) - assumed) | {'bitrate_bps'}
    derived = registry.constrain_simulation_values('ethernet', native, fixed)
    return {**parameters, **{key: value for key, value in derived.items() if key in assumed}}


def planning_frame_parameters(payload_bytes, parameters):
    """Use actual message data to derive only assumed dependent MAC lengths."""
    from backend.nis.communication import DEFAULT_TECHNOLOGY_REGISTRY as registry
    assumed = set(parameters.get('_simulation_assumption_fields', []))
    dependent = {'eth_client_bytes', 'eth_pad_bytes', 'eth_mac_frame_bytes',
                 'eth_wire_slot_bytes', 'eth_type_length'} & assumed
    native = registry.normalize_parameters('ethernet', {
        key: value for key, value in parameters.items() if key in registry.parameter_keys('ethernet')})
    native['payload_bytes'] = payload_bytes
    derived = registry.constrain_simulation_values('ethernet', native, set(native) - dependent)
    return {**parameters, **{key: value for key, value in derived.items() if key in dependent}}

def estimate_frame(protocol, payload_bytes, parameters):
    normalized = str(protocol or "CUSTOM").upper().replace("-", "_").replace(" ", "_")
    payload = max(0, int(payload_bytes))
    bitrate = _positive(parameters.get("bitrate"), 0.0)
    rate_confirmed = parameters.get("_rate_evidenced") is not False
    available = bitrate > 0 and rate_confirmed
    layer=parameters.get('eth_payload_layer')
    headers=parameters.get('eth_upper_header_bytes')
    tags=parameters.get('eth_vlan_tags')
    mtu=parameters.get('mtu_bytes')
    gap=parameters.get('eth_ifg_bits')
    whole=lambda x: isinstance(x,(int,float)) and not isinstance(x,bool) and isfinite(x) and int(x)==x
    if (layer not in {'MAC_CLIENT','UPPER_LAYER'} or not whole(headers) or headers<0
        or layer=='MAC_CLIENT' and headers!=0 or not whole(tags) or tags not in {0,1,2}
        or not whole(mtu) or mtu<=0 or not whole(gap) or gap<96
        or parameters.get('eth_frame_profile') not in {'BASIC_MAC','JUMBO_DEVICE'}):
        return FrameEstimate(normalized,payload,0,0.0,'ETHERNET_LAYOUT_UNVERIFIED',transmission_time_available=False)
    client=payload+int(headers)
    if client>mtu or parameters.get('eth_frame_profile')=='BASIC_MAC' and (client>1500 or mtu>1500):
        raise ValueError('Ethernet MAC-client data exceed selected MTU; segmentation is not evidenced.')
    frame_bits=(max(64,18+client+4*int(tags))+8)*8+int(gap)
    available=available and parameters.get('duplex')=='FULL'
    # Half-duplex carrier extension/collisions/backoff are a different model.
    if parameters.get('duplex')!='FULL':
        return FrameEstimate(normalized,payload,frame_bits,0.0,'ETHERNET_ACCESS_UNVERIFIED',transmission_time_available=False)
    return FrameEstimate(normalized, payload, frame_bits, frame_bits / bitrate if available else 0.0,
                         "ETHERNET_WIRE_ESTIMATE", calculation_version='2.0',transmission_time_available=available)

def prepare_timing_parameters(payload_bytes, bitrate=None, *, arbitration_bitrate=None, data_bitrate=None, local_timing_evidence=None, can_fd_brs=None, can_frame_format=None, can_fd_dlc=None, can_fd_wire_data_bytes=None):
    technology_id = 'ethernet'
    if not bitrate:
        raise ValueError(f"{technology_id} benötigt eine bestätigte Bitrate.")
    rate_parameters = {"bitrate_bps": bitrate}
    frame_parameters = {"bitrate": bitrate}
    native = {key:value for key,value in {'can_fd_brs':can_fd_brs,'can_frame_format':can_frame_format,
                'can_fd_dlc':can_fd_dlc,'can_fd_wire_data_bytes':can_fd_wire_data_bytes}.items() if value is not None}
    if set(native) - set():
        raise ValueError('CAN timing options are not applicable to this technology.')
    rate_parameters.update(native)
    frame_parameters.update(native)
    return rate_parameters, frame_parameters

def validate_timing_scope(payload_bytes, bitrate, rate_parameters, frame_parameters):
    return None

FRAME_PROTOCOLS = ('ETHERNET',)
