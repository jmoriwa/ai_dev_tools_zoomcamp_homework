import {api,statuses,priorities,assignees} from './api.js';
const $ = selector => document.querySelector(selector);
const escape = value => String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const options = (values,first) => (first!==undefined?`<option value="">${first}</option>`:'')+values.map(v=>`<option>${escape(v)}</option>`).join('');
const initials = name => name?name.split(' ').map(n=>n[0]).join(''):'–';
const avatar = name => `<span class="avatar a${assignees.indexOf(name)}">${initials(name)}</span>`;
const form = $('#task-form'), commentForm = $('#comment-form'), dialog = $('#task-dialog');
let archived=false, tasks=[], current=null, commentId=null, dragged=null, renderVersion=0, toastTimer;
$('#assignee-filter').innerHTML=options(assignees,'All assignees');
$('#priority-filter').innerHTML=options(priorities,'All priorities');
form.elements.status.innerHTML=options(statuses);form.elements.priority.innerHTML=options(priorities);form.elements.assignee.innerHTML=options(assignees,'Unassigned');commentForm.elements.name.innerHTML=options(assignees);
function notify(message) {$('#toast').textContent=message;$('#toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').hidden=true,3500);}
async function attempt(action) {try {$('#dialog-error').textContent='';await action();}catch(error){if(dialog.open)$('#dialog-error').textContent=error.message;else notify(error.message);}}
function card(t) {
  const overdue=t.dueDate&&t.status!=='Done'&&new Date(`${t.dueDate}T00:00:00`)<new Date(new Date().setHours(0,0,0,0));
  const due=t.dueDate?new Date(`${t.dueDate}T00:00:00`).toLocaleDateString(undefined,{month:'short',day:'numeric'}):'';
  return `<article class="card ${overdue?'overdue':''}" data-id="${t.id}" draggable="${!archived}"><div class="card-top"><span class="priority ${t.priority.toLowerCase()}"><span aria-hidden="true">${t.priority==='High'?'↑':t.priority==='Medium'?'＝':'↓'}</span> ${t.priority}</span><span class="grip" aria-hidden="true">⠿</span></div><button class="card-title" data-open="${t.id}">${escape(t.title)}</button><p class="card-description">${escape(t.description)}</p>${due?`<div class="due ${overdue?'late':''}">◷ ${overdue?'Overdue · ':''}${due}</div>`:''}<div class="card-bottom"><span class="person">${avatar(t.assignee)}<span>${escape(t.assignee||'Unassigned')}</span></span><span class="comments-badge" aria-label="${t.comments.length} comments">☷ ${t.comments.length}</span></div></article>`;
}
async function render() {
  const version=++renderVersion;
  const [visible,all,archive]=await Promise.all([api.list({archived,search:$('#search').value,assignee:$('#assignee-filter').value,priority:$('#priority-filter').value}),api.list(),api.list({archived:true})]);
  if(version!==renderVersion)return;tasks=visible;
  $('#archive-count').textContent=archive.length;$('#task-count').textContent=`${archived?archive.length:all.length} tasks`;
  $('#result-count').textContent=`Showing ${visible.length} ${visible.length===1?'task':'tasks'}`;
  const filtered=!!($('#search').value||$('#assignee-filter').value||$('#priority-filter').value);$('#clear-filters').hidden=!filtered;
  $('#board').classList.toggle('archive-board',archived);
  $('#board').innerHTML=archived?(visible.length?visible.map(card).join(''):'<div class="empty archive-empty"><h3>All clear here</h3><p>Archived tasks will appear here. Try clearing your filters.</p></div>'):statuses.map((status,i)=>{const items=visible.filter(t=>t.status===status),total=all.filter(t=>t.status===status).length;return `<section class="column c${i}" data-status="${status}" aria-label="${status}"><div class="column-heading"><span class="status-dot"></span><h2>${status}</h2><span class="column-count">${filtered?`${items.length} / ${total}`:total}</span><button class="icon-button" data-add="${status}" aria-label="Add task to ${status}">＋</button></div><div class="card-list">${items.map(card).join('')}${!items.length?'<div class="empty">'+(filtered?'No matching tasks':'A little room for what’s next')+'</div>':''}</div><button class="add-card" data-add="${status}">＋ Add task</button></section>`;}).join('');
}
function openTask(task=null,status='To Do') {
  current=task;form.reset();commentForm.reset();resetComment();$('#dialog-error').textContent='';
  $('#dialog-title').textContent=task?'Task details':'New task';
  for(const key of ['title','description','priority','assignee','dueDate','status'])form.elements[key].value=task?.[key]??({status,priority:'Medium'}[key]||'');
  form.elements.status.disabled=!!task?.archived;
  $('#delete-task').hidden=!task;$('#archive-task').hidden=!task||task.status!=='Done';$('#archive-task').textContent=task?.archived?'Restore to board':'Archive task';
  $('#comments-section').hidden=!task;renderComments();if(!dialog.open)dialog.showModal();form.elements.title.focus();
}
function renderComments() {
  $('#comment-count').textContent=current?.comments.length||0;
  $('#comments').innerHTML=current?.comments.length?current.comments.map(c=>`<div class="comment"><div class="comment-head">${avatar(c.name)}<strong>${escape(c.name)}</strong><button class="text-button" data-edit-comment="${c.id}" aria-label="Edit comment by ${escape(c.name)}">Edit</button><button class="text-button danger" data-delete-comment="${c.id}" aria-label="Delete comment by ${escape(c.name)}">Delete</button></div><p>${escape(c.text)}</p></div>`).join(''):'<p class="muted">No comments yet. Start the conversation.</p>';
}
function resetComment(){commentId=null;commentForm.elements.text.value='';$('#submit-comment').textContent='Add comment';$('#cancel-comment').hidden=true;}
function switchView(value){archived=value;$('#board-nav').classList.toggle('active',!value);$('#archive-nav').classList.toggle('active',value);$('#page-title').textContent=$('#breadcrumb').textContent=value?'Archive':'Project board';$('#subtitle').textContent=value?'Good work, tucked away. Your completed tasks live here.':'A clear view of what’s next, what’s moving, and what’s done.';$('.drag-hint').hidden=value;attempt(render);}
$('#board-nav').onclick=()=>switchView(false);$('#archive-nav').onclick=()=>switchView(true);$('#new-task').onclick=()=>openTask();$('#close-dialog').onclick=()=>dialog.close();
for(const selector of ['#search','#assignee-filter','#priority-filter'])$(selector).addEventListener('input',()=>attempt(render));
$('#clear-filters').onclick=()=>{$('#search').value=$('#assignee-filter').value=$('#priority-filter').value='';attempt(render);};
$('#board').onclick=e=>{const add=e.target.closest('[data-add]'), card=e.target.closest('[data-id]');if(add)openTask(null,add.dataset.add);else if(card)openTask(tasks.find(t=>t.id===card.dataset.id));};
form.onsubmit=e=>{e.preventDefault();attempt(async()=>{const fields=Object.fromEntries(new FormData(form));if(current)await api.update(current.id,fields);else await api.create(fields);dialog.close();await render();notify(current?'Task updated':'Task created');});};
$('#delete-task').onclick=()=>$('#confirm-dialog').showModal();$('#cancel-delete').onclick=()=>$('#confirm-dialog').close();
$('#confirm-delete').onclick=()=>attempt(async()=>{await api.remove(current.id);$('#confirm-dialog').close();dialog.close();await render();notify('Task deleted');});
$('#archive-task').onclick=()=>attempt(async()=>{await api.archive(current.id,!current.archived);dialog.close();await render();notify(current.archived?'Task restored to Done':'Task archived');});
commentForm.onsubmit=e=>{e.preventDefault();attempt(async()=>{current=await api.saveComment(current.id,{...Object.fromEntries(new FormData(commentForm)),id:commentId});resetComment();renderComments();await render();});};
$('#cancel-comment').onclick=resetComment;
$('#comments').onclick=e=>{const edit=e.target.closest('[data-edit-comment]'),del=e.target.closest('[data-delete-comment]');if(edit){const c=current.comments.find(c=>c.id===edit.dataset.editComment);commentId=c.id;commentForm.elements.name.value=c.name;commentForm.elements.text.value=c.text;$('#submit-comment').textContent='Save comment';$('#cancel-comment').hidden=false;commentForm.elements.text.focus();}if(del)attempt(async()=>{current=await api.deleteComment(current.id,del.dataset.deleteComment);if(commentId===del.dataset.deleteComment)resetComment();renderComments();await render();});};
// Native desktop drag-and-drop; the status selector and position buttons below
// also provide keyboard and touch access to movement and manual ordering.
$('#board').addEventListener('dragstart',e=>{const card=e.target.closest('[data-id]');if(!card||archived)return;dragged=card.dataset.id;e.dataTransfer.setData('text/plain',dragged);e.dataTransfer.effectAllowed='move';card.classList.add('dragging');});
function clearDrop(){document.querySelectorAll('.drop-before,.drop-target,.dragging').forEach(el=>el.classList.remove('drop-before','drop-target','dragging'));}
$('#board').addEventListener('dragover',e=>{const column=e.target.closest('[data-status]');if(!column||!dragged)return;e.preventDefault();document.querySelectorAll('.drop-before,.drop-target').forEach(el=>el.classList.remove('drop-before','drop-target'));column.classList.add('drop-target');const card=e.target.closest('[data-id]');if(card&&card.dataset.id!==dragged)card.classList.add('drop-before');});
$('#board').addEventListener('drop',e=>{const column=e.target.closest('[data-status]');if(!column||!dragged)return;e.preventDefault();const id=dragged,before=e.target.closest('[data-id]')?.dataset.id||null;dragged=null;clearDrop();attempt(async()=>{await api.move(id,column.dataset.status,before);await render();notify(`Task moved to ${column.dataset.status}`);});});
$('#board').addEventListener('dragend',()=>{dragged=null;clearDrop();});
const reorder=document.createElement('div');reorder.className='reorder';reorder.innerHTML='<span>Position in column</span><button type="button" class="secondary" id="move-up">↑ Move up</button><button type="button" class="secondary" id="move-down">↓ Move down</button>';form.querySelector('.form-actions').before(reorder);
for(const [selector,direction] of [['#move-up',-1],['#move-down',1]])$(selector).onclick=()=>attempt(async()=>{if(!current||current.archived)return;const list=(await api.list()).filter(t=>t.status===current.status),i=list.findIndex(t=>t.id===current.id);if(i+direction<0||i+direction>=list.length){notify('Already at the edge of this column');return;}await api.move(current.id,current.status,direction<0?list[i-1].id:list[i+2]?.id||null);await render();notify('Task order updated');});
new MutationObserver(()=>{reorder.hidden=!current||current.archived;}).observe(dialog,{attributes:true,attributeFilter:['open']});
attempt(render);
