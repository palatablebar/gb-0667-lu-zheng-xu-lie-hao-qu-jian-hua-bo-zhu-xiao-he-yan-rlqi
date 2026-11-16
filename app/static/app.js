const certificateState={busy:false};
const message=document.querySelector('#feedback');
async function certificateRequest(path,payload){certificateState.busy=true;document.querySelectorAll('button').forEach(b=>b.disabled=true);message.hidden=false;message.textContent='正在核验…';try{const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const data=await response.json();if(!response.ok)throw Error(data.detail||'核验失败，请重试');location.href=location.pathname+'?run='+(data.manifest?.run_id||document.querySelector('#run-meta').dataset.run);}catch(error){message.textContent=error.message;document.querySelectorAll('button').forEach(b=>b.disabled=false);}finally{certificateState.busy=false;}}
function readCertificateInput(){const form=document.querySelector('#intake-form');if(!form)return{sample:'dirty'};const values=new FormData(form);return values.get('csv').trim()?{csv:values.get('csv')}:{sample:values.get('sample')};}
document.querySelector('#intake-form')?.addEventListener('submit',e=>{e.preventDefault();certificateRequest('/api/batches',readCertificateInput());});
document.querySelector('#rerun')?.addEventListener('click',()=>certificateRequest('/api/batches',readCertificateInput()));
document.querySelector('#print').addEventListener('click',()=>window.print());
document.querySelector('#review')?.addEventListener('click',()=>{const meta=document.querySelector('#run-meta').dataset;certificateRequest('/api/review/'+meta.run,{revision:Number(meta.revision)});});

// ---- M8 月末关账：补回凭据只修正受影响区间，关账前强制清零待确认 ----
async function closingRequest(path,payload){
  message.hidden=false;message.textContent='正在处理…';
  document.querySelectorAll('button').forEach(b=>b.disabled=true);
  try{
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json();
    if(!response.ok)throw Error(data.detail||'处理失败，旧版已保留');
    const target=location.pathname+'?run='+data.id;
    location.href=target;
  }catch(error){message.textContent=error.message;document.querySelectorAll('button').forEach(b=>b.disabled=false);}
}
function closingMeta(){return document.querySelector('#run-meta').dataset;}
document.querySelectorAll('.evidence-btn').forEach(btn=>{
  btn.addEventListener('click',()=>{
    const tpl=document.querySelector('#evidence-form');
    let panel=document.querySelector('#evidence-panel');
    if(panel){panel.remove();return;}
    panel=tpl.content.firstElementChild.cloneNode(true);
    panel.querySelector('#ev-key').value=btn.dataset.key;
    btn.closest('td').appendChild(panel);
    panel.querySelector('#ev-submit').addEventListener('click',()=>{
      const meta=closingMeta();
      closingRequest('/api/closing/evidence',{
        ledger_id:meta.run,
        interval_key:panel.querySelector('#ev-key').value,
        kind:panel.querySelector('#ev-kind').value,
        ref:panel.querySelector('#ev-ref').value.trim(),
        detail:panel.querySelector('#ev-detail').value.trim(),
        target_status:panel.querySelector('#ev-target').value,
        version:Number(meta.revision),
      });
    });
  });
});
document.querySelector('#close-ledger')?.addEventListener('click',()=>{
  const meta=closingMeta();
  closingRequest('/api/closing/close',{ledger_id:meta.run,version:Number(meta.revision)});
});
