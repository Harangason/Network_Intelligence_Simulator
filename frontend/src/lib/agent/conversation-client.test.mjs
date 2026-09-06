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
