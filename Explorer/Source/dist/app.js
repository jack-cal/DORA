'use strict';
const strings={ko:{blocks:'블록',mempool:'미확정 거래',title:'수무우의 기록을 한눈에.',subtitle:'블록부터 거래까지, 체인의 기록을 직접 확인하세요.',search:'검색 ↗',local:'로컬 노드의 저장 데이터',refresh:'새로고침',loading:'체인 데이터를 읽고 있습니다…',footer:'이 노드에 저장된 활성 체인을 조회합니다. 전역 연결 상태나 거래의 영구 확정을 보장하지 않습니다.',readonly:'조회 전용',placeholder:'블록 높이, 블록 해시, 거래 ID 또는 sumuww1 주소',height:'블록 높이',indexed:'이 노드의 활성 체인',transactions:'거래',alltx:'채굴 보상 거래 포함',waiting:'로컬 노드의 미확정 거래',interval:'최근 평균 블록 간격',intervalnote:'최근 최대 24개 간격 · 목표 600초',seconds:'초',latest:'최근 블록',latestnote:'검증 후 이 노드에 저장된 블록 기록',active:'활성 체인',hash:'블록 해시',time:'생성 시각',count:'거래 수',reward:'보상 청구액',older:'이전 블록',newest:'최신으로',snapshot:'로컬 데이터 기준',difficulty:'난이도 조정',activation:'DGW 전환 높이',target:'목표 블록 간격',utxos:'미사용 출력',empty:'현재 로컬 미확정 거래가 없습니다.',emptytx:'아직 거래 내역이 없습니다.',total:'출력 합계',txid:'거래 ID',block:'블록',confirmations:'확인 수',parent:'이전 블록',next:'다음 블록',size:'크기',weight:'무게',nonce:'논스',bits:'난이도 비트',merkle:'머클 루트',copy:'복사',copied:'복사됨',details:'상세 정보',coinbase:'채굴 보상',ordinary:'일반 거래',inputs:'입력',outputs:'출력',mint:'블록 보상으로 생성',fee:'거래 수수료',pending:'미확정',confirmed:'확인된 잔액',immature:'미성숙 채굴 보상',available:'사용 가능 잔액',history:'주소 거래 내역',address:'주소',utxolist:'미사용 출력',mature:'성숙',immaturestatus:'미성숙',spent:'사용됨',unspent:'미사용',unspendable:'사용 불가',unknown:'미지원 출력 스크립트',more:'다음 페이지',previous:'이전 페이지',notnetwork:'탐색기의 갱신 시각이며 네트워크 동기화 상태를 뜻하지 않습니다.',pendingreceived:'미확정 수신 출력',error:'데이터를 불러오지 못했습니다.',invalid:'블록 높이, 해시, 거래 ID 또는 올바른 SUMUWW 주소를 입력하세요.',notfound:'이 노드의 활성 체인 또는 미확정 거래에서 찾을 수 없습니다.',pendingreserved:'미확정 거래에 사용 예정',last:'마지막 블록',version:'버전',timeout:'응답 시간이 초과됐습니다. 다시 시도하세요.',unavailable:'데이터를 읽을 수 없습니다. 다시 시도하세요.'},en:{blocks:'Blocks',mempool:'Mempool',title:'Explore every connection.',subtitle:'Follow the blocks, transactions and addresses on SUMUWW.',search:'Search ↗',local:'Stored data from a local node',refresh:'Refresh',loading:'Reading chain data…',footer:'Shows the active chain stored by this node. It does not establish global connectivity or irreversible transaction finality.',readonly:'READ ONLY',placeholder:'Block height, block hash, transaction ID or sumuww1 address',height:'Block height',indexed:'Active chain on this node',transactions:'Transactions',alltx:'Includes coinbase transactions',waiting:'Pending on this local node',interval:'Average block interval',intervalnote:'Up to 24 recent intervals · target 600s',seconds:'s',latest:'Latest blocks',latestnote:'Blocks validated and stored by this node',active:'ACTIVE CHAIN',hash:'Block hash',time:'Block timestamp',count:'Transactions',reward:'Claimed reward',older:'Older blocks',newest:'Latest',snapshot:'Local data snapshot',difficulty:'Difficulty adjustment',activation:'DGW activation height',target:'Target block interval',utxos:'Unspent outputs',empty:'No transactions in the local mempool.',emptytx:'No transaction history yet.',total:'Output total',txid:'Transaction ID',block:'Block',confirmations:'Confirmations',parent:'Previous block',next:'Next block',size:'Size',weight:'Weight',nonce:'Nonce',bits:'Difficulty bits',merkle:'Merkle root',copy:'Copy',copied:'Copied',details:'Details',coinbase:'Coinbase',ordinary:'Transfer',inputs:'Inputs',outputs:'Outputs',mint:'Created as a block reward',fee:'Transaction fee',pending:'Pending',confirmed:'Confirmed balance',immature:'Immature mining rewards',available:'Available balance',history:'Address transactions',address:'Address',utxolist:'Unspent outputs',mature:'Mature',immaturestatus:'Immature',spent:'Spent',unspent:'Unspent',unspendable:'Unspendable',unknown:'Unsupported output script',more:'Next page',previous:'Previous page',notnetwork:'Explorer refresh time; this does not indicate network synchronization.',pendingreceived:'Pending received outputs',error:'Unable to load data.',invalid:'Enter a block height, hash, transaction ID or valid SUMUWW address.',notfound:'Not found in this node’s active chain or local mempool.',pendingreserved:'Reserved by pending transaction',last:'Last block',version:'Version',timeout:'The request timed out. Please retry.',unavailable:'Data is unavailable. Please retry.'}};
Object.assign(strings.ko,{statistics:'통계',received:'받은 출력',spentinputs:'사용한 입력',netchange:'잔액 변화',addressnote:'받은 출력에는 거스름돈이 포함될 수 있습니다. 잔액 변화는 받은 출력에서 사용한 입력을 뺀 값입니다.',csv:'CSV 내보내기',csv1000:'최근 최대 1,000건 CSV',rawblock:'원본 블록 다운로드',rawtx:'원본 거래 다운로드',proof:'포함 증명',proofdownload:'포함 증명 JSON',proofscope:'거래 ID가 이 블록 헤더의 머클 루트에 포함되는지 확인합니다. 체인의 영구 확정이나 합의 검증을 뜻하지 않습니다.',proofvalid:'헤더에 대한 포함 확인',proofposition:'거래 위치 (0부터)',proofcount:'블록 내 거래 수',proofpath:'머클 경로',lastblock:'마지막 블록 시각',readtime:'데이터 조회 시각',blockage:'마지막 블록 경과',syncunknown:'네트워크 최신 높이와의 일치 여부는 확인되지 않았습니다.',minutes:'분',hours:'시간',days:'일',sampleblocks:'표본 블록',difficultychart:'초기 난이도 대비',intervalchart:'블록 타임스탬프 간격',transactionchart:'블록별 거래 수',chartnote:'초기 목표값 대비 난이도와 블록 기록을 표시합니다. 시간 간격은 타임스탬프 기준이며 음수일 수 있습니다.',ordinarycount:'일반 거래 수',rewardtotal:'표본의 보상 청구 합계',nodata:'표시할 데이터가 없습니다.'});
Object.assign(strings.en,{statistics:'Statistics',received:'Received outputs',spentinputs:'Spent inputs',netchange:'Net change',addressnote:'Received outputs may include change. Net change is received outputs minus spent inputs.',csv:'Export CSV',csv1000:'CSV: up to 1,000 recent records',rawblock:'Download raw block',rawtx:'Download raw transaction',proof:'Inclusion proof',proofdownload:'Proof JSON',proofscope:'Checks TXID inclusion in this block header’s Merkle root. This does not establish chain finality or consensus validity.',proofvalid:'Inclusion verified against header',proofposition:'Transaction index (zero-based)',proofcount:'Transactions in block',proofpath:'Merkle path',lastblock:'Last block timestamp',readtime:'Data read at',blockage:'Time since last block',syncunknown:'Agreement with the latest network height has not been observed.',minutes:'min',hours:'h',days:'d',sampleblocks:'Sample blocks',difficultychart:'Difficulty relative to initial target',intervalchart:'Block timestamp intervals',transactionchart:'Transactions per block',chartnote:'Shows difficulty relative to the initial target and stored block records. Timestamp differences can be negative.',ordinarycount:'Ordinary transactions',rewardtotal:'Claimed rewards in sample',nodata:'No data to display.'});

