import assert from "node:assert/strict";
import test from "node:test";

import {
  topologyClusterFamilyForKey,
  topologyClusterForText,
  topologySystemIdentityForText,
} from "./topology-cluster-knowledge.ts";

test("automotive systems remain separate while related systems share a domain cluster", () => {
  const motor = topologyClusterForText("Motorsteuerung", "automotive");
  const exhaust = topologyClusterForText("Abgasnachbehandlung", "automotive");
  const transmission = topologyClusterForText("Getriebesteuerung", "automotive");
  const steering = topologyClusterForText("Lenkung", "automotive");
  const lighting = topologyClusterForText("Innenlicht", "automotive");
  const comfort = topologyClusterForText("Fahrersitz", "automotive");

  assert.notEqual(motor.key, exhaust.key);
  assert.notEqual(motor.key, transmission.key);
  assert.deepEqual(
    topologyClusterFamilyForKey(motor.key, "automotive"),
    topologyClusterFamilyForKey(exhaust.key, "automotive"),
  );
  assert.deepEqual(
    topologyClusterFamilyForKey(motor.key, "automotive"),
    topologyClusterFamilyForKey(transmission.key, "automotive"),
  );
  assert.notDeepEqual(
    topologyClusterFamilyForKey(motor.key, "automotive"),
    topologyClusterFamilyForKey(steering.key, "automotive"),
  );
  assert.deepEqual(
    topologyClusterFamilyForKey(lighting.key, "automotive"),
    topologyClusterFamilyForKey(comfort.key, "automotive"),
  );
});

test("automotive body and infotainment vocabulary maps into stable outer clusters", () => {
  for (const name of ["Fahrertuer", "FondtuerLinks", "Heckklappe", "Schiebedach", "Beifahrersitz"]) {
    const cluster = topologyClusterForText(name, "automotive");
    assert.equal(topologyClusterFamilyForKey(cluster.key, "automotive").key, "body_comfort");
  }
  for (const name of ["Soundsystem", "Konnektivitaet", "Telematik"]) {
    const cluster = topologyClusterForText(name, "automotive");
    assert.equal(topologyClusterFamilyForKey(cluster.key, "automotive").key, "infotainment");
  }
});

test("industry profiles do not leak automotive cluster semantics", () => {
  const automotive = topologyClusterForText("Motor", "automotive");
  const automation = topologyClusterForText("Motor", "industrial_automation");

  assert.equal(automotive.key, "powertrain_motor");
  assert.equal(automation.key, "motion");
});

test("system aliases merge only exact duplicate system identities", () => {
  assert.equal(topologySystemIdentityForText("Motion-ECU", "automotive"), "motorsteuerung");
  assert.equal(topologySystemIdentityForText("Motor", "automotive"), "motorsteuerung");
  assert.equal(topologySystemIdentityForText("Motorsteuerung", "automotive"), "motorsteuerung");
  assert.equal(topologySystemIdentityForText("Getriebe", "automotive"), "getriebesteuerung");
  assert.notEqual(
    topologySystemIdentityForText("Abgasnachbehandlung", "automotive"),
    topologySystemIdentityForText("Motorsteuerung", "automotive"),
  );
  assert.notEqual(
    topologySystemIdentityForText("Motor", "industrial_automation"),
    topologySystemIdentityForText("Motorsteuerung", "industrial_automation"),
  );
});
