import test from 'node:test';
import assert from 'node:assert/strict';
import {createApi} from './api.js';

test('all operations map to HTTP methods, encoded paths and contract bodies',async()=>{
  const calls=[];
  const api=createApi({fetchImpl:async(url,options)=>{calls.push({url,...options});return Response.json({id:'saved'});}});
  await api.list({archived:true,search:'a & b',assignee:'Sam Rivera',priority:'High'});
  const query=new URL(calls[0].url,'http://localhost').searchParams;
  assert.equal(query.get('search'),'a & b');assert.equal(query.get('archived'),'true');assert.equal(query.get('assignee'),'Sam Rivera');assert.equal(query.get('priority'),'High');
  await api.create({title:'New'});await api.update('a/b',{title:'Edit'});await api.remove('a/b');
  await api.move('a/b','Done');await api.archive('a/b');await api.archive('a/b',false);
  await api.saveComment('a/b',{id:null,name:'Sam Rivera',text:'Hello'});
  await api.saveComment('a/b',{id:'c/d',name:'Sam Rivera',text:'Edited'});
  await api.deleteComment('a/b','c/d');
  assert.deepEqual(calls.slice(1).map(c=>[c.method,c.url,c.body && JSON.parse(c.body)]),[
    ['POST','/api/tasks',{title:'New'}],['PATCH','/api/tasks/a%2Fb',{title:'Edit'}],['DELETE','/api/tasks/a%2Fb',undefined],
    ['POST','/api/tasks/a%2Fb/move',{status:'Done',beforeId:null}],['PATCH','/api/tasks/a%2Fb/archive',{archived:true}],['PATCH','/api/tasks/a%2Fb/archive',{archived:false}],
    ['POST','/api/tasks/a%2Fb/comments',{name:'Sam Rivera',text:'Hello'}],['PUT','/api/tasks/a%2Fb/comments/c%2Fd',{name:'Sam Rivera',text:'Edited'}],['DELETE','/api/tasks/a%2Fb/comments/c%2Fd',undefined]
  ]);
});
test('returns backend data including deletion result',async()=>{
  const api=createApi({fetchImpl:async()=>Response.json(true)});assert.equal(await api.remove('task'),true);
});
test('surfaces domain, validation, network and invalid response errors',async()=>{
  for(const [response,pattern] of [
    [Response.json({detail:'Task not found'},{status:404}),/Task not found/],
    [Response.json({detail:[{loc:['body','title'],msg:'Field required'}]},{status:422}),/title: Field required/],
    [new Response('Bad gateway',{status:502}),/502/],
    [new Response('invalid'),/invalid response/]
  ]) await assert.rejects(createApi({fetchImpl:async()=>response}).list(),pattern);
  await assert.rejects(createApi({fetchImpl:async()=>{throw Error('fetch failed');}}).list(),/Unable to reach the backend/);
});
