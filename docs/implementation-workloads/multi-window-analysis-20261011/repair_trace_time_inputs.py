"""Apply the evidenced product repair only after the running gate has ended."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
receipt = ROOT / 'backend/test-output/release-gates/delivery-a25a8a753c3a/b9804dd2b416/receipt.json'
assert json.loads(receipt.read_text())['status'] == 'FAIL'
record = json.loads((HERE / 'time-window-repair.json').read_text())
assert record['status'] == 'DIAGNOSED_NOT_APPLIED'
for item in record['before']:
    assert hashlib.sha256((ROOT / item['file']).read_bytes()).hexdigest() == item['sha256']

path = ROOT / 'frontend/src/features/traces/ui/trace-analysis-workbench.tsx'
source = path.read_text(encoding='utf-8')

def replace(old, new):
    global source
    assert source.count(old) == 1, old
    source = source.replace(old, new)

replace('  const [timeEnd, setTimeEnd] = useState(1e15);',
        '  const [timeEnd, setTimeEnd] = useState(1e15);\n  const timeRangeDraft = useRef<[number, number]>([0, 1e15]);')
replace('    setTimeStart(c.time_range[0]); setTimeEnd(c.time_range[1]); setQuery(c.filter_set.query);',
        '    timeRangeDraft.current = [...c.time_range];\n    setTimeStart(c.time_range[0]); setTimeEnd(c.time_range[1]); setQuery(c.filter_set.query);')
replace('''  useEffect(() => {
    if (workspace && traceJob && !applyingContext.current) workspace.store.update({time_range:[timeStart,timeEnd],filter_set:{query}});
  },[timeStart,timeEnd,query,traceJob]);''',
        '''  // Publish user intent directly. Received display state must never echo back,
  // and an incoming-context guard must not discard a concurrent user edit.
  function changeTimeRange(start: number, end: number) {
    timeRangeDraft.current = [start, end];
    setTimeStart(start); setTimeEnd(end);
    if (traceJob) workspace?.store.update({time_range: [start, end]});
  }
  function changeQuery(value: string) {
    setQuery(value);
    if (traceJob) workspace?.store.update({filter_set: {query: value}});
  }''')
replace('    if (range) { setTimeStart(range.start); setTimeEnd(range.end); setQuery(search.get("q") ?? ""); }',
        '    if (range) { timeRangeDraft.current = [range.start, range.end]; setTimeStart(range.start); setTimeEnd(range.end); setQuery(search.get("q") ?? ""); }')
replace('session_id:result.session_id,time_cursor:null,time_basis:null});',
        'session_id:result.session_id,time_cursor:null,time_basis:null,time_range:[0,1e15],filter_set:{query:""}});')
replace('      setTimeStart(0); setTimeEnd(1e15); setQuery("");',
        '      timeRangeDraft.current = [0, 1e15];\n      setTimeStart(0); setTimeEnd(1e15); setQuery("");')
replace('workspace?.store.update({event_id:event.id,message_id:messageId,',
        'workspace?.store.update({time_range:[...timeRangeDraft.current],filter_set:{query},event_id:event.id,message_id:messageId,')
replace('onChange={(event) => setQuery(event.target.value)} placeholder="Globale Filter:',
        'maxLength={4096} onChange={(event) => changeQuery(event.target.value)} placeholder="Globale Filter:')
replace('if (Number.isFinite(value)) setTimeStart(Math.max(0, Math.min(value, timeEnd)));',
        'if (Number.isFinite(value)) changeTimeRange(Math.max(0, Math.min(value, timeRangeDraft.current[1])), timeRangeDraft.current[1]);')
replace('if (!event.target.value) { setTimeEnd(1e15); return; }',
        'if (!event.target.value) { changeTimeRange(timeRangeDraft.current[0], 1e15); return; }')
replace('if (Number.isFinite(value)) setTimeEnd(Math.max(timeStart, value));',
        'if (Number.isFinite(value)) changeTimeRange(timeRangeDraft.current[0], Math.max(timeRangeDraft.current[0], value));')
replace('onChange={event => { setTimeStart(Math.min(Number(event.target.value), timelineEnd)); setTimeEnd(timelineEnd); }}',
        'onChange={event => changeTimeRange(Math.min(Number(event.target.value), timelineEnd), timelineEnd)}')
replace('onChange={event => { setTimeEnd(Math.max(Number(event.target.value), timelineStart)); setTimeStart(timelineStart); }}',
        'onChange={event => changeTimeRange(timelineStart, Math.max(Number(event.target.value), timelineStart))}')
path.write_text(source, encoding='utf-8')

test_path = ROOT / 'frontend/e2e/analysis-workspace.spec.ts'
test = test_path.read_text(encoding='utf-8')
anchor = "  await expect(events.getByLabel('Von (s)',{exact:true})).toHaveValue('0.4');await expect(events.getByLabel('Bis (s)',{exact:true})).toHaveValue('0.8');"
assert test.count(anchor) == 1
test = test.replace(anchor, "  await expect(page.getByLabel('Von (s)',{exact:true})).toHaveValue('0.4');await expect(page.getByLabel('Bis (s)',{exact:true})).toHaveValue('0.8');\n" + anchor)
anchor = '  expect(times.length).toBeGreaterThan(0);for(const text of times){const t=parseFloat(text);expect(t).toBeGreaterThanOrEqual(.4);expect(t).toBeLessThanOrEqual(.8);}'
assert test.count(anchor) == 1
test = test.replace(anchor, anchor + '''
  // Rapid edits in the follower publish both bounds, even before an ACK arrives.
  await events.getByLabel('Von (s)',{exact:true}).fill('0.5');await events.getByLabel('Bis (s)',{exact:true}).fill('0.7');
  await expect(page.getByLabel('Von (s)',{exact:true})).toHaveValue('0.5');await expect(page.getByLabel('Bis (s)',{exact:true})).toHaveValue('0.7');
  const globalFilter = 'Globale Filter: ID, Quelle, Ziel, Payload, Finding ...';
  await events.getByPlaceholder(globalFilter,{exact:true}).fill('Sensor');
  await expect(page.getByPlaceholder(globalFilter,{exact:true})).toHaveValue('Sensor');
  await page.getByPlaceholder(globalFilter,{exact:true}).fill('');
  await expect(events.getByPlaceholder(globalFilter,{exact:true})).toHaveValue('');''')
test_path.write_text(test, encoding='utf-8')
record.update(status='APPLIED_PENDING_VERIFICATION', release_status='Previous full gate FAIL retained; fresh full PASS and delivery required.', after={item['file']:hashlib.sha256((ROOT/item['file']).read_bytes()).hexdigest() for item in record['before']})
(HERE / 'time-window-repair.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
print('Explicit time-range and filter intents repaired; bidirectional original-data E2E assertions retained and extended.')
