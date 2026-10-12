import hashlib,json,pathlib,subprocess,urllib.request
BASE=pathlib.Path(__file__).resolve().parent
ROOT=BASE.parents[2]
DOCKER=json.loads((ROOT/'config/networkis.resources.json').read_text(encoding='utf-8-sig'))['paths']['docker_cli']
receipt_path=pathlib.Path(__import__('sys').argv[1]); receipt=json.loads(receipt_path.read_text())
assert receipt['status']=='PASS'
r={'image_id':subprocess.check_output([DOCKER,'inspect','NetworkIS','--format','{{.Image}}'],text=True).strip(),'receipt':str(receipt_path.resolve()),'cases':[]}
assert r['image_id']==receipt['image_id']
for endpoint in ['ready','build-info']:
 with urllib.request.urlopen('http://127.0.0.1:13500/api/'+endpoint,timeout=10) as response:r[endpoint]=json.load(response)
assert r['ready']['status']=='ready'
assert r['build-info']['source_sha256']==receipt['release']['source_sha256']
for industry,model_type in [('Custom','custom'),('Robotics','robotics_ros'),('Aerospace','aerospace'),('Building','building_automation')]:
 graph=[{'network_id':'ethernet','bus_name':'Perception','controllers':[{'ecu':'Kameraverarbeitung','sensors':['Sensor1'],'actuators':[]},{'ecu':'AutonomeNavigation','sensors':[],'actuators':[]}],'functional_routes':[{'source':'Kameraverarbeitung','target':'AutonomeNavigation','signals':['KameraverarbeitungObjektdaten'],'excluded_signals':[]}]}]
 prompt='\n'.join(['- Industrie: '+industry,'- Projekt-Modelltyp: '+model_type,'- Netzwerktechnologien: Ethernet (ethernet)','- Hardware-Sollwerte: {"gateways":0,"ecus":2,"sensors":1,"actuators":0}','- Geräteanschlüsse: {"Kameraverarbeitung":"Ethernet","AutonomeNavigation":"Ethernet","Sensor1":"Ethernet"}','- Sensor-Messgrößen: {"Sensor1":"image_frame"}','- Funktionaler Generierungsvertrag: sensor-actuator-v1','- Systemcluster-Graph: '+json.dumps(graph),'Konkrete Aufgabe des Nutzers, per Wizard-Uebernehmen bestaetigt:','Kameraverarbeitung mit Bilddaten und autonomer Navigation.'])
 result=subprocess.run([DOCKER,'exec','-i','NetworkIS','node','--experimental-strip-types','/app/frontend/scripts/extract-wizard-specification.mjs'],input=json.dumps({'prompt':prompt}),text=True,encoding='utf-8',capture_output=True,check=True)
 spec=json.loads(result.stdout);chains=spec['chains']
 sensor=next(c for c in chains if c['hardware_name']=='Sensor1' and (c.get('semantic') or {}).get('semantic_type')=='BYTE_ARRAY')
 output=next(c for c in chains if c['signal_name']=='KameraverarbeitungObjektdaten')
 assert sensor['length_bits']==1400*8
 assert output['length_bits']==1168*8 and output['dlc']==1168
 assert output['configuration']['structured_payload']['max_objects']==48
 assert output['configuration']['communication_contract']['scope']=='FUNCTION_OUTPUT'
 assert output['configuration']['functional_device_contract']['input_names']==['Sensor1']
 assert not any(c['message_name']==output['message_name'] and c['signal_name']!=output['signal_name'] for c in chains)
 r['cases'].append({'industry':industry,'model_type':spec['modelType'],'raw_sensor_bits':sensor['length_bits'],'object_payload_bytes':output['dlc'],'schema_version':output['configuration']['structured_payload']['version'],'separate_function_output':True})
r['status']='PASSED';r['mutation']='NONE; pure generator and GET health only'
(BASE/'production-functional.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
print(json.dumps({'status':r['status'],'image_id':r['image_id'],'case_count':len(r['cases'])}))
