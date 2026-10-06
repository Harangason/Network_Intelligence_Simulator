import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readConversation} from './conversation-client.ts';

test('cards share one in-flight request but keep projects separate', async () => {
  const original=globalThis.fetch;const calls=[];
  globalThis.fetch=async(_url,options)=>{calls.push(options.headers['X-Project-ID']);return Response.json({success:true,data:{questions:{},decisions:{},selected_context:{active_view:'/studio',selected_object_refs:[]}}});};
  try{
    const [a,b]=await Promise.all([readConversation('project-a'),readConversation('project-a')]);
    assert.deepEqual(a,b);assert.deepEqual(calls,['project-a']);
    await readConversation('project-b');assert.deepEqual(calls,['project-a','project-b']);
    const controller=new AbortController();controller.abort();
    await assert.rejects(readConversation('project-a',controller.signal),{name:'AbortError'});
    assert.equal((await readConversation('project-a')).success,true);
  }finally{globalThis.fetch=original;}
});

test('receipt recovery bypasses a cached pre-commit conversation', async () => {
  const original = globalThis.fetch;
  let accepted = false;
  globalThis.fetch = async () => Response.json({ success: true, data: {
    questions: {}, wizard_operations: accepted ? { operation: { accepted: true } } : {},
  } });
  try {
    assert.deepEqual((await readConversation('receipt-project')).data.wizard_operations, {});
    accepted = true;
    assert.deepEqual((await readConversation('receipt-project')).data.wizard_operations, {});
    assert.equal((await readConversation('receipt-project', undefined, undefined, { fresh: true })).data.wizard_operations.operation.accepted, true);
  } finally { globalThis.fetch = original; }
});
