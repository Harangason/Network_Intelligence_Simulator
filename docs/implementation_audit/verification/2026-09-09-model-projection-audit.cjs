// Read-only reproduction of the current UI projection on the exported project.
// Run from repository root: node docs/implementation_audit/verification/2026-09-09-model-projection-audit.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const ts = require('../../../frontend/node_modules/typescript');
const base = 'docs/implementation_audit/verification/';
const bundle = JSON.parse(fs.readFileSync(base + '2026-09-09-nis-project-bundle.json', 'utf8').replace(/^\uFEFF/, ''));
const source = fs.readFileSync('frontend/src/components/structure-tree-workbench.tsx', 'utf8');
const style = fs.readFileSync('frontend/src/lib/engineering-object-style.ts', 'utf8');
const names = style.slice(style.indexOf('export function engineeringHardwareName'), style.indexOf('export function isMergedHardwareAlias')).replace('export function', 'function');
const treeLogic = source.slice(source.indexOf('const LEVELS:'), source.indexOf('function emptySelection'));
const script = ts.transpileModule(names + '\n' + treeLogic + '\nglobalThis.buildGroups = buildSystemFrameGroups;', {compilerOptions: {target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS}}).outputText;
const context = vm.createContext({});
vm.runInContext(script, context);
const data = bundle.source_data;
const hardware = data.engineering_hardware_nodes;
const groups = context.buildGroups(hardware);
const treeOwners = Object.fromEntries(groups.flatMap(group => group.members.map(member => [member.id, {id: group.owner?.id ?? null, name: group.owner?.name ?? null, basis: group.basis}])));
const hw = Object.fromEntries(hardware.map(item => [item.id, item]));
const functions = Object.fromEntries(data.engineering_functions.map(item => [item.id, item]));
const interfaces = Object.fromEntries(data.engineering_interfaces.map(item => [item.id, item]));
const messages = Object.fromEntries(data.engineering_messages.map(item => [item.id, item]));
const ports = Object.fromEntries(data.engineering_hardware_interfaces.map(item => [item.id, item]));
const direct = Object.values(interfaces).filter(item => !item.function_id);
const noFunctionSignals = data.engineering_signals.filter(item => !interfaces[messages[item.message_id]?.interface_id]?.function_id);
const topology = bundle.workflow.topology;
const topoNodes = Object.fromEntries(topology.nodes.map(item => [item.id, item]));
const physicalOwners = {};
for (const edge of topology.edges) {
  const a = topoNodes[edge.source]?.engineeringId;
  const b = topoNodes[edge.target]?.engineeringId;
  for (const [endpoint, owner] of [[a,b], [b,a]]) {
    if (['SensorController', 'ActuatorController'].includes(hw[endpoint]?.device_type) && hw[owner]?.device_type === 'ECU') {
      (physicalOwners[endpoint] ??= new Set()).add(owner);
    }
  }
}
const ownershipDifferences = Object.entries(physicalOwners).filter(([id, owners]) => owners.size === 1 && !owners.has(treeOwners[id]?.id)).map(([id, owners]) => ({name:hw[id].name,id,physical_owner:hw[[...owners][0]].name,structure_tree_owner:treeOwners[id]?.name}));
const networkIdsByPort = {};
for (const node of topology.nodes) {
  for (const port of node.ports ?? []) {
    if (port.hardwareInterfaceId && port.physicalNetworkId) {
      (networkIdsByPort[port.hardwareInterfaceId] ??= new Set()).add(port.physicalNetworkId);
    }
  }
}
const reusedPorts = Object.entries(networkIdsByPort).filter(([,networks]) => networks.size > 1).map(([id,networks]) => ({id,name:ports[id]?.name,canonical_network:ports[id]?.network_ref,physical_networks:[...networks]}));
const acceptedAssignments = Object.fromEntries((bundle.workflow.context.equipment_assignment_feedback ?? []).filter(item => item.accepted).map(item => [item.endpoint_name,item]));
for (const item of ownershipDifferences) item.accepted_wizard_owner = acceptedAssignments[item.name]?.controller_name ?? null;
const egrHardware = hardware.find(item => item.name === 'EGRValvePosition');
const egrInterface = Object.values(interfaces).find(item => item.hardware_node_id === egrHardware.id);
const egrRoute = data.engineering_routing_entries.find(item => item.source?.node_id === egrHardware.id);
const egrEdges = topology.edges.filter(item => (item.routingEntryIds ?? []).includes(egrRoute.id));
const egrExample = {
  accepted_wizard_assignment:acceptedAssignments.EGRValvePosition,
  hardware:{id:egrHardware.id,name:egrHardware.name,device_class:egrHardware.device_class},
  interface:{id:egrInterface.id,name:egrInterface.name,function_id:egrInterface.function_id,hardware_node_id:egrInterface.hardware_node_id},
  route:{id:egrRoute.id,name:egrRoute.name,source:egrRoute.source,destinations:egrRoute.destinations,approval_state:egrRoute.approval_state,valid:egrRoute.validation?.valid},
  topology_edges:egrEdges.map(edge => ({id:edge.id,source:edge.source,target:edge.target,source_port:topoNodes[edge.source]?.ports.find(port => port.id===edge.sourcePort),target_port:topoNodes[edge.target]?.ports.find(port => port.id===edge.targetPort)})),
};
const report = {
  project_id:bundle.project_id,
  counts:{hardware:hardware.length,functions:Object.keys(functions).length,hardware_interfaces:Object.keys(ports).length,interfaces:Object.keys(interfaces).length,messages:Object.keys(messages).length,signals:data.engineering_signals.length},
  false_orphan_interfaces:direct.filter(item => hw[item.hardware_node_id]).length,
  actual_missing_interface_parent:direct.filter(item => !hw[item.hardware_node_id]).length,
  signals_without_function:noFunctionSignals.length,
  signal_owner_classes:[...new Set(noFunctionSignals.map(item => hw[interfaces[messages[item.message_id]?.interface_id]?.hardware_node_id]?.device_class))],
  hardware_explicit_owners:hardware.filter(item => item.identity?.system_owner_id).length,
  topology_explicit_owners:topology.nodes.filter(item => item.systemOwnerId).length,
  accepted_wizard_assignments:Object.keys(acceptedAssignments).length,
  ui_differences_matching_accepted_wizard_assignments:ownershipDifferences.filter(item => item.accepted_wizard_owner === item.physical_owner).length,
  ui_vs_physical_owner_differences:ownershipDifferences,
  hardware_interfaces_reused_on_separate_physical_networks:reusedPorts,
  egr_example:egrExample,
  canonical_message_port_owner_mismatches:Object.values(messages).filter(item => ports[item.hardware_interface_id]?.hardware_node_id !== interfaces[item.interface_id]?.hardware_node_id).map(item => item.name),
};
fs.writeFileSync(base + '2026-09-09-model-projection-audit.json', JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({...report,ui_vs_physical_owner_differences:ownershipDifferences.length,hardware_interfaces_reused_on_separate_physical_networks:reusedPorts.length,egr_example:undefined},null,2));
