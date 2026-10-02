from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
root=Path.cwd();sys.path.insert(0,str(root))
from backend.communication.technologies import DEFAULT_TECHNOLOGY_REGISTRY as registry
from backend.communication.technologies import pcie as n
folder=root/'docs/implementation-workloads/technology-full-parameter-audit-20261001';xml=folder/'individual/pcie-tests.xml'
for path in ('backend/communication/technologies/pcie.py','backend/tests/test_pcie_parameter_review.py','backend/communication/technologies/catalog.py','backend/communication/technologies/core/components.py'):
 assert xml.stat().st_mtime_ns>=(root/path).stat().st_mtime_ns,('stale',path)
p=ET.parse(xml);s=p.findall('.//testsuite');assert s and all(int(v.get(k,'0'))==0 for v in s for k in('failures','errors','skipped'))
cases=p.findall('.//testcase');native=sum(c.get('classname','').endswith('test_pcie_parameter_review')for c in cases)
assert native>=len(registry.parameter_fields('pcie'))+10 and len({c.get('classname')for c in cases})==10
primary=root/'work/pcie-primary';manifest=json.loads((primary/'manifest.json').read_text())
for entry in manifest:
 assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['sha256']
 entry['read_scope']='Downloaded HTML. Only gen4-5.html contains the reviewed architecture paragraph; physical.html and implementation.html are redirect shells and are NOT evidence of the requested document.'
for name,scope in [('registers.h','Pinned Linux v6.12 PCIe capability/control/status masks. Source constants reviewed, not licensed full PCIe standard.'),('web-tool-sections.json','Returned primary-source web excerpts for Altera813754 v25.3 device table38, features, credit interface and timeout. Not downloaded original HTML/PDF.'),('web-tool-generations.json','Returned PCI-SIG technical article and released7.0 Q&A excerpts; not full licensed Base/CEM specification.'),('web-tool-errors-phy.json','Returned Altera683411 transaction-error table: document15.1, web timestamp2025-12-16; Intel683724 archive physical-layer search excerpt. Not full normative document.')]:
 target=primary/name;assert target.exists(),name
 manifest.append(dict(path=str(target.relative_to(root)),sha256=hashlib.sha256(target.read_bytes()).hexdigest(),read_scope=scope,content_kind='RAW_PINNED_SOURCE'if name.endswith('.h')else'WEB_TOOL_TEXT_EXCERPT'))
(primary/'reviewed-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
before={v['key']for v in next(v for v in json.loads((folder/'inventory-before.json').read_text())if v['technology']=='pcie')['form_parameters']};after={v['key']for v in registry.parameter_fields('pcie')}
meanings={v['key']:v['description']for v in n.DECLARATIONS};meanings['payload_bytes']='Whole application bytes, distinct one DWORD-aligned TLP, MPS, MRRS, path capabilities, FLIT packing and actual flow-control service. No universal CAN8/Ethernet1500 ceiling.'
spec=dict(technology='pcie',native=meanings,removed={k:n.REMOVED[k]for k in before-after},sources=list(n.SOURCES),revisions=list(n.SOURCES.values()),
 scope=['Each declared type/unit/bound/meaning/dependency/default/provenance reviewed using pinned Linuxv6.12 masks and scoped public Intel/Altera/PCI-SIG primary text. Full licensed Base/CEM/ECN and every optional capability not claimed. Source provenance distinguishes raw files, web excerpts and failed redirect-shell downloads.',
 'Independent industry-neutral negotiated lane link; no CAN arbitration or Ethernet rate/MTU. Runtime remains MODEL_MISSING, theoretical codec ceiling never application capacity.',
 'Actual Gen1..7 rates2.5..128GT/s and widths; Gen1/2 8b10b,Gen3..5 128b130b,Gen6/7 FLIT_PAM4. Lower-rate FLIT requires registered source. One-direction raw rate distinct codec/packet/replay/credit losses.',
 'MPS/MRRS independent encodings0..5, actual capability/path MPS, DWORD-aligned wire TLP versus whole application and remaining completion bytes. MEMORY request4KB boundary checked against lossless address low12bits. NON_FLIT header/prefix/ECRC/LCRC/framing distinct fixed256byte FLIT236/6/8/6; FLIT can carry split larger TLPs.',
 'Source-qualified Agilex3/5 GTS25.3 capabilities, lane/tag/MPS/VC/clock restrictions and rounded16byte data-credit units. Actual available header/data credits and active/nontraining link govern emission; no inferred credits from raw advertised limits.',
 'Actual hexadecimal BDF/address/status, Link Status bits decoded against generation/lanes/training/active. AER snapshot explicitly not full error-bit codec. Actual ordering/coherency, completion/tag/correlation/poison/timeout and application freshness distinct link acknowledgement. Conventional reset1s source qualification independent training.',
 'Shared expression checker now rejects malformed/unknown operation arity, non-scalar references, nonfinite intermediate results and excessive power allocation; typed boolean/numeric conditions. Fresh cumulative native protocol regression remains required.',
 f'{len(cases)} isolated tests PASS, {native} native and nine shared suites.'],
 validation=dict(status='PASS',tests_passed=len(cases),isolated_sql=True,selected_scope=f'{native} PCIe and nine shared suites',complete_release_gate='NOT_RUN'),
 not_certified=['Full licensed standards, optional ARI/ATS/PASID/CXL features, complete packet/state/replay/flow-control executor, channel compliance, hardware E2E and physical capacity. Actual capabilities and transaction evidence are not synthesized.','Remaining profiles, cumulative consumers, README, release gate and exact tested-image production delivery remain pending.'])
(root/'work/pcie-review-decisions.json').write_text(json.dumps(spec,indent=2)+'\n');print(dict(tests=len(cases),native=native,fields=len(meanings),removed=len(before-after)))
