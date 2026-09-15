// HTTP adapter for the Littleboard API.
export const statuses = ['Backlog','To Do','In Progress','Done'];
export const priorities = ['Low','Medium','High'];
export const assignees = ['Alex Morgan','Jamie Chen','Sam Rivera','Taylor Brooks'];

export function createApi({baseUrl='/api', fetchImpl=globalThis.fetch}={}) {
  async function request(path, method='GET', body) {
    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        method,
        headers: body === undefined ? {Accept:'application/json'} : {Accept:'application/json','Content-Type':'application/json'},
        ...(body === undefined ? {} : {body:JSON.stringify(body)})
      });
    } catch {
      throw Error('Unable to reach the backend. Check that both servers are running.');
    }
    const data = await response.json().catch(()=>null);
    if (!response.ok) {
      const detail = data?.detail;
      const message = typeof detail === 'string' ? detail : Array.isArray(detail)
        ? detail.map(error=>`${(error.loc||[]).slice(1).join('.') || 'Request'}: ${error.msg}`).join('; ')
        : `Request failed (${response.status}). Please try again.`;
      throw Error(message);
    }
    if (data === null) throw Error('The backend returned an invalid response.');
    return data;
  }
  const taskPath = id => `/tasks/${encodeURIComponent(id)}`;
  return {
    list({archived=false,search='',assignee='',priority=''}={}) {
      return request(`/tasks?${new URLSearchParams({archived,search,assignee,priority})}`);
    },
    create: fields => request('/tasks','POST',fields),
    update: (id,fields) => request(taskPath(id),'PATCH',fields),
    remove: id => request(taskPath(id),'DELETE'),
    move: (id,status,beforeId=null) => request(`${taskPath(id)}/move`,'POST',{status,beforeId}),
    archive: (id,archived=true) => request(`${taskPath(id)}/archive`,'PATCH',{archived}),
    saveComment: (id,{id:commentId,name,text}) => request(`${taskPath(id)}/comments${commentId ? `/${encodeURIComponent(commentId)}` : ''}`,commentId?'PUT':'POST',{name,text}),
    deleteComment: (id,commentId) => request(`${taskPath(id)}/comments/${encodeURIComponent(commentId)}`,'DELETE')
  };
}
export const api = createApi();
