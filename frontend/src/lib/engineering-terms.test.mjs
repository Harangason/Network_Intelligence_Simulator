import assert from "node:assert/strict";
import test from "node:test";
import { engineeringTokens, containsEngineeringTerm } from "./engineering-terms.ts";
import { topologyClusterForText } from "./topology-cluster-knowledge.ts";

test("technical compounds retain their meaning and separate German and CamelCase words", () => {
  assert.deepEqual(engineeringTokens("Fahrersitz"), ["fahrer", "sitz"]);
  assert.deepEqual(engineeringTokens("Fahrwerk"), ["fahrwerk"]);
  assert.deepEqual(engineeringTokens("Dämpferregelung"), ["daempfer", "regelung"]);
  assert.deepEqual(engineeringTokens("FrontLeftSuspensionTravel"), ["front", "left", "suspension", "travel"]);
  assert.deepEqual(engineeringTokens("EGRValvePosition"), ["egr", "valve", "position"]);
  assert.equal(containsEngineeringTerm("Radarverarbeitung", "rad"), false);
  assert.equal(containsEngineeringTerm("Fahrersitz", "fahrwerk"), false);
  assert.equal(containsEngineeringTerm("DriverSeat", "drive"), false);
});

test("the system identity outweighs incidental words in descriptions", () => {
  assert.equal(topologyClusterForText("Fahrersitz Fahrwerk CAN Steuerung", "automotive").key, "body_comfort");
  assert.equal(topologyClusterForText("Fahrwerk Fahrersitz CAN Steuerung", "automotive").key, "chassis");
  assert.equal(topologyClusterForText("FrontLeftSuspensionTravel", "automotive").key, "chassis");
  assert.equal(topologyClusterForText("OilTemperature", "automotive").key, "powertrain_motor");
  assert.equal(topologyClusterForText("ExhaustGasTemperature", "automotive").key, "powertrain_exhaust");
});
