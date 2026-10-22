const token=document.querySelector('meta[name="app-token"]').content;
const $=id=>document.getElementById(id);
let state, messageTimer, pendingOrder;
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{'Content-Type':'application/json','X-App-Token':token},body:body?JSON.stringify(body):undefined});const v=await r.json();if(!r.ok)throw Error(v.error||'요청 실패');return v;}
function message(text){$('message').textContent=text;$('message').style.display='block';clearTimeout(messageTimer);messageTimer=setTimeout(()=>$('message').style.display='none',6000);}
const states={active:'거래 가능',reserved:'예약됨',canceled:'취소됨',expired:'만료됨'};
const phases={STARTING:'시험 노드 시작',AGREED:'조건 확정',SMW_LOCK_CONFIRMED:'수무우 자금 잠금 확인',BOTH_LOCKS_CONFIRMED:'양쪽 잠금 확인',BTC_CLAIM_CONFIRMED:'BTC 수령 확인',COMPLETED:'양쪽 교환 완료',REFUND_WAIT:'환불 기한 확인',REFUNDED:'양쪽 환불 완료'};
async function refresh(){try{state=await api('state');$('my-port').textContent=state.relay_port;$('identity').textContent=state.identity;$('peer-count').textContent=state.peers.length;$('order-count').textContent=state.orders.filter(x=>x.status==='active').length;$('orders').replaceChildren();$('empty').hidden=state.orders.length>0;
for(const o of state.orders){const tr=document.createElement('tr');for(const [i,text] of [o.side==='sell'?'판매':'구매',o.smw,o.btc,states[o.status]].entries()){const td=document.createElement('td');td.textContent=text;if(i===0)td.className=o.side;tr.append(td);}const td=document.createElement('td');if(o.status==='active'){const b=document.createElement('button');b.textContent=o.mine?'취소':'거래 예약';b.addEventListener('click',async()=>{if(!o.mine){pendingOrder=o;$('confirm-text').textContent=`${o.smw} SMW ↔ ${o.btc} BTC`;$('confirm').showModal();return;}try{await api('cancel',{id:o.id});await refresh();message('주문을 취소했습니다.');}catch(e){message(e.message);}});td.append(b);}tr.append(td);$('orders').append(tr);}
$('peers').replaceChildren();for(const p of state.peers){const li=document.createElement('li');li.textContent=`127.0.0.1:${p.port}`;$('peers').append(li);}
const j=state.job;for(const id of ['success-check','refund-check'])$(id).disabled=j.running;
$('evidence-panel').hidden=!j.result;if(j.result)$('evidence').textContent=JSON.stringify(j.result,null,2);
$('job').textContent=j.running?`진행 중 · ${phases[j.state]||j.state}`:j.passed===true?`검사 통과 · ${j.mode==='success'?'양쪽 교환 완료':'기한 전 환불 거부 및 재시작 후 양쪽 환불 완료'} · ${j.result.elapsed_seconds}초 (가속 시험망)` :j.passed===false?`검사 실패 · ${j.error}`:'아직 실행하지 않았습니다.';
}catch(e){$('job').textContent='프로그램과 연결이 끊겼습니다. '+e.message;}}
$('order-form').addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.target);try{await api('order',Object.fromEntries(f));await refresh();message('서명된 시험 주문을 등록했습니다.');}catch(e){message(e.message);}});
$('peer-form').addEventListener('submit',async e=>{e.preventDefault();try{await api('connect',{port:Number(new FormData(e.target).get('port'))});await refresh();message('시험 노드에 연결하고 주문을 받았습니다.');}catch(e){message(e.message);}});
$('sync').addEventListener('click',async()=>{try{const r=await api('sync',{});await refresh();message(r.peers.some(p=>!p.ok)?'일부 노드에 연결하지 못했습니다.':'주문 동기화를 마쳤습니다.');}catch(e){message(e.message);}});
for(const [id,mode] of [['success-check','success'],['refund-check','refund']])$(id).addEventListener('click',async()=>{try{await api('check',{mode});await refresh();}catch(e){message(e.message);}});
$('confirm-cancel').addEventListener('click',()=>$('confirm').close());
$('confirm-accept').addEventListener('click',async()=>{try{await api('reserve',{id:pendingOrder.id});$('confirm').close();await refresh();message('주문을 예약했습니다. 자산은 전송되지 않았습니다.');}catch(e){message(e.message);}});
refresh();setInterval(refresh,2000);
