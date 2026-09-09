import assert from "node:assert/strict";
import test from "node:test";
import { engineeringParent, engineeringOwnership, canAssignEngineeringParent, explicitSystemOwner } from "./engineering-ownership.ts";

function fixture() {
  const hardware = { id:"sensor", name:"EGRValvePosition", object_type:"HardwareNode", device_type:"SensorController", device_class:1, identity:{system_owner_id:"ecu"} };
  const ecu = { id:"ecu", name:"Abgasnachbehandlung", object_type:"HardwareNode", device_type:"ECU", device_class:4, identity:{} };
  const fn = { id:"function", name:"Steuerung", object_type:"Function", hardware_node_id:"ecu" };
  const intf = { id:"interface", object_type:"Interface", function_id:null, hardware_node_id:"sensor" };
  const message = { id:"message", object_type:"Message", interface_id:"interface" };
  const signal = { id:"signal", object_type:"Signal", message_id:"message" };
  return {hardware,ecu,fn,intf,message,signal,objects:new Map([hardware,ecu,fn,intf,message,signal].map(item=>[item.id,item]))};
}

test("direct sensor chain has a real parent, hardware and confirmed system without a fake function", () => {
  const f=fixture();
  assert.deepEqual(engineeringParent(f.intf),{id:"sensor",type:"HardwareNode",field:"hardware_node_id",relation:"HAS_INTERFACE"});
  const owner=engineeringOwnership(f.signal,f.objects);
  assert.equal(owner.hardware,f.hardware);
  assert.equal(owner.system,f.ecu);
  assert.equal(owner.function,null);
  assert.equal(owner.error,null);
  assert.equal(canAssignEngineeringParent(f.intf,f.hardware),true);
  assert.equal(canAssignEngineeringParent(f.intf,f.ecu),false);
  assert.equal(canAssignEngineeringParent(f.intf,f.fn),true);
});

test("real missing references and broken function links are not silently repaired", () => {
  const f=fixture();
  f.intf.function_id="deleted-function";
  assert.match(engineeringOwnership(f.signal,f.objects).error,/function_id/);
  assert.equal(engineeringOwnership(f.signal,f.objects).hardware,null);
});

test("system membership survives rename and never comes from name similarity", () => {
  const f=fixture();
  f.hardware.name="CompletelyRenamed";
  assert.equal(explicitSystemOwner(f.hardware,f.objects),f.ecu);
  f.hardware.identity={};
  f.hardware.name="AbgasnachbehandlungSensor";
  assert.equal(explicitSystemOwner(f.hardware,f.objects),null);
});
