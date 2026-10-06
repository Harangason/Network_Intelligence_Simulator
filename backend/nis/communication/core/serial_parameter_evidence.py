"""Shared evidence acceptance for registered serial timing implementations."""
def finalize_local_rate(target, resolved, rate_evidenced, confirmed_serial_evidence, _number):
    serial = confirmed_serial_evidence(target, resolved)
    known_clock = _number(resolved.get('bitrate'), 0) if rate_evidenced else 0
    if known_clock:
        resolved['_confirmed_bus_clock_bps'] = known_clock
    if serial and known_clock and serial['bitrate_bps'] != known_clock:
        resolved['_rate_findings'] = [{'code': 'TECHNOLOGY_RATE_MODEL_MISMATCH',
                                      'message': 'Gerätetakt widerspricht der bestätigten Busfrequenz.'}]
        serial = None
    rate_evidenced = serial is not None
    if serial:
        resolved["bitrate"] = serial["bitrate_bps"]
    else:
        resolved.pop("bitrate", None)
    resolved["_rate_evidenced"] = rate_evidenced
    return resolved['_rate_evidenced']
