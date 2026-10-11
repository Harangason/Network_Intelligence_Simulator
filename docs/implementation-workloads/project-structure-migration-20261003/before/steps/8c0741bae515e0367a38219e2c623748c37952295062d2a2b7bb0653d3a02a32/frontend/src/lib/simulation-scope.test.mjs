import assert from "node:assert/strict";
import test from "node:test";
import { simulationScopeFrom, simulationScopeValid, sameSimulationScope } from "./simulation-scope.ts";

test("scope defaults to the whole model and explicit exclusions require a reason", () => {
  assert.equal(simulationScopeFrom(null).include_all, true);
  const selected = simulationScopeFrom({mode:"MESSAGE",message_ids:["m2","m1","m1"]});
  assert.deepEqual(selected.message_ids,["m1","m2"]);
  assert.equal(simulationScopeValid(selected),false);
  assert.equal(simulationScopeValid({...selected,reason:"Subsystemtest"}),true);
  assert.equal(simulationScopeValid({...selected,message_ids:[],reason:"Subsystemtest"}),false);
});

test("preflight and runner compare normalized persisted IDs rather than order or unused selection", () => {
  const a=simulationScopeFrom({mode:"SIGNAL",signal_ids:["s2","s1"],reason:"Subsystemtest"});
  const b=simulationScopeFrom({...a,signal_ids:["s1","s2"]});
  assert.equal(sameSimulationScope(a,b),true);
  assert.equal(sameSimulationScope(a,{...b,signal_ids:["s1"]}),false);
  assert.deepEqual(simulationScopeFrom({mode:"ALL",message_ids:["stale"]}).message_ids,[]);
});
