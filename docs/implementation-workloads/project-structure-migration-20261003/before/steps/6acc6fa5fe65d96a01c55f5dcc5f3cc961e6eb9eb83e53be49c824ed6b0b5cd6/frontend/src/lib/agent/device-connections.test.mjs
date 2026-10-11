import assert from "node:assert/strict";
import test from "node:test";
import { selectDeviceConnectionInTask } from "./device-connections.ts";

test("successive device choices preserve every reviewed connection", () => {
  let task = "1 Raspberry Pi mit Drucksensor und Relais";
  task = selectDeviceConnectionInTask(task, "RaspberryPi", "I2C");
  task = selectDeviceConnectionInTask(task, "Druck", "I2C");
  task = selectDeviceConnectionInTask(task, "Relaisausgang", "GPIO");

  assert.match(task, /- Geräteanschlüsse: \{"RaspberryPi":"I2C","Druck":"I2C","Relaisausgang":"GPIO"\}$/m);
});
