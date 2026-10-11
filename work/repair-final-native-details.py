from pathlib import Path
p=Path('backend/communication/technologies/wireless_m_bus.py');s=p.read_text(encoding='utf-8')
s=s.replace("for mode in('S2','T2','C2','R2','N2','F2'):r('fac_n'", "for mode in('S2','T2','C2','R2','F2'):r('fac_n'",1)
s=s.replace(" r('fac_ms',", " r('data_bps',{'edition':'TI_AN121_2012_DRAFT','mode':'N2'},when_present=['wm_fac_n'],required=True,s=TI)\n for bps in(2400,4800,19200):r('fac_n',{'edition':'TI_AN121_2012_DRAFT','mode':'N2','data_bps':bps},allowed=[2,3,5]if bps==19200 else[5,7,13],s=TI)\n r('fac_ms',",1)
s=s.replace("v('coding',coding,{'mode':mode,'direction':'METER_TO_OTHER'});v('chip_rate_cps',rate,{'mode':mode,'direction':'METER_TO_OTHER'});v('centre_mhz',freq,{'mode':mode,'direction':'METER_TO_OTHER'})", "v('coding',coding,{'mode':mode,'direction':'METER_TO_OTHER'});v('chip_rate_cps',rate,{'mode':mode,'direction':'METER_TO_OTHER'})\n  if mode!='R2':v('centre_mhz',freq,{'mode':mode,'direction':'METER_TO_OTHER'})")
p.write_text(s,encoding='utf-8')
p=Path('backend/tests/test_wireless_m_bus_parameter_review.py');s=p.read_text(encoding='utf-8');s+='''

@pytest.mark.parametrize('bps,allowed,bad',[(2400,7,2),(4800,13,3),(19200,3,7)])
def test_historical_ng_frequent_access_is_not_na_to_nf(bps,allowed,bad):
 x={**actual(),'wm_edition':'TI_AN121_2012_DRAFT','wm_mode':'N2','wm_data_bps':bps,'wm_fac_n':allowed}
 assert status(x)=='VALID'
 assert status({**x,'wm_fac_n':bad})=='INVALID'
 assert status({k:v for k,v in x.items() if k!='wm_data_bps'})=='UNVERIFIED'

def test_r2_meter_frequency_is_channel_dependent_not_other_device_frequency():
 f={v['key']:v for v in registry.parameter_fields('wireless_m_bus')}
 assert not any(v['when'].get('wm_mode')=='R2' and v['when'].get('wm_direction')=='METER_TO_OTHER' for v in f['wm_centre_mhz']['conditional_defaults'])
''';p.write_text(s,encoding='utf-8')
p=Path('backend/communication/technologies/zigbee.py');s=p.read_text(encoding='utf-8').replace("r('attempts',{'stack':'EMBERZNET_8_2_1','aps_retry':True},allowed=[3])", "r('attempts',{'stack':'EMBERZNET_8_2_1','aps_retry':True},maximum=3)")
p.write_text(s,encoding='utf-8')
p=Path('backend/tests/test_zigbee_parameter_review.py');s=p.read_text(encoding='utf-8').replace("assert status({**x,'zb_attempts':2})=='INVALID'", "assert status({**x,'zb_attempts':2})=='VALID';assert status({**x,'zb_attempts':4})=='INVALID'")
p.write_text(s,encoding='utf-8')
