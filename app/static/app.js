const certificateState={busy:false};
const message=document.querySelector('#feedback');
async function certificateRequest(path,payload){certificateState.busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);message.hidden=false;message.textContent='正在核验…';try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.detail||'核验失败，请重试');location.href=location.pathname+'?run='+(data.manifest?.run_id||document.querySelector('#run-meta').dataset.run);}catch(error){message.textContent=error.message;document.querySelectorAll('button').forEach(b=>b.disabled=false);}finally{certificateState.busy=false;}}
function readCertificateInput(){const form=document.querySelector('#intake-form');if(!form)return{sample:'dirty'};const values=new FormData(form);return values.get('csv').trim()?{csv:values.get('csv')}:{sample:values.get('sample')};}
document.querySelector('#intake-form')?.addEventListener('submit',e=>{e.preventDefault();certificateRequest('/api/batches',readCertificateInput());});
document.querySelector('#rerun').addEventListener('click',()=>certificateRequest('/api/batches',readCertificateInput()));
document.querySelector('#print').addEventListener('click',()=>window.print());
document.querySelector('#review')?.addEventListener('click',()=>{const meta=document.querySelector('#run-meta').dataset;certificateRequest('/api/review/'+meta.run,{revision:Number(meta.revision)});});
