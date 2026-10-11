import sys, importlib.util, json
from pathlib import Path
sys.path.insert(0,str(Path.cwd()))
spec=importlib.util.spec_from_file_location('tcp_tests',Path('backend/tests/test_tcp_parameter_review.py'))
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
def status(x):
 r=m.registry.validate_parameters('tcp',x)
 if r['status']!='VALID': print(json.dumps(r,default=str))
 return r['status']
m.status=status
for name in ('test_effective_mss_accounts_both_tcp_ip_options_and_peer_path_limit','test_ws_both_offers_syn_unscaled_and_received_oversize_clamped','test_first_rtt_rto_and_source_recommended_floor_not_lan_clock_guess','test_rttvar_uses_old_srtt_before_update','test_rto_backoff_honors_actual_optional_cap_without_inventing60seconds','test_rwnd_is_not_cwnd_and_flight_size_not_window','test_optional_iw10_experiment_is_separately_selected','test_reno_timeout_threshold_uses_actual_flight_and_one_loss_segment','test_cubic_own_window_units_and_cubic_shape_not_reno_increase_limit'):
 print(name)
 try: getattr(m,name)()
 except AssertionError: pass
