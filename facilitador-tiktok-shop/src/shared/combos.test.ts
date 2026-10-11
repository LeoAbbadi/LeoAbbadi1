import { test } from "node:test";
import assert from "node:assert/strict";
import { planVideos, totalCombinations } from "./combos.ts";

const ids = (p: string, n: number) => Array.from({ length: n }, (_, i) => `${p}${i + 1}`);

test("10 ganchos × 5 corpos × 3 CTAs = 150 vídeos únicos", () => {
  const plan = planVideos(ids("g", 10), ids("c", 5), ids("t", 3), 1000);
  assert.equal(totalCombinations(10, 5, 3), 150);
  assert.equal(plan.length, 150);
  assert.equal(new Set(plan.map((v) => `${v.hook}${v.body}${v.cta}`)).size, 150);
});

test("os primeiros vídeos usam ganchos diferentes e saem como Original", () => {
  const plan = planVideos(ids("g", 10), ids("c", 5), ids("t", 3), 150);
  const first10 = plan.slice(0, 10);
  assert.equal(new Set(first10.map((v) => v.hook)).size, 10);
  assert.ok(first10.every((v) => v.label === "original"));
  assert.ok(plan.slice(10).every((v) => v.label !== "original"));
});

test("Parecidos ficam no fim da fila", () => {
  const plan = planVideos(ids("g", 10), ids("c", 5), ids("t", 3), 150);
  const firstParecido = plan.findIndex((v) => v.label === "parecido");
  // 10 ganchos × 5 corpos = 50 pares inéditos antes de repetir um par
  assert.equal(firstParecido, 50);
  assert.ok(plan.slice(firstParecido).every((v) => v.label === "parecido"));
});

test("nunca repete o mesmo corpo em dois posts seguidos quando dá pra evitar", () => {
  const plan = planVideos(ids("g", 10), ids("c", 5), ids("t", 3), 150);
  for (let i = 1; i < plan.length; i++) assert.notEqual(plan[i]!.body, plan[i - 1]!.body);
});

test("pedindo menos vídeos, recebe os mais diferentes", () => {
  const plan = planVideos(ids("g", 4), ids("c", 4), ids("t", 2), 8);
  assert.equal(plan.length, 8);
  assert.equal(plan.filter((v) => v.label === "original").length, 4);
  assert.ok(plan.every((v) => v.label !== "parecido"));
});

test("calendário respeita posts por dia", () => {
  const plan = planVideos(ids("g", 3), ids("c", 2), ids("t", 1), 6, 2);
  assert.deepEqual(plan.map((v) => v.dayOffset), [0, 0, 1, 1, 2, 2]);
});

test("slot vazio gera zero vídeos", () => {
  assert.equal(planVideos(ids("g", 3), [], ids("t", 1), 10).length, 0);
});
