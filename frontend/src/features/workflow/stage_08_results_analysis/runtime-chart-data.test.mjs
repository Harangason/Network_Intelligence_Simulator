import test from 'node:test';
import assert from 'node:assert/strict';
import { loadWindow, extremaSample, zoomWindow, jitterAssessment, forecastUnderAssumptions } from './runtime-chart-data.ts';
test('overlay preserves real times, excludes other networks and invalid points', () => {
  const points=[{network_id:'a',time_s:0,load_percent:0},{network_id:'b',time_s:1,load_percent:2},{network_id:'c',time_s:1,load_percent:8},{network_id:'a',time_s:NaN,load_percent:1},{network_id:'a',time_s:1,load_percent:-1}];
  assert.deepEqual(loadWindow(points,['a','b'],0,1),points.slice(0,2));
  assert.deepEqual(loadWindow(points,[],0,1),[]);
});
test('sampling retains spike, endpoints and original objects', () => {
  const points=Array.from({length:2000},(_,i)=>({time_s:i,load_percent:i===555?999:1}));
  const sampled=extremaSample(points);
  assert(sampled.includes(points[0]) && sampled.includes(points.at(-1)) && sampled.includes(points[555]));
  assert(sampled.every(p=>points.includes(p)) && sampled.length<=800);
});
test('zoom clamps edges and never exceeds the observed time range',()=>{
  assert.deepEqual(zoomWindow(0,10,10,.5),[2.5,7.5]);
  assert.deepEqual(zoomWindow(8,10,10,2),[6,10]);
  assert.deepEqual(zoomWindow(2,8,10,10),[0,10]);
});
test('jitter needs observed intervals and an explicit limit, including zero',()=>{
  const r={received_event_count:2,configured_cycle_ms:10,maximum_jitter_ms:0,jitter_limit_ms:0};
  assert.equal(jitterAssessment(r),'Innerhalb der Grenze');
  assert.equal(jitterAssessment({...r,maximum_jitter_ms:1}),'Grenze überschritten');
  assert.equal(jitterAssessment({...r,jitter_limit_ms:null}),'Grenze offen');
  assert.equal(jitterAssessment({...r,received_event_count:1}),'Keine bewertbaren Intervalle');
  assert.equal(jitterAssessment({...r,configured_cycle_ms:0}),'Keine bewertbaren Intervalle');
});
test('forecast uses only explicit stored assumptions; incomplete coverage is unknown',()=>{
  const a={capacity_verified:false,simulation_capacity:{status:'CALCULATED_UNDER_ASSUMPTIONS',peak_load_percent:30,capacity_reserve_percent:70}};
  assert.deepEqual(forecastUnderAssumptions({networks:[a]}),{peak:30,reserve:70,networks:1});
  assert.equal(forecastUnderAssumptions({networks:[a,{capacity_verified:false}]}).peak,null);
  assert.equal(forecastUnderAssumptions({overview:{max_peak_load_percent:66}}),null);
  assert.equal(forecastUnderAssumptions({networks:[{...a,simulation_capacity:{...a.simulation_capacity,peak_load_percent:null}}]}).peak,null);
});