Object.assign(strings.ko,{all:'전체',transactionhistory:'거래 내역',coinbaselist:'채굴 보상 거래',ordinarylist:'일반 거래',browseordinary:'일반 거래 전체 보기',type:'종류'});
Object.assign(strings.en,{coinbase:'Mining reward',ordinary:'Ordinary transaction',all:'All',transactionhistory:'Transaction history',coinbaselist:'Mining reward transactions',ordinarylist:'Ordinary transactions',browseordinary:'View all ordinary transactions',type:'Type'});
if(typeof explorerLanguages!=='undefined')Object.assign(strings,explorerLanguages.strings);
const languageChoices=typeof explorerLanguages!=='undefined'?explorerLanguages.languages:[['ko','한국어'],['en','English']];
const locale=()=>lang==='zh'?'zh-CN':lang==='mn-Mong'?'mn-Mong-CN':lang==='no'?'nb-NO':lang;
let lang='en';
try { const saved=localStorage.getItem('sumuww-explorer-language');lang=languageChoices.some(([code])=>code===saved)?saved:'en'; } catch {}
let sequence=0, searchSequence=0, routeVersion=0, rendering=false, renderController=null, searchNotice='';
const $=id=>document.getElementById(id),t=key=>strings[lang][key]||key;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const n=v=>Number(v).toLocaleString(locale());
const money=v=>{let [a,b='']=String(v??'0').split('.');return a.replace(/\B(?=(\d{3})+(?!\d))/g,',')+(b.replace(/0+$/,'')?'.'+b.replace(/0+$/,''):'');};
const when=v=>new Date(v*1000).toLocaleString(locale(),{month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false});
const link=(type,key,label,cls='')=>`<a class="${cls}" href="#/${type}/${encodeURIComponent(key)}" title="${esc(key)}">${esc(label??key)}</a>`;
const short=v=>v?v.slice(0,13)+'…'+v.slice(-8):'—';
const metric=(key,value)=>`<div class="metric"><span>${esc(t(key))}</span><span>${value}</span></div>`;
const button=(url,label)=>`<a class="quiet-button" href="${esc(url)}">${esc(label)}</a>`;
const panel=(title,body,note='',badge='',actions='')=>`<section class="panel"><div class="panel-head"><div><h2>${esc(title)}</h2>${note?`<p>${esc(note)}</p>`:''}</div><div class="panel-actions">${badge?`<span class="pill">${esc(badge)}</span>`:''}${actions}</div></div>${body}</section>`;
const empty=key=>`<div class="empty"><span class="empty-icon">◇</span>${esc(t(key))}</div>`;
function translate(){document.documentElement.lang=lang;document.documentElement.dir=['ar','ur'].includes(lang)?'rtl':'ltr';document.querySelectorAll('[data-i18n]').forEach(e=>e.textContent=t(e.dataset.i18n));$('query').placeholder=t('placeholder');$('query').setAttribute('aria-label',t('placeholder'));$('language').value=lang;}
async function api(path,{signal}={}) {
  const controller=new AbortController();
  const cancel=()=>controller.abort();
  if(signal?.aborted)cancel();else signal?.addEventListener('abort',cancel,{once:true});
  const timer=setTimeout(cancel,15000);
  try {
    const response=await fetch('/api/'+path,{cache:'no-store',signal:controller.signal});
    let data;
    try { data=await response.json(); } catch { throw new Error(t('unavailable')); }
    if(!response.ok){const error=new Error(data.error||t('error'));error.status=response.status;error.code=data.code;throw error;}
    return data;
  } catch(error) {
    if(controller.signal.aborted&&!signal?.aborted)throw new Error(t('timeout'));
    throw error;
  } finally {
    clearTimeout(timer);signal?.removeEventListener('abort',cancel);
  }
}
function stats(data){$('stats').innerHTML=[['height',n(data.height),'indexed','▧'],['transactions',link('transactions','',n(data.transactions)).replace('#/transactions/','#/transactions?kind=all'),'alltx','⇄'],['mempool',n(data.mempool_count),'waiting','◷'],['interval',data.interval===null?'—':n(Math.round(data.interval))+'<small>'+esc(t('seconds'))+'</small>','intervalnote','◴']].map(([label,value,note,icon])=>`<div class="stat"><div class="stat-label"><span class="stat-icon">${icon}</span>${esc(t(label))}</div><div class="stat-value number">${value}</div><div class="stat-note">${label==='transactions'?`${link('transactions','',t('coinbase')+' '+n(data.coinbase_transactions??0)).replace('#/transactions/','#/transactions?kind=coinbase')} · ${link('transactions','',t('ordinary')+' '+n(data.ordinary_transactions??0)).replace('#/transactions/','#/transactions?kind=ordinary')}`:esc(t(note))}</div></div>`).join('');$('updated').textContent=when(data.updated_at);$('updated').title=t('notnetwork');}
const download=(path,label,snapshot)=>{const query=typeof snapshot==='string'&&/^[0-9a-f]{64}$/.test(snapshot)?(path.includes('?')?'&':'?')+'snapshot='+snapshot:'';return `<a class="quiet-button" href="/api/${esc(path+query)}" download>${esc(label)}</a>`;};
const signedMoney=value=>value===null||value===undefined?'—':(value.startsWith('-')||value==='0.00000000'?'':'+')+money(value);
function transactionTable(items,{address=false}={}){
  if(!items.length)return empty('emptytx');
  const fields=address?['txid','block','received','spentinputs','netchange']:['txid','block','total','size'];
  return `<div class="table-wrap"><table><thead><tr>${fields.map(key=>`<th>${esc(t(key))}</th>`).join('')}</tr></thead><tbody>${items.map(tx=>`<tr><td>${tx.coinbase?`<span class="coinbase">${esc(t('coinbase'))}</span>`:''}${link('transaction',tx.txid,short(tx.txid),'mono hash')}</td><td>${tx.height!==undefined?link('block',tx.height,n(tx.height)):esc(tx.pending?t('pending'):'—')}</td>${address?`<td class="number">${tx.received===null||tx.received===undefined?'—':esc(money(tx.received))}</td><td class="number">${tx.spent===null||tx.spent===undefined?'—':esc(money(tx.spent))}</td><td class="number ${tx.net_change?.startsWith('-')?'negative':'positive'}">${esc(signedMoney(tx.net_change))} <small>SMW</small></td>`:`<td class="reward number">${esc(money(tx.output_total))} <small>SMW</small></td><td class="number">${n(tx.size)} B</td>`}</tr>`).join('')}</tbody></table></div>`;
}
function home(data){const blocks=`<div class="table-wrap"><table><thead><tr>${['height','hash','time','count','reward'].map(x=>`<th>${esc(t(x))}</th>`).join('')}</tr></thead><tbody>${data.blocks.map(b=>`<tr><td>${link('block',b.height,n(b.height),'block-no number')}</td><td>${link('block',b.hash,short(b.hash),'mono hash')}</td><td class="number">${esc(when(b.timestamp))}</td><td class="number">${n(b.tx_count)}</td><td class="reward number">${esc(money(b.reward))} SMW</td></tr>`).join('')}</tbody></table></div><div class="panel-bottom"><span>${esc(t('snapshot'))}</span><div class="pagination">${location.hash.includes('before=')?button('#/',t('newest')):''}${data.next_before!==null?button('#/?before='+data.next_before,t('older')):''}</div></div>`;
return panel(t('latest'),blocks,t('latestnote'),t('active'),download('export/blocks.csv?limit=1000',t('csv1000'),data.snapshot))+`<div class="grid-bottom">${panel(t('mempool'),data.mempool.length?transactionTable(data.mempool):empty('empty'),t('waiting'))}${panel(t('difficulty'),`<div class="metric-list">${metric('difficulty',esc(data.algorithm==='DGW v3'?'DGW v3':t('difficulty')+' · 2,016 '+t('blocks')))}${metric('activation',n(data.activation_height))}${metric('target','600 '+esc(t('seconds')))}${metric('utxos',n(data.utxos))}</div>`, '', '',button('#/statistics',t('statistics')))}</div>`;}
const heading=(title,key)=>`<div class="breadcrumb"><a href="#/">Explorer</a><span>/</span><span>${esc(title)}</span></div><h2 class="detail-title">${esc(title)}</h2><div class="detail-hash mono"><span>${esc(key)}</span><button class="copy" data-copy="${esc(key)}">${esc(t('copy'))}</button></div>`;
function pageUrl(base,offset){
  const [route,query='']=base.split('?'),params=new URLSearchParams(query);
  params.set('offset',String(offset));return route+'?'+params.toString();
}
function pageNumbers(current,pages){
  return [...new Set([1,pages,current-2,current-1,current,current+1,current+2])].filter(page=>page>=1&&page<=pages).sort((a,b)=>a-b);
}
function pagination(offset,total,size,base){
  const current=Math.floor(offset/size)+1,pages=Math.max(1,Math.ceil(total/size));
  let previous=0;
  const numbers=pageNumbers(current,pages).map(page=>{
    const gap=previous&&page>previous+1?'<span class="page-gap" aria-hidden="true">…</span>':'';previous=page;
    return gap+`<a class="quiet-button page-number ${page===current?'selected':''}" href="${esc(pageUrl(base,(page-1)*size))}" ${page===current?'aria-current="page"':''}>${n(page)}</a>`;
  }).join('');
  return `<div class="panel-bottom page-controls"><span class="page-status">${esc(t('page'))} ${n(current)} / ${n(pages)} · ${n(total)} ${esc(t('transactions'))}</span><div class="pagination">${offset?button(pageUrl(base,Math.max(0,offset-size)),t('previous')):''}${numbers}${offset+size<total?button(pageUrl(base,offset+size),t('more')):''}</div><form class="page-jump" data-page-jump data-page-base="${esc(base)}" data-page-size="${size}" data-page-count="${pages}"><label>${esc(t('page'))}<input type="number" name="page" aria-label="${esc(t('page'))}" min="1" max="${pages}" step="1" inputmode="numeric" required value="${Math.min(current,pages)}"></label><button type="submit">${esc(t('go'))}</button></form></div>`;
}
function jumpPage(event){
  const form=event.target.closest('[data-page-jump]');if(!form)return;
  event.preventDefault();const input=form.querySelector('input');
  if(!input.reportValidity())return;
  const page=Number(input.value),pages=Number(form.dataset.pageCount),size=Number(form.dataset.pageSize);
  if(!Number.isSafeInteger(page)||page<1||page>pages)return;
  const offset=(page-1)*size;if(!Number.isSafeInteger(offset)||offset>1000000)return;
  const url=pageUrl(form.dataset.pageBase,offset);
  if(location.hash===url)render();else location.hash=url;
}
function blockPage(data){return heading(t('block')+' #'+n(data.height),data.hash)+panel(t('details'),`<div class="detail-grid">${metric('confirmations','<span class="status-badge">'+n(data.confirmations)+'</span>')}${metric('time',esc(when(data.timestamp)))}${metric('size',n(data.size)+' B')}${metric('weight',n(data.weight)+' WU')}${metric('count',n(data.tx_count))}${metric('reward',esc(money(data.reward))+' SMW')}${metric('bits','<span class="mono">'+esc(data.bits)+'</span>')}${metric('nonce',n(data.nonce))}${metric('difficulty',esc(data.algorithm==='DGW v3'?'DGW v3':t('difficulty')+' · 2,016 '+t('blocks')))}${metric('version',n(data.version))}${metric('parent',data.height?link('block',data.parent,short(data.parent),'mono'):'—')}${metric('next',data.next?link('block',data.next,short(data.next),'mono'):'—')}<div class="wide">${metric('merkle','<span class="mono hash full">'+esc(data.merkle)+'</span>')}</div></div>`,'',t('active'),download('block/'+encodeURIComponent(data.hash)+'/raw',t('rawblock'),data.snapshot)+button('#/audit/'+data.hash,t('audit')))+panel(t('transactions'),transactionTable(data.transactions)+pagination(data.offset,data.tx_count,50,'#/block/'+data.hash));}
function transactionPage(data){let input=data.coinbase?`<div class="io"><span class="coinbase">${esc(t('coinbase'))}</span><p>${esc(t('mint'))}</p></div>`:data.inputs.map(i=>`<div class="io">${i.address?link('address',i.address,short(i.address),'mono'):link('transaction',i.previous,short(i.previous),'mono')}<div class="io-meta">${link('transaction',i.previous,short(i.previous),'mono')} : ${i.previous_n}</div>${i.value?`<div class="io-amount number">${esc(money(i.value))} SMW</div>`:''}</div>`).join('');let output=data.outputs.map(o=>`<div class="io">${o.address?link('address',o.address,short(o.address),'mono'):`<span class="mono">${esc(t('unknown'))}</span>`}<div class="io-amount number">${esc(money(o.value))} SMW</div><div class="io-meta">#${o.n} · ${o.spent_by?link('transaction',o.spent_by,t('spent')):esc(data.pending?t('pending'):o.unspendable?t('unspendable'):t('unspent'))}</div></div>`).join('');return heading(t('txid'),data.txid)+panel(t('details'),`<div class="detail-grid">${metric('confirmations',n(data.confirmations))}${metric('block',data.pending?esc(t('pending')):link('block',data.height,n(data.height)))}${metric('size',n(data.size)+' B')}${metric('weight',n(data.weight)+' WU')}${metric('vsize',n(data.vsize??Math.ceil(data.weight/4))+' vB')}${metric('feerate',esc(data.fee_rate??'—')+' /vB')}${metric('total',esc(money(data.output_total))+' SMW')}${metric('fee',data.fee===null||data.fee===undefined?'—':esc(money(data.fee))+' SMW')}</div>`,'',data.pending?t('pending'):data.coinbase?t('coinbase'):t('ordinary'),download('transaction/'+encodeURIComponent(data.txid)+'/raw',t('rawtx'),data.snapshot)+(data.pending?'':button('#/proof/'+data.txid,t('proof')))+button('#/related/'+data.txid,t('related'))+download('transaction/'+data.txid+'/receipt?lang='+encodeURIComponent(lang),t('receipt'),data.snapshot))+panel(t('transactions'),`<div class="flow"><div><h3>${esc(t('inputs'))}</h3>${input}</div><span class="flow-arrow">→</span><div><h3>${esc(t('outputs'))}</h3>${output}</div></div>`);}
function transactionsPage(data){
  const filters=[['all','all'],['coinbase','coinbaselist'],['ordinary','ordinarylist']].map(([kind,label])=>`<a class="quiet-button ${data.kind===kind?'selected':''}" href="#/transactions?kind=${kind}">${esc(t(label))}</a>`).join('');
  const rows=data.transactions.length?`<div class="table-wrap"><table><thead><tr>${['type','txid','block','time','total','fee','feerate','confirmations'].map(key=>`<th>${esc(t(key))}</th>`).join('')}</tr></thead><tbody>${data.transactions.map(tx=>`<tr><td><span class="${tx.coinbase?'coinbase':'status-badge'}">${esc(t(tx.coinbase?'coinbase':'ordinary'))}</span></td><td>${link('transaction',tx.txid,short(tx.txid),'mono hash')}</td><td>${link('block',tx.height,n(tx.height),'number')}</td><td class="number">${esc(when(tx.timestamp))}</td><td class="number">${esc(money(tx.output_total))} SMW</td><td>${esc(tx.fee===null?'—':money(tx.fee))}</td><td>${esc(tx.fee_rate??'—')}</td><td class="number">${n(tx.confirmations)}</td></tr>`).join('')}</tbody></table></div>`:empty('emptytx');
  const base='#/transactions?'+filterQuery(data.filters,{kind:data.kind});
  const pages=pagination(data.offset,data.total,25,base);
  const query=filterQuery(data.filters,{kind:data.kind});
  return panel(t('filters'),filterForm(data.filters,false,data.kind))+panel(t('transactionhistory'),rows+pages,t('feeunit'),'',filters+download('export/transactions.csv?'+query,t('csv'),data.snapshot)+download('report/transactions?'+query+'&lang='+encodeURIComponent(lang),t('pdf'),data.snapshot));
}
function addressPage(data){const metrics=[['confirmed',data.confirmed],['available',data.available],['immature',data.immature]].map(([key,value])=>`<div class="panel"><div class="stat-label">${esc(t(key))}</div><div class="stat-value number">${esc(money(value))}<small> SMW</small></div></div>`).join('');const coins=data.utxos.length?`<div class="table-wrap"><table><thead><tr><th>${esc(t('txid'))}</th><th>${esc(t('height'))}</th><th>SMW</th><th>${esc(t('details'))}</th></tr></thead><tbody>${data.utxos.map(o=>`<tr><td>${link('transaction',o.txid,short(o.txid),'mono')} : ${o.n}</td><td>${link('block',o.height,n(o.height))}</td><td>${esc(money(o.value))}</td><td>${esc(o.pending_spent?t('pendingreserved'):o.mature?t('mature'):t('immaturestatus'))}</td></tr>`).join('')}</tbody></table></div>`:empty('emptytx');return heading(t('address'),data.address)+`<div class="address-metrics">${metrics}</div>`+panel(t('history'),transactionTable(data.transactions,{address:true})+pagination(data.offset,data.total_transactions,25,'#/address/'+data.address),t('addressnote'),'',download('export/address/'+encodeURIComponent(data.address)+'?limit=1000',data.total_transactions>1000?t('csv1000'):t('csv'),data.snapshot)+button('#/history/'+encodeURIComponent(data.address),t('period'))+download('address/'+encodeURIComponent(data.address)+'/report?lang='+encodeURIComponent(lang),t('pdf'),data.snapshot))+ (data.pending.length?panel(t('mempool'),transactionTable(data.pending,{address:true}),t('pendingreceived')+': '+money(data.pending_received)+' SMW'):'')+panel(t('utxolist'),coins,`${Math.min(data.utxo_count,100)} / ${data.utxo_count}`);}
function duration(seconds){
  if(seconds===null||seconds===undefined)return '—';
  const value=Math.max(0,Math.floor(seconds));
  if(value<60)return n(value)+' '+t('seconds');
  if(value<3600)return n(Math.floor(value/60))+' '+t('minutes');
  if(value<86400)return n(Math.floor(value/3600))+' '+t('hours');
  return n(Math.floor(value/86400))+' '+t('days');
}
function freshness(data){
  const full=v=>v===undefined?'—':new Date(v*1000).toLocaleString(locale(),{hour12:false});
  $('freshness').innerHTML=`<div><span>${esc(t('lastblock'))}</span><strong>${esc(full(data.last_block_time))}</strong></div><div><span>${esc(t('readtime'))}</span><strong>${esc(full(data.updated_at))}</strong></div><div><span>${esc(t('blockage'))}</span><strong>${esc(duration(data.last_block_age_seconds))}</strong></div><p>${esc(t('syncunknown'))}</p>`;
  $('freshness').hidden=false;
}
function chart(data,key,title){
  const points=data.points.filter(p=>typeof p[key]==='number'&&Number.isFinite(p[key]));
  if(!points.length)return panel(title,empty('nodata'));
  const values=points.map(p=>p[key]),min=Math.min(...values),max=Math.max(...values),spread=max-min||1;
  const x=i=>54+i*620/Math.max(points.length-1,1),y=v=>max===min?100:160-(v-min)*120/spread;
  const coordinates=points.map((p,i)=>x(i).toFixed(2)+','+y(p[key]).toFixed(2)).join(' ');
  const label=v=>Math.abs(v)>=1e8||(v!==0&&Math.abs(v)<.0001)?v.toExponential(3):v.toLocaleString(locale(),{maximumFractionDigits:4});
  const svg=`<svg class="chart" viewBox="0 0 700 202" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title><line x1="54" y1="40" x2="674" y2="40" class="chart-grid"/><line x1="54" y1="100" x2="674" y2="100" class="chart-grid"/><line x1="54" y1="160" x2="674" y2="160" class="chart-grid"/><text x="48" y="44" text-anchor="end">${esc(label(max))}</text><text x="48" y="164" text-anchor="end">${esc(label(min))}</text><polyline points="${coordinates}" fill="none" class="chart-line"/>${[0,points.length-1].filter((v,i,a)=>a.indexOf(v)===i).map(i=>`<circle cx="${x(i)}" cy="${y(points[i][key])}" r="3" class="chart-dot"><title>#${points[i].height}: ${esc(label(points[i][key]))}</title></circle>`).join('')}<text x="54" y="190">#${points[0].height}</text><text x="674" y="190" text-anchor="end">#${points[points.length-1].height}</text></svg>`;
  return panel(title,svg);
}
function statisticsPage(data){
  const ranges=[24,144,2016].map(limit=>`<a class="quiet-button ${data.limit===limit?'selected':''}" href="#/statistics?limit=${limit}">${n(limit)} ${esc(t('sampleblocks'))}</a>`).join('');
  return panel(t('statistics'),`<div class="metric-list">${metric('sampleblocks',n(data.from_height)+'–'+n(data.to_height))}${metric('ordinarycount',n(data.ordinary_transactions))}${metric('rewardtotal',esc(money(data.total_claimed_rewards))+' SMW')}</div>`,t('chartnote'),'',button('#/transactions?kind=ordinary',t('browseordinary'))+ranges+download('statistics/export?limit='+data.limit,t('csv'),data.snapshot))+chart(data,'difficulty_ratio',t('difficultychart'))+chart(data,'interval_seconds',t('intervalchart'))+chart(data,'transactions',t('transactionchart'));
}
function proofPage(data){
  return heading(t('proof'),data.txid)+panel(t('proof'),`<div class="detail-grid">${metric('proofvalid',data.proof_valid?'✓':'—')}${metric('block',link('block',data.block_hash,n(data.block_height)))}${metric('proofposition',n(data.transaction_index))}${metric('proofcount',n(data.transaction_count))}<div class="wide">${metric('merkle','<span class="mono hash full">'+esc(data.merkle_root)+'</span>')}</div></div>`,t('proofscope'),'',download('transaction/'+data.txid+'/proof?download=1',t('proofdownload'),data.snapshot))+panel(t('proofpath'),data.siblings.length?`<div class="metric-list">${data.siblings.map((hash,i)=>`<div class="metric"><span>#${i}</span><span class="mono hash full">${esc(hash)}</span></div>`).join('')}</div>`:`<div class="empty">0</div>`);
}
function showNotice(message){$('notice').textContent=message;$('notice').hidden=!message;}
async function readPage(parts,params,signal){
  for(let attempt=0;attempt<3;attempt++){
    try{
      const before=params.get('before');
      const overview=await api('overview'+(before!==null?'?before='+encodeURIComponent(before):''),{signal});
      if(!parts.length)return {overview,detail:null};
      const offset=params.get('offset')||'0';
      let path;
      const advanced=advancedPath(parts,params);
      if(advanced)path=advanced;
      else if(parts[0]==='statistics'&&parts.length===1)path='statistics?limit='+encodeURIComponent(params.get('limit')||'144');
      else if(parts[0]==='proof'&&parts.length===2){let key;try{key=decodeURIComponent(parts[1]);}catch{const error=new Error(t('invalid'));error.status=400;throw error;}path='transaction/'+encodeURIComponent(key)+'/proof?';}
      else if(parts[0]==='transactions'&&parts.length===1)path='transactions?kind='+encodeURIComponent(params.get('kind')||'ordinary')+'&offset='+encodeURIComponent(offset);
      else if(parts[0]==='mempool'&&parts.length===1)path='mempool?offset='+encodeURIComponent(offset);
      else if(['block','transaction','address'].includes(parts[0])&&parts.length===2){
        let key;try{key=decodeURIComponent(parts[1]);}catch{const error=new Error(t('invalid'));error.status=400;throw error;}
        path=parts[0]+'/'+encodeURIComponent(key)+'?offset='+encodeURIComponent(offset);
      }else{const error=new Error(t('invalid'));error.status=400;throw error;}
      const detail=await api(path+(path.endsWith('?')?'':'&')+'snapshot='+encodeURIComponent(overview.snapshot),{signal});
      return {overview,detail};
    }catch(error){if(error.status===409&&attempt<2)continue;throw error;}
  }
}
async function render({auto=false}={}){
  if(auto&&(rendering||document.activeElement?.closest('[data-page-jump],[data-advanced-filter]')))return;
  const ticket=++sequence;
  renderController?.abort();renderController=new AbortController();
  const signal=renderController.signal;
  rendering=true;$('refresh').disabled=true;$('view').setAttribute('aria-busy','true');
  if(!auto){searchNotice='';showNotice('');$('view').innerHTML='<div class="loading">'+esc(t('loading'))+'</div>';}
  try{
    const route=(location.hash.slice(1)||'/').split('?');
    const parts=route[0].split('/').filter(Boolean),params=new URLSearchParams(route[1]||'');
    const {overview:data,detail}=await readPage(parts,params,signal);
    if(ticket!==sequence)return;
    stats(data);freshness(data);$('stats').hidden=false;
    let html;
    if(!parts.length)html=home(data);
    else if(parts[0]==='mempool')html=panel(t('mempool'),(detail.transactions.length?transactionTable(detail.transactions):empty('empty'))+pagination(detail.offset,detail.total,25,'#/mempool'),t('waiting')+' · '+n(detail.total));
    else if(['fees','mining','audit','related','history'].includes(parts[0]))html=advancedPage(parts[0],detail);
    else if(parts[0]==='transactions')html=transactionsPage(detail);
    else if(parts[0]==='statistics')html=statisticsPage(detail);
    else if(parts[0]==='proof')html=proofPage(detail);
    else html=parts[0]==='block'?blockPage(detail):parts[0]==='transaction'?transactionPage(detail):addressPage(detail);
    $('view').innerHTML=html;showNotice(searchNotice);
  }catch(error){
    if(ticket!==sequence||signal.aborted)return;
    showNotice(error.status===404?t('notfound'):error.status===400?t('invalid'):t('unavailable')+' '+error.message);
    $('stats').hidden=true;$('freshness').hidden=true;$('updated').textContent=t('unavailable');$('view').innerHTML=empty('error');
  }finally{
    if(ticket===sequence){rendering=false;$('refresh').disabled=false;$('view').setAttribute('aria-busy','false');}
  }
}
$('search').addEventListener('submit',async event=>{
  event.preventDefault();const submit=event.currentTarget.querySelector('button');
  const ticket=++searchSequence,route=routeVersion;submit.disabled=true;
  try{
    const result=await api('search?q='+encodeURIComponent($('query').value.trim()));
    if(ticket!==searchSequence||route!==routeVersion)return;
    searchNotice='';showNotice('');
    const url='#/'+result.type+'/'+encodeURIComponent(result.key);
    if(location.hash===url)await render();else location.hash=url;
  }catch(error){
    if(ticket!==searchSequence||route!==routeVersion)return;
    searchNotice=error.status===404?t('notfound'):error.status===400?t('invalid'):t('unavailable')+' '+error.message;
    showNotice(searchNotice);
  }finally{submit.disabled=false;}
});
$('refresh').addEventListener('click',()=>render());
$('language').innerHTML=languageChoices.map(([code,label])=>`<option value="${esc(code)}">${esc(label)}</option>`).join('');
$('language').addEventListener('change',()=>{
  lang=languageChoices.some(([code])=>code===$('language').value)?$('language').value:'ko';
  try{localStorage.setItem('sumuww-explorer-language',lang);}catch{}
  translate();render();
});

document.addEventListener('submit',jumpPage);
document.addEventListener('submit',advancedSubmit);
document.addEventListener('click',async event=>{
  const button=event.target.closest('[data-copy]');if(!button)return;
  try{await navigator.clipboard.writeText(button.dataset.copy);button.textContent=t('copied');setTimeout(()=>button.textContent=t('copy'),1500);}catch{button.textContent=t('error');}
});
window.addEventListener('hashchange',()=>{routeVersion++;searchSequence++;render();window.scrollTo({top:0,behavior:'smooth'});});
translate();render();setInterval(()=>{if(!document.hidden)render({auto:true});},15000);
