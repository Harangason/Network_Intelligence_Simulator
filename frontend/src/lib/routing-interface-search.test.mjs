import test from 'node:test';
import assert from 'node:assert/strict';
import { endpointInterfaceChoices } from './routing-interface-search.ts';
import { payloadScopeConflicts } from './routing-payload-scope.ts';

const iface = (id, node, network, type = 'CAN_FD') => ({ id, name: id, hardware_node_id: node, interface_type: type,
  physicalBindings: [{ id: network, name: network, protocol: type, portId: `${id}-port` }] });

test('gateway receive options prioritize the final physical leg, not the source protocol', () => {
  const interfaces = [iface('A local IO', 'adas', 'local-can'), iface('ETH_ADAS', 'adas', 'ETH_System_01', 'Ethernet'), iface('gateway-out', 'gateway', 'ETH_System_01', 'Ethernet')];
  const before = JSON.stringify(interfaces);
  const result = endpointInterfaceChoices(interfaces, 'adas', 'gateway', 'CAN_FD');
  assert.equal(result[0].item.id, 'ETH_ADAS'); assert.equal(result[0].common[0].id, 'ETH_System_01');
  assert.equal(result[1].common.length, 0);
  assert.equal(JSON.stringify(interfaces), before);
});

test('interface search combines name, technology and readable physical bus; no other device leaks in', () => {
  const interfaces = [iface('Climate Status', 'climate', 'ETH_Klima_01', 'Ethernet'), iface('Climate Local', 'climate', 'LIN_Klima', 'LIN'), iface('Climate Status', 'other', 'ETH_Klima_01', 'Ethernet')];
  assert.deepEqual(endpointInterfaceChoices(interfaces, 'climate', '', '', 'status UND ethernet klima').map(c => c.item.name), ['Climate Status']);
  assert.equal(endpointInterfaceChoices(interfaces, 'climate', '', '', 'not-present').length, 0);
});

test('local I/O is kept inside its canonical recipient boundary; explicit device and function outputs remain selectable', () => {
  const message = { id: 'command', routingScope: { restricted: true, scope: 'LOCAL_IO', consumer_refs: ['actuator'] } };
  assert.equal(payloadScopeConflicts([message], ['adas'], {}, []).length, 1);
  assert.equal(payloadScopeConflicts([message], ['actuator'], {}, []).length, 0);
  assert.equal(payloadScopeConflicts([{ id: 'thermometer', routingScope: { restricted: false } }], ['adas'], {}, []).length, 0);
  assert.equal(payloadScopeConflicts([{ id: 'status', routingScope: { restricted: false, scope: 'FUNCTION_OUTPUT' } }], ['adas'], {}, []).length, 0);
  assert.equal(payloadScopeConflicts([{ id: 'not-loaded' }], ['adas'], {}, []).length, 1);
});
