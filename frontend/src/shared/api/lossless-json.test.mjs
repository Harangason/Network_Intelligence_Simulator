import assert from 'node:assert/strict';
import {test} from 'node:test';
import {parseLosslessJson, readLosslessJson} from './lossless-json.ts';

test('uint64 and signed protocol counters survive read, edit, provenance and reload', async () => {
  const response = new Response('{"values":{"alias":18446744073709551615,"ns":9223372036854775807},"proof":{"value":18446744073709551615},"small":255,"decimal":0.1}');
  const parsed = await readLosslessJson(response);
  assert.equal(parsed.values.alias, '18446744073709551615');
  assert.equal(parsed.values.ns, '9223372036854775807');
  assert.equal(parsed.proof.value, parsed.values.alias);
  assert.equal(parsed.small, 255);
  assert.equal(parsed.decimal, 0.1);
  assert.deepEqual(parseLosslessJson(JSON.stringify(parsed)), parsed);
});

test('JSON syntax and escaped text remain intact at exact-integer boundaries', () => {
  const data = parseLosslessJson('{"a":9007199254740991,"b":9007199254740992,"c":-9007199254740992,"text":"x \\" 18446744073709551615","empty":null}');
  assert.equal(data.a, Number.MAX_SAFE_INTEGER);
  assert.equal(data.b, '9007199254740992');
  assert.equal(data.c, '-9007199254740992');
  assert.equal(data.text, 'x " 18446744073709551615');
  for (const malformed of ['{"x":01}', '{"x":1e}', '[1,]', '{"x":"unterminated}']) {
    assert.throws(() => parseLosslessJson(malformed));
  }
});
