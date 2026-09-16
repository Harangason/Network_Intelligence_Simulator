import { extractEngineeringSpecification } from '../frontend/src/lib/agent/engineering-specification.ts';
import fs from 'node:fs';
const cases=JSON.parse(fs.readFileSync('.tool-checker/industry40.normalized.json','utf8')).test_cases;
const results=cases.map(c=>({test_id:c.test_id,input:c.input,result:extractEngineeringSpecification(c.input,{},'custom')}));
fs.writeFileSync('.tool-checker/parser-results.json',JSON.stringify(results,null,2));
for(const r of results)console.log(r.test_id,JSON.stringify({targets:r.result.targetCounts,chains:r.result.chains.length,types:r.result.chains.reduce((a,c)=>(a[c.device_type]=(a[c.device_type]||0)+1,a),{}),names:r.result.chains.slice(0,8).map(c=>c.hardware_name)}));
