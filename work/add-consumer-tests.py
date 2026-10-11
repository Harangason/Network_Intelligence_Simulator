from pathlib import Path
p=Path('frontend/src/lib/technology-parameters.test.mjs')
s=p.read_text(encoding='utf-8').replace('booleanParameterValue,','booleanParameterValue, numericParameterValue,',1)
s+='''

test('wide protocol integers use exact decimal bounds and identical confirmation proof', () => {
  const field = {key:'sp_alias',label:'Alias',type:'number',integer:true,numeric_encoding:'DECIMAL_STRING',decimal_min:'0',decimal_max:'18446744073709551615'};
  const value = numericParameterValue(field,'18446744073709551615');
  assert.equal(value,'18446744073709551615');
  assert.throws(() => numericParameterValue(field,'18446744073709551616'));
  assert.throws(() => numericParameterValue(field,'1.2'));
  assert.throws(() => numericParameterValue(field,'1e18'));
  const profile = {id:'sparkplug_b',parameter_schema:[field]};
  const saved = confirmTechnologyParameters({},profile,{sp_alias:value});
  const loaded = JSON.parse(JSON.stringify(saved));
  assert.equal(technologyParameterValues(loaded,profile).sp_alias,value);
  assert.equal(technologyParameterUnverified(loaded,'sp_alias','sparkplug_b'),false);
  assert.throws(() => numericParameterValue({label:'Address',integer:true,min:0,max:255},'1.5'));
});

test('conditional proposals resolve dependency order and retain confirmed actual peer configuration', () => {
  const timeout = {key:'timeout',conditional_defaults:[{when:{mode:'STANDARD',version:'A'},value:100},{when:{mode:'STANDARD',version:'A'},value:100}]};
  const profile = {id:'actual',parameter_schema:[timeout,{key:'version',conditional_defaults:[{when:{mode:'STANDARD'},value:'A'}]},{key:'mode',default:'STANDARD'}]};
  assert.equal(technologyParameterValues({},profile).timeout,100);
  assert.equal(conditionalParameterDefault(timeout,{mode:'STANDARD',version:'A'}),100);
  const previous = {technology:'actual',technology_parameters:{actual:{values:{mode:'STANDARD',version:'A',timeout:200},provenance:{timeout:{value:200,source:'TECHNOLOGY_DEFAULT_PROPOSAL',status:'REVIEW_REQUIRED'}}}}};
  assert.equal(technologyParameterValues(previous,profile).timeout,100);
  const confirmed = confirmTechnologyParameters({},profile,{mode:'STANDARD',version:'A',timeout:200});
  assert.equal(technologyParameterValues(confirmed,profile).timeout,200);
});
'''
p.write_text(s,encoding='utf-8')
p=Path('frontend/src/components/simulation-wizard.tsx');s=p.read_text(encoding='utf-8')
s=s.replace("          values[key] = typeof expected === 'boolean' ? booleanParameterValue({}, entered)", "          const control = form.elements.namedItem(key);\n          values[key] = typeof expected === 'boolean' ? control instanceof HTMLInputElement && control.type === 'checkbox' ? control.checked : booleanParameterValue({}, entered)",1)
p.write_text(s,encoding='utf-8')
