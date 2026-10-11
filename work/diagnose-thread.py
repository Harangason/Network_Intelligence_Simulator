import sys,importlib.util,json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
spec=importlib.util.spec_from_file_location('thread_tests','backend/tests/test_thread_parameter_review.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def status(x):
 r=m.registry.validate_parameters('thread',x)
 if r['status']!='VALID':print(json.dumps(r,default=str))
 return r['status']
m.status=status
for name in ('test_thread_own_profile_no127byte_application_cap_or_ethernet_clock','test_utf8_network_name_byte_limit_broadcast_pan_and_extended_pan','test_registered_edition_requires_own_source_not_public_baseline_bounds','test_parent_child_and_active_forwarding_role_are_not_interchangeable','test_radio_symbol_psdu_and_whole_airtime_not_functional_timing'):
 print(name)
 try:getattr(m,name)()
 except (AssertionError,KeyError) as e:print(type(e).__name__,str(e))
