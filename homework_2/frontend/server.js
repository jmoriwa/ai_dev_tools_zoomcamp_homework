// Development static server with a same-origin proxy to FastAPI.
import http from 'node:http';
import { readFile } from 'node:fs/promises';
const backend = new URL(process.env.BACKEND_URL || 'http://127.0.0.1:8000');
const files = {'/':'index.html','/index.html':'index.html','/app.js':'app.js','/api.js':'api.js','/styles.css':'styles.css'};
http.createServer(async (req,res) => {
  const pathname = new URL(req.url,'http://localhost').pathname;
  if (pathname.startsWith('/api/')) {
    const upstream = http.request(new URL(req.url,backend), {
      method:req.method, headers:{...req.headers,host:backend.host}
    }, response => {
      res.writeHead(response.statusCode,response.headers);
      response.pipe(res);
    });
    upstream.setTimeout(10000,()=>upstream.destroy(Error('Backend timeout')));
    upstream.on('error',()=>{
      if (res.headersSent) {res.destroy();return;}
      res.writeHead(502,{'Content-Type':'application/json'});
      res.end(JSON.stringify({detail:'Unable to reach the backend. Start FastAPI on port 8000 and try again.'}));
    });
    req.pipe(upstream);
    return;
  }
  const file = files[pathname];
  if (!file) {res.writeHead(404);res.end('Not found');return;}
  try {const body=await readFile(new URL(file,import.meta.url));res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':'text/html');res.end(body);}
  catch {res.writeHead(500);res.end('Unable to load file');}
}).listen(Number(process.env.PORT || 3000),'127.0.0.1',()=>console.log(`Kanban: http://localhost:${process.env.PORT || 3000}`));
