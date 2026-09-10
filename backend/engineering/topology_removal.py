"""Disconnect removed drawing connections without deleting authored devices or payloads."""
from copy import deepcopy
from hashlib import sha256


def detached_topology(previous, current):
    result = deepcopy(current)
    old_ports = {p['id']: p for n in previous.get('nodes') or [] for p in n.get('ports') or []}
    old_connected = {e.get(side + 'Port') for e in previous.get('edges') or [] for side in ('source', 'target')}
    connected = {e.get(side + 'Port') for e in current.get('edges') or [] for side in ('source', 'target')}
    ports = [p for n in result.get('nodes') or [] for p in n.get('ports') or []]
    active_channels = {p.get('hardwareInterfaceId') for p in ports if p['id'] in connected}
    for port in ports:
        old = old_ports.get(port['id'], {})
        if port['id'] not in old_connected or port['id'] in connected or port.get('hardwareInterfaceId') in active_channels:
            continue
        if port.get('physicalNetworkId') != old.get('physicalNetworkId'):
            continue
        # A released port remains usable but is no longer a member of the old bus.
        digest = sha256((str(port.get('hardwareInterfaceId') or port['id']) + '\n' + str(old.get('physicalNetworkId'))).encode()).hexdigest()[:12]
        port['physicalNetworkId'] = 'network-' + port['bus'] + '-free-' + digest
        port.pop('physicalNetworkName', None)
    return result


def retire_removed_connections(previous, current, *, actor='network-editor'):
    """Called inside the topology save transaction, after endpoint reconciliation."""
    from .relations import delete_relation
    from .repository import NotFoundError, get_object, update_object

    kept = {e.get('engineeringRelationId') for e in current.get('edges') or []}
    removed = {e.get('engineeringRelationId') for e in previous.get('edges') or []} - kept - {None, ''}
    for identifier in removed:
        try:
            delete_relation(identifier)
        except NotFoundError:
            pass
    old_channels = {p.get('hardwareInterfaceId') for n in previous.get('nodes') or [] for p in n.get('ports') or []}
    kept_channels = {p.get('hardwareInterfaceId') for n in current.get('nodes') or [] for p in n.get('ports') or []}
    for identifier in old_channels - kept_channels - {None, ''}:
        try:
            channel = get_object('HardwareNetworkInterface', identifier)
        except NotFoundError:
            continue
        # Hardware and message definitions survive removing their canvas connector.
        # Clearing network_ref ensures exports/validation cannot still claim a connection.
        capabilities = {key: value for key, value in (channel.get('capabilities') or {}).items()
                        if key not in {'network_id', 'topology_id', 'topology_node_id', 'topology_port_id', 'topology_port_ids'}}
        changes = {}
        if channel.get('network_ref'):
            changes['network_ref'] = None
        if capabilities != (channel.get('capabilities') or {}):
            changes['capabilities'] = capabilities
        if changes:
            update_object('HardwareNetworkInterface', identifier, changes)

    # The regular reconciler only visits route IDs still present in current edges.
    # Removed paths must invalidate imported/manual routes too, including the last edge.
    from uuid import UUID
    from psycopg.types.json import Jsonb
    from .db import get_connection
    from .project_context import current_project_id
    from .routing.repository import _audit

    kept_edges = {e['id'] for e in current.get('edges') or []}
    route_ids = set()
    for edge in previous.get('edges') or []:
        if edge['id'] in kept_edges:
            continue
        for raw in [edge.get('routingEntryId'), *(edge.get('routingEntryIds') or [])]:
            try:
                route_ids.add(str(UUID(str(raw))))
            except (ValueError, TypeError):
                continue
    if route_ids:
        with get_connection() as connection:
            rows = connection.execute(
                "SELECT * FROM engineering_routing_entries WHERE project_id=%s AND id=ANY(%s::uuid[]) FOR UPDATE",
                (current_project_id(), sorted(route_ids))).fetchall()
            for row in rows:
                if row.get('status') in {'REJECTED', 'SUPERSEDED'}:
                    continue
                reason = 'Eine physische Verbindung der Route wurde im Netzwerkeditor gelöscht.'
                validation = deepcopy(row.get('validation') or {})
                warnings = [w for w in validation.get('warnings') or [] if w.get('code') != 'PHYSICAL_PATH_REMOVED']
                validation.update(valid=False, outdated_reason=reason,
                                  warnings=[*warnings, {'code':'PHYSICAL_PATH_REMOVED', 'message':reason}])
                after = connection.execute(
                    "UPDATE engineering_routing_entries SET status='OUTDATED', approval_state='PENDING', "
                    "review_state='IN_REVIEW', validation=%s, modified_by=%s, modified_at=now() "
                    "WHERE project_id=%s AND id=%s RETURNING *",
                    (Jsonb(validation), actor, current_project_id(), row['id'])).fetchone()
                _audit(connection, str(row['id']), 'NETWORK_PATH_REMOVED', actor=actor, before=row, after=after, reason=reason)
