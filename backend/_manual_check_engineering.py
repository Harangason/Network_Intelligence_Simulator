"""Manuelles Rauchtest-Skript für die Engineering-API (nicht Teil der Test-Suite)."""
from __future__ import annotations

import json
import sys

sys.path.insert(0, ".")

from app import create_app  # noqa: E402

app = create_app(testing=True)
client = app.test_client()


def show(label, resp):
    print(f"--- {label}: {resp.status_code} ---")
    try:
        print(json.dumps(resp.get_json(), indent=2, default=str)[:1500])
    except Exception as e:
        print("no json", e)


# health
show("engineering health", client.get("/api/engineering/health"))
show("schema", client.get("/api/engineering/schema"))

# create hardware node
hw_resp = client.post(
    "/api/engineering/hardware-nodes",
    json={
        "name": "ECU-Front-Left",
        "description": "Test-ECU",
        "domain": "automotive",
        "device_type": "ECU",
        "identity": {"serial": "123"},
        "created_by": "smoketest",
    },
)
show("create hardware node", hw_resp)
hw_id = hw_resp.get_json()["id"]

# get it
show("get hardware node", client.get(f"/api/engineering/hardware-nodes/{hw_id}"))

# update it
show(
    "update hardware node",
    client.patch(
        f"/api/engineering/hardware-nodes/{hw_id}",
        json={"description": "Updated description", "modified_by": "smoketest"},
    ),
)

# versions
show("versions", client.get(f"/api/engineering/hardware-nodes/{hw_id}/versions"))

# create interface linked to hw node
iface_resp = client.post(
    "/api/engineering/interfaces",
    json={
        "name": "CAN0",
        "hardware_node_id": hw_id,
        "interface_type": "CAN_FD",
        "created_by": "smoketest",
    },
)
show("create interface", iface_resp)
iface_id = iface_resp.get_json()["id"]

# relation
rel_resp = client.post(
    "/api/engineering/relations",
    json={
        "relation_type": "HAS_INTERFACE",
        "source_type": "HardwareNode",
        "source_id": hw_id,
        "target_type": "Interface",
        "target_id": iface_id,
        "created_by": "smoketest",
    },
)
show("create relation", rel_resp)

show("list relations for hw node", client.get(f"/api/engineering/relations?object_type=HardwareNode&object_id={hw_id}"))

# invalid enum
show(
    "invalid device_type",
    client.post(
        "/api/engineering/hardware-nodes",
        json={"name": "bad", "device_type": "NotARealType"},
    ),
)

# delete not-draft should fail after approval_state change? still draft by default so delete works
del_resp = client.delete(f"/api/engineering/interfaces/{iface_id}")
print(f"--- delete interface: {del_resp.status_code} ---")

# cleanup hardware node
del_resp2 = client.delete(f"/api/engineering/hardware-nodes/{hw_id}")
print(f"--- delete hardware node: {del_resp2.status_code} ---")

print("DONE")
