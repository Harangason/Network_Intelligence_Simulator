import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { extractEngineeringSpecification } from '../frontend/src/lib/agent/engineering-specification.ts';
const cases=JSON.parse(fs.readFileSync(new URL('./industry40.normalized.json',import.meta.url),'utf8')).test_cases;
const oracle=JSON.parse(fs.readFileSync(new URL('./reports/industry40-results.json',import.meta.url),'utf8'));
for(const c of cases)test(c.test_id+' explicitly stated inventory counts only',()=>{
  const actual=extractEngineeringSpecification(c.input,{},'custom').targetCounts;
  const expected=oracle.find(x=>x.test_id===c.test_id).expected_counts;
  const errors=Object.entries(expected).filter(([k,v])=>v!==null&&v!==actual[k]).map(([k,v])=>`${k}: ${actual[k]} instead of ${v}`);
  assert.deepEqual(errors,[],c.test_id+': '+errors.join('; '));
});
