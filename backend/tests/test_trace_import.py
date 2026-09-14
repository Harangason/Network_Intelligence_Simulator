"""Adapter tests use actual file bytes and a standalone Flask app; no SQL writes."""
import io
import json
import time

import can
import dpkt
import numpy as np
import pytest
from asammdf import MDF, Signal
from flask import Flask

from backend.app.trace_import import import_trace, trace_import_api, MAX_BYTES


def test_text_formats_and_validation():
    for filename, content in [
        ('trace.csv', b'time_s,message,payload_hex\n0.5,CAN,01 ff\n'),
        ('trace.json', b'[{"time_s":0.5,"message":"CAN"}]'),
        ('trace.jsonl', b'{"time_s":0.5}\n{"time_s":1.0}')]:
        result = import_trace(content, filename)
        assert result['events'][0]['timestamp'] == .5
        assert result['analysis_only']
    for content in [b'[]', b'[{"time_s":-1}]', b'[{"time_s":"NaN"}]', b'[1]']:
        with pytest.raises(ValueError):
            import_trace(content, 'trace.json')
    with pytest.raises(ValueError, match='Spaltenzahl'):
        import_trace(b'time_s,message\n0,one,extra', 'trace.csv')


@pytest.mark.parametrize('fmt', ['asc', 'blf', 'log', 'trc'])
def test_can_reader_roundtrip(tmp_path, fmt):
    path = tmp_path / f'capture.{fmt}'
    with can.Logger(str(path)) as writer:
        writer(can.Message(timestamp=1.25, arbitration_id=0x321, is_extended_id=False,
                           data=[0x12, 0xAB], channel=0))
    result = import_trace(path.read_bytes(), path.name)
    event = result['events'][0]
    assert event['message'] == '0x321'
    assert event['payload_hex'] == '12 ab'
    assert event['signals'] == []
    assert result['warnings']


def test_can_fd(tmp_path):
    path = tmp_path / 'fd.asc'
    with can.ASCWriter(path) as writer:
        writer(can.Message(timestamp=1, arbitration_id=0x123456, is_extended_id=True,
                           is_fd=True, data=bytes(range(12)), channel=1))
    result = import_trace(path.read_bytes(), path.name)
    event = result['events'][0]
    assert event['technology'].startswith('CAN FD')
    assert event['extended_id']
    assert event['message'] == '0x00123456'
    assert len(bytes.fromhex(event['payload_hex'])) == 12


@pytest.mark.parametrize('fmt', ['pcap', 'pcapng'])
def test_capture_roundtrip_and_corruption(fmt):
    stream = io.BytesIO()
    writer = (dpkt.pcap.Writer if fmt == 'pcap' else dpkt.pcapng.Writer)(stream)
    packet = bytes.fromhex('001122334455aabbccddeeff88b5') + b'payload'
    writer.writepkt(packet, ts=1.25)
    data = stream.getvalue()
    result = import_trace(data, 'renamed.bin')
    assert result['format'] == fmt
    event = result['events'][0]
    assert event['timestamp'] == 1.25
    assert event['source'] == 'aa:bb:cc:dd:ee:ff'
    assert event['destination'] == '00:11:22:33:44:55'
    assert bytes.fromhex(event['payload_hex']) == packet
    with pytest.raises(ValueError):
        import_trace(data[:-2], f'bad.{fmt}')


@pytest.mark.parametrize('version', ['3.30', '4.10'])
def test_mdf_real_measurements(tmp_path, version):
    path = tmp_path / ('sample.mdf' if version.startswith('3') else 'sample.mf4')
    with MDF(version=version) as mdf:
        mdf.append([Signal(samples=np.array([12.5, 13.0]), timestamps=np.array([0.1, 0.2]), name='Speed', unit='m/s')])
        mdf.save(path, overwrite=True)
    result = import_trace(path.read_bytes(), 'renamed.bin')
    assert len(result['events']) == 2
    signal = result['events'][0]['signals'][0]
    assert signal['value'] == 12.5
    assert signal['unit'] == 'm/s'
    assert signal['signal'] == 'Speed'


def test_preview_reports_truncation():
    result = import_trace(json.dumps([{'time_s': i} for i in range(2001)]).encode(), 'large.json')
    assert result['truncated']
    assert len(result['events']) == 2000
    assert any('nicht vollständig' in warning for warning in result['warnings'])


