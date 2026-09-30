import assert from "node:assert/strict";
import test from "node:test";
import { dateAtZone, dayInZone } from "../src/lib/dates.ts";

test("fechas de calendario usan el día del atleta sin depender del navegador", () => {
  assert.equal(dayInZone("2026-09-21T01:00:00Z", "America/Mexico_City"), "2026-09-20");
  assert.equal(dayInZone("2026-09-21T01:00:00Z", "Pacific/Auckland"), "2026-09-21");
  assert.equal(dateAtZone("2026-09-20", "America/Mexico_City"), "2026-09-20T13:00:00.000Z");
});

test("ida y vuelta conserva día local en extremos y cambios de horario", () => {
  for (const zone of ["Pacific/Auckland", "America/New_York", "Europe/Madrid", "Pacific/Honolulu"]) {
    for (const day of ["2026-03-08", "2026-09-20", "2026-11-01"]) {
      assert.equal(dayInZone(dateAtZone(day, zone), zone), day);
    }
  }
});
