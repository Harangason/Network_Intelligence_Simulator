"""Real workflow snapshot -> job -> canonical events -> downloaded IP captures."""
import argparse
import ipaddress
import json
from pathlib import Path
import struct
import time
from urllib.request import Request, urlopen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--wizard-report', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:13500')
    args = parser.parse_args()
    project = json.loads(args.wizard_report.read_text(encoding='utf-8'))['project']
    assert project.startswith('astra-e2e-')
    def request(path, payload=None, binary=False):
        req = Request(args.base_url+path, method='POST' if payload is not None else 'GET',
            headers={'X-Project-ID': project, 'Content-Type': 'application/json'}, data=None if payload is None else json.dumps(payload).encode())
        with urlopen(req, timeout=50) as response:
            return response.read() if binary else json.load(response)
    results = []
    for version in (4, 6):
        request('/api/engineering/capacity/calculate', {})
        preflight = request('/api/engineering/preflight', {})
        assert preflight['status'] in {'COMPLETE', 'APPROVED', 'WARNING'}, preflight
        snapshot = request('/api/engineering/workflow/simulation-snapshots', {'configuration': {'duration_s': .08, 'seed': 0, 'ip_version': version,
            'transport_protocol': 'udp', 'source_port': 12000, 'destination_port': 13000, 'formats': ['universal-jsonl', 'universal-csv', 'pcap', 'pcapng'],
            'scenario': {'mode': 'NORMAL', 'faults': []}}})
        job = request('/api/simulations', {'workflow_managed': True, 'workflow_snapshot_id': snapshot['id'], 'project_id': project})
        for _ in range(50):
            job = request('/api/simulations/' + job['id'])
            if job['status'] in {'completed', 'failed', 'canceled'}:
                break
            time.sleep(.4)
        assert job['status'] == 'completed', job.get('error')
        page = request('/api/simulations/' + job['id'] + '/trace-window?limit=500')
        assert page['next_cursor'] is None
        other_technologies = sorted({e['technology'] for e in page['events'] if not e.get('ethernet')})
        events = [e for e in page['events'] if e.get('ethernet')]
        assert events and all(e['ip_version'] == version and e['ethernet']['source_port'] == 12000 for e in events)
        artifacts = job['result']['artifacts']
        pcap_index = next(i for i, path in enumerate(artifacts) if path.endswith('.pcap'))
        data = request(f'/api/simulations/{job["id"]}/artifacts/{pcap_index}', binary=True)
        offset, packets = 24, 0
        for event in events:
            if event['status'] == 'dropped':
                continue
            for receiver in event['ethernet']['destinations']:
                sec, us, length, original = struct.unpack('<IIII', data[offset:offset+16])
                packet = data[offset+16:offset+16+length]
                ip = packet[14:]
                assert ip[0] >> 4 == version
                src, dst = (ip[12:16], ip[16:20]) if version == 4 else (ip[8:24], ip[24:40])
                assert str(ipaddress.ip_address(src)) == event['src_ip']
                assert str(ipaddress.ip_address(dst)) == receiver['ip']
                start = 20 if version == 4 else 40
                assert struct.unpack('!HH', ip[start:start+4]) == (12000, 13000)
                payload_length = struct.unpack('!H', ip[start+4:start+6])[0]-8
                assert ip[start+8:start+8+payload_length] == bytes.fromhex(event['payload_hex'])
                assert abs(sec+us/1e6-event['timestamp_unix']) < 1e-6
                offset += 16+length
                packets += 1
        assert offset == len(data)
        results.append({'ip_version': version, 'job_id': job['id'], 'snapshot_id': snapshot['id'], 'packets_verified': packets,
            'other_universal_technologies': other_technologies,
            'source_ip': events[0]['src_ip'], 'destination_ips': events[0]['dst_ips'],
            'tx_port': events[0]['sender_port'], 'rx_ports': events[0]['receiver_ports'],
            'browser_url': args.base_url + f'/trace-analysis?project={project}&job={job["id"]}&view=messages&focus_s={events[0]["time_s"]}'})
    report = {'project': project, 'status': 'PASSED', 'runs': results, 'no_demo_participants': True, 'same_payload_and_time_as_universal_trace': True}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
