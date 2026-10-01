import assert from "node:assert/strict";
import test from "node:test";
import {
  normalizeStudioTheme,
  readStudioTheme,
  STUDIO_THEME_STORAGE_KEY,
} from "./studio-theme.ts";

test("normalizes supported studio themes", () => {
  assert.equal(normalizeStudioTheme("light"), "light");
  assert.equal(normalizeStudioTheme("dark"), "dark");
  assert.equal(normalizeStudioTheme("system"), null);
  assert.equal(normalizeStudioTheme(undefined), null);
});

test("reads a persisted theme and defaults invalid values to dark", () => {
  const storage = { getItem: (key) => key === STUDIO_THEME_STORAGE_KEY ? "light" : null };
  assert.equal(readStudioTheme(storage), "light");
  assert.equal(readStudioTheme({ getItem: () => "invalid" }), "dark");
  assert.equal(readStudioTheme(), "dark");
});
