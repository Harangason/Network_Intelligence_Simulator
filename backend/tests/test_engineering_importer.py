from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from backend.engineering.importer import preview_import
from backend.engineering.models import EngineeringValidationError


def test_dbc_preview_builds_complete_hierarchy() -> None:
    content = b'''VERSION "1.0"
BU_: Gateway Display
BO_ 256 VehicleStatus: 8 Gateway
 SG_ Speed : 0|16@1+ (0.01,0) [0|250] "km/h" Display
'''

    plan = preview_import("vehicle.dbc", content)

    assert plan["format"] == "dbc"
    assert plan["counts"] == {
        "hardware_nodes": 2,
        "functions": 2,
        "interfaces": 2,
        "messages": 1,
        "signals": 1,
    }
    assert plan["messages"][0]["message_id_hex"] == "0x100"
    assert plan["signals"][0]["unit"] == "km/h"
    assert next(
        node["device_type"] for node in plan["hardware_nodes"] if node["name"] == "Gateway"
    ) == "Gateway"


def test_preview_accepts_files_larger_than_previous_limit() -> None:
    content = b'''VERSION "1.0"
BU_: Gateway Display
BO_ 256 VehicleStatus: 8 Gateway
 SG_ Speed : 0|16@1+ (0.01,0) [0|250] "km/h" Display
''' + (b"\nCM_ \"padding\";" * 700_000)

    plan = preview_import("large-vehicle.dbc", content)

    assert len(content) > 10 * 1024 * 1024
    assert plan["counts"]["messages"] == 1


def test_csv_preview_detects_columns_and_parent_keys() -> None:
    content = (
        "Domain;Hardware;Function;Interface;Bus;Message;CAN_ID;Signal;Start_Bit;Length_Bits;Unit\n"
        "Rail;Brake ECU;Brake Control;CAN 1;CAN_FD;BrakeStatus;0x180;WheelSpeed;0;16;km/h\n"
    ).encode()

    plan = preview_import("signals.csv", content)

    assert plan["counts"]["hardware_nodes"] == 1
    assert plan["counts"]["signals"] == 1
    assert plan["mapping"]["hardware"] == "Hardware"
    assert plan["interfaces"][0]["interface_type"] == "CAN_FD"
    assert plan["signals"][0]["message_key"] == plan["messages"][0]["key"]
    assert {item["domain"] for key in ("hardware_nodes", "functions", "interfaces", "messages", "signals") for item in plan[key]} == {"Rail"}


def test_import_defaults_to_generic_domain_instead_of_automotive() -> None:
    plan = preview_import(
        "generic.csv",
        b"Hardware,Message,Signal\nController,Status,Healthy\n",
    )

    assert plan["hardware_nodes"][0]["domain"] == "generic"
    assert plan["signals"][0]["domain"] == "generic"


def _minimal_xlsx() -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Import" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Hardware</t></is></c><c r="B1" t="inlineStr"><is><t>Message</t></is></c><c r="C1" t="inlineStr"><is><t>Signal</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>Body ECU</t></is></c><c r="B2" t="inlineStr"><is><t>DoorStatus</t></is></c><c r="C2" t="inlineStr"><is><t>DoorOpen</t></is></c></row></sheetData></worksheet>',
        )
    return buffer.getvalue()


def test_xlsx_preview_reads_first_worksheet() -> None:
    plan = preview_import("model.xlsx", _minimal_xlsx())

    assert plan["format"] == "xlsx"
    assert plan["hardware_nodes"][0]["name"] == "Body ECU"
    assert plan["messages"][0]["name"] == "DoorStatus"
    assert plan["signals"][0]["name"] == "DoorOpen"


def test_arxml_preview_extracts_typical_engineering_objects() -> None:
    content = b"""<?xml version="1.0" encoding="UTF-8"?>
<AUTOSAR>
  <AR-PACKAGES>
    <AR-PACKAGE>
      <SHORT-NAME>Vehicle</SHORT-NAME>
      <ELEMENTS>
        <ECU-INSTANCE><SHORT-NAME>BodyGateway</SHORT-NAME></ECU-INSTANCE>
        <CAN-CLUSTER><SHORT-NAME>ComfortCAN</SHORT-NAME></CAN-CLUSTER>
        <CAN-FRAME><SHORT-NAME>DoorStatusFrame</SHORT-NAME></CAN-FRAME>
        <I-SIGNAL><SHORT-NAME>DoorOpen</SHORT-NAME></I-SIGNAL>
      </ELEMENTS>
    </AR-PACKAGE>
  </AR-PACKAGES>
</AUTOSAR>
"""

    plan = preview_import("vehicle.arxml", content)

    assert plan["format"] == "arxml"
    assert plan["counts"]["hardware_nodes"] == 1
    assert plan["counts"]["interfaces"] == 1
    assert plan["counts"]["messages"] == 1
    assert plan["counts"]["signals"] == 1
    assert plan["hardware_nodes"][0]["device_type"] == "Gateway"
    assert plan["interfaces"][0]["interface_type"] == "CAN"
    assert plan["messages"][0]["name"] == "DoorStatusFrame"
    assert plan["signals"][0]["name"] == "DoorOpen"


def test_yaml_preview_detects_industry_device_collections() -> None:
    content = b"""
industry: industrial
devices:
  - name: ProfinetController
    kind: ecu
networks:
  - name: ProfinetLine
    technology: ethernet
messages:
  - name: ConveyorStatus
signals:
  - name: MotorCurrent
    length_bits: 16
"""

    plan = preview_import("factory.yaml", content)

    assert plan["format"] == "yaml"
    assert plan["counts"]["hardware_nodes"] == 1
    assert plan["counts"]["messages"] == 1
    assert plan["counts"]["signals"] == 1
    assert plan["interfaces"][0]["interface_type"] == "Ethernet"


def test_json_preview_supports_generic_model_records() -> None:
    content = b"""[
  {
    "domain": "rail",
    "hardware": "DoorController",
    "device_type": "ECU",
    "interface": "TRDP",
    "protocol": "Ethernet",
    "message": "DoorCommand",
    "signal": "OpenRequest"
  }
]"""

    plan = preview_import("rail-model.json", content)

    assert plan["format"] == "json"
    assert plan["hardware_nodes"][0]["domain"] == "rail"
    assert plan["interfaces"][0]["interface_type"] == "Ethernet"
    assert plan["messages"][0]["name"] == "DoorCommand"
    assert plan["signals"][0]["name"] == "OpenRequest"


def test_text_trace_preview_imports_frame_messages() -> None:
    content = b"""
   0.000001 1 18FF50E5x Rx d 8 01 02 03 04 05 06 07 08
   0.010000 CAN_ID=0x123 DLC=4 00 01 02 03
"""

    plan = preview_import("machine.asc", content)

    assert plan["format"] == "asc"
    assert plan["counts"]["hardware_nodes"] == 1
    assert plan["counts"]["messages"] == 2
    assert {message["message_id_hex"] for message in plan["messages"]} == {"0x18FF50E5", "0x123"}


def test_preview_rejects_legacy_binary_excel() -> None:
    with pytest.raises(EngineeringValidationError, match="Unterstützt"):
        preview_import("legacy.xls", b"legacy")
