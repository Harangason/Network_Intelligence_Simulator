# Format Generators

This folder contains small generators for the formats shown by the converter UI.

CAN-oriented formats:

- `generate_can_blf.py` - BLF plus DBC, using the main project generator and `python-can`
- `generate_can_asc.py` - Vector ASC-style trace
- `generate_can_trc.py` - PEAK TRC-style trace
- `generate_can_dbc.py` - DBC signal database
- `generate_can_arxml.py` - AUTOSAR ARXML-style system description
- `generate_can_fibex.py` - FIBEX-style system description
- `generate_can_csv.py`, `generate_can_json.py`, `generate_can_log.py`, `generate_can_txt.py`, `generate_can_xml.py`, `generate_can_yaml.py`, `generate_can_yml.py`

Ethernet-oriented formats:

- `generate_eth_pcap.py` - Ethernet/IPv4/UDP/SOME-IP PCAP
- `generate_eth_pcapng.py` - Ethernet/IPv4/UDP/SOME-IP PCAPNG

Measurement formats:

- `generate_can_mdf.py` - ASAM MDF 3.x summary, requires optional package `asammdf`
- `generate_can_mf4.py` - ASAM MDF 4/MF4 summary, requires optional package `asammdf`

Bulk generation:

```powershell
python format_generators\generate_all_formats.py --out-dir generated_formats --channels 4 --duration 1 --messages 20
```

Central controller:

```powershell
python generate_realistic_communication_tool.py --formats all --out-dir generated_formats --routing-table routing_table_example.csv --channels 10
python generate_realistic_communication_tool.py --formats blf,dbc,csv,json,pcapng --out-dir generated_package --routing-table routing_table_example.csv
python generate_realistic_communication_tool.py --formats can-all --out-dir generated_can_only
python generate_realistic_communication_tool.py --formats eth-all --out-dir generated_eth_only
```

Without `--out-dir` and with the default `--formats blf,dbc`, the root script keeps its original behavior and writes `--out` plus `--dbc`.

Routing table:

```powershell
python generate_realistic_communication_tool.py --write-routing-template routing_table_example.csv
python generate_realistic_communication_tool.py --routing-table routing_table_example.csv --channels 10
python format_generators\generate_all_formats.py --routing-table routing_table_example.csv --channels 10
```

CSV columns:

```csv
name,sender,receiver,cycle_ms,channel,gateway_to_channel,frame_id
LIDAR_OBJECT_LIST,LIDAR_FRONT,ADAS_DOMAIN,20,0,1,0x100
```

Example single-format calls:

```powershell
python format_generators\generate_can_dbc.py --out network.dbc --channels 16 --bus fd
python format_generators\generate_eth_pcapng.py --out someip.pcapng --duration 2 --messages 8
python format_generators\generate_can_blf.py --out trace.blf --dbc trace.dbc --bus xl --channels 8
```

Notes:

- CAN XL is represented as a logical profile where the available BLF writer still stores CAN-FD-compatible frames, because the installed `python-can` version has no native CAN XL frame object.
- MDF/MF4 are intentionally delegated to `asammdf`; generating valid binary MDF blocks by hand would be fragile for real analysis tools.
