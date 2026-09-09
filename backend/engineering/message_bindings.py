"""Canonical physical transmission bindings for messages with several channels."""


def message_hardware_interface_ids(message):
    primary = str((message or {}).get('hardware_interface_id') or '')
    additional = {str(binding.get('hardware_interface_id') or '') for binding in
        ((message or {}).get('configuration') or {}).get('physical_transmit_bindings') or [] if isinstance(binding, dict)}
    return ({primary} | additional) - {''}


def explicit_transmit_interface_ids(message):
    return {str(binding.get('hardware_interface_id') or '') for binding in
        ((message or {}).get('configuration') or {}).get('physical_transmit_bindings') or [] if isinstance(binding, dict)} - {''}