def test_mf4_can_capture_is_not_a_decoded_signal(tmp_path):
    path = tmp_path / 'can.mf4'
    with can.MF4Writer(path) as writer:
        timestamp = time.time() + 1
        writer(can.Message(timestamp=timestamp, arbitration_id=0x123, is_extended_id=False, data=[1, 2], channel=0))
    with MDF(path) as mdf:
        expected_time = timestamp - mdf.header.start_time.timestamp()
    result = import_trace(path.read_bytes(), path.name)
    assert len(result['events']) == 1
    assert result['events'][0]['message'] == '0x123'
    assert result['events'][0]['signals'] == []
    assert result['events'][0]['payload_hex'] == '01 02'
    assert result['events'][0]['timestamp'] == pytest.approx(expected_time, abs=1e-6)


def test_http_upload_and_errors():
    app = Flask(__name__)
    app.register_blueprint(trace_import_api, url_prefix='/api')
    client = app.test_client()
    result = client.post('/api/trace-import?filename=x.json', data=b'[{"time_s":0}]', content_type='application/octet-stream')
    assert result.status_code == 200
    assert result.json['events'][0]['timestamp'] == 0
    assert client.post('/api/trace-import?filename=x.pcap', data=b'bad').status_code == 422
    assert client.post('/api/trace-import?filename=x.json', environ_overrides={'CONTENT_LENGTH': str(MAX_BYTES + 1), 'wsgi.input': io.BytesIO(b'x')}).status_code == 413
    assert client.post('/api/trace-import?filename=x.txt', data=b'unknown').status_code == 422


def test_unknown_fields_and_missing_time_are_preserved():
    result = import_trace(b'[{"vendor":{"code":0},"payload":"ab"}]', 'vendor.json')
    event = result['events'][0]
    assert event['timestamp'] is None
    assert event['time_status'] == 'unavailable'
    assert event['vendor'] == {'code': 0}
    assert event['source_record_index'] == 0


def test_ethernet_ip_udp_layers_are_decoded_without_signal_invention():
    import socket
    udp = dpkt.udp.UDP(sport=1234, dport=5678, data=b'hello')
    udp.ulen = len(udp)
    ip = dpkt.ip.IP(src=socket.inet_aton('192.0.2.1'), dst=socket.inet_aton('192.0.2.2'), p=17, data=udp)
    ip.len = len(ip)
    frame = dpkt.ethernet.Ethernet(src=b'\x01'*6, dst=b'\x02'*6, type=0x800, data=ip)
    buffer = io.BytesIO()
    dpkt.pcap.Writer(buffer).writepkt(bytes(frame), ts=1)
    event = import_trace(buffer.getvalue(), 'trace.pcap')['events'][0]
    assert event['protocols']['ip']['source'] == '192.0.2.1'
    assert event['protocols']['transport'] == {'name': 'UDP', 'source_port': 1234, 'destination_port': 5678}
    assert event['signals'] == []
    assert bytes.fromhex(event['payload_hex']) == bytes(frame)


def test_http_exact_500_mib_capture_stream(tmp_path):
    import struct
    path = tmp_path / 'large.pcapng'
    with path.open('wb') as stream:
        writer = dpkt.pcapng.Writer(stream)
        for index in range(2001):
            writer.writepkt(b'\x00' * 60, ts=index + 1)
        length = MAX_BYTES - stream.tell()
        stream.write(struct.pack('<II', 0x12345678, length))
        stream.seek(MAX_BYTES - 4)
        stream.write(struct.pack('<I', length))
    app = Flask(__name__)
    app.register_blueprint(trace_import_api, url_prefix='/api')
    with path.open('rb') as stream:
        response = app.test_client().post('/api/trace-import?filename=large.pcapng',
            input_stream=stream, content_length=MAX_BYTES, content_type='application/octet-stream')
    assert response.status_code == 200, response.json
    assert response.json['truncated']
    assert response.json['imported_events'] == 2000


@pytest.mark.parametrize('filename,content', [
    ('large.csv', b'time_s,message\n' + b'1,hello\n' * 700000),
    ('large.jsonl', b'{"time_s":1}\n' * 500000),
    ('large.json', b'{"events":[' + b'{"time_s":1},' * 500000 + b'{"time_s":2}]}'),
], ids=['csv', 'jsonl', 'json'])
def test_large_text_upload_preview(filename, content):
    app = Flask(__name__)
    app.register_blueprint(trace_import_api, url_prefix='/api')
    response = app.test_client().post('/api/trace-import?filename=' + filename, data=content)
    assert response.status_code == 200, response.json
    assert response.json['truncated']
    assert response.json['imported_events'] == 2000
