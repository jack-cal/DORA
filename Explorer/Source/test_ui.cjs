// Executes the actual UI code with a small DOM/fetch fixture; no browser or node data is modified.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {test}=require('node:test');
const source=fs.readFileSync(__dirname+'/dist/app.js','utf8');

test('unsupported formatting locale has an explicit fallback',async()=>{
  const h=await boot();
  h.run("lang='mn-Mong'");
  assert.ok(['mn-Mong-CN','mn','en'].includes(h.run('locale()')));
  assert.equal(h.run('Intl.DateTimeFormat.supportedLocalesOf([locale()]).length'),1);
});

test('advanced routes preserve only supported filters and encode keys',async()=>{
  const h=await boot();
  assert.equal(h.run("advancedPath(['transactions'],new URLSearchParams('kind=ordinary&sort=rate&order=asc&min_amount=0.00000001&junk=x'))"),'transactions?min_amount=0.00000001&sort=rate&order=asc&kind=ordinary&offset=0');
  assert.equal(h.run("advancedPath(['history','sumuww1abc'],new URLSearchParams('max_height=123&offset=25'))"),'address/sumuww1abc/history?max_height=123&offset=25');
});
test('advanced history filters survive pagination and PDF links',async()=>{
  const h=await boot();const html=h.run("historyPage({address:'sumuww1x',filters:{min_height:'10',max_height:'50'},from_height:10,to_height:50,opening_balance:'1.00000000',closing_balance:'2.00000000',received:'2.00000000',spent:'1.00000000',net_change:'1.00000000',transactions:[],points:[],offset:0,total:60,snapshot:'a'.repeat(64)})");
  assert.ok(html.includes('min_height=10&amp;max_height=50&amp;lang=ko&amp;snapshot='));assert.ok(html.includes('min_height=10&amp;max_height=50&amp;offset=25'));
});
test('unknown fees and empty mempool render without invented rates',async()=>{
  const h=await boot();const html=h.run("feesPage({recommendations:[{level:'economy',fee_rate:null},{level:'normal',fee_rate:null},{level:'priority',fee_rate:null}],total:0,vsize:0,total_known_fees:'0.00000000',unresolved_fees:0,sample_count:0,buckets:[],transactions:[]})");
  assert.ok(html.includes('—'));assert.ok(html.includes('수수료 표본'));assert.ok(!html.includes('NaN'));
});
test('audit distinguishes missing observation from an observed empty selection',async()=>{
  const h=await boot();assert.ok(h.run("auditPage({height:2,blockhash:'a'.repeat(64),available:false})").includes('생성 전 관측 기록이 없습니다'));
  assert.ok(h.run("auditPage({height:2,blockhash:'a'.repeat(64),available:true,observed_at:1,expected:[],actual:[],missing:[],added:[],unseen:[]})").includes('예상 거래 목록'));
});
test('new pages are renderable in all 34 languages',async()=>{
  const h=await boot();for(const [code] of h.run('languageChoices')){h.run('lang='+JSON.stringify(code));const html=h.run("relatedPage({txid:'a'.repeat(64),package_fee:null,package_vsize:null,effective_fee_rate:null,parents:[],children:[],pending_ancestors:[],pending_descendants:[]})");assert.ok(!html.includes('undefined'));assert.ok(!html.includes('<script>'));}
});
const overview=(height=2,snapshot='a'.repeat(64))=>({height,snapshot,updated_at:1,transactions:height+1,mempool_count:0,mempool:[],interval:600,blocks:[],next_before:null,algorithm:'DGW v3',activation_height:8064,utxos:1});
const block={hash:'b'.repeat(64),height:2,confirmations:1,timestamp:1,size:100,weight:400,tx_count:0,reward:'50.00000000',bits:'1e0377ae',nonce:1,algorithm:'DGW v3',version:1,parent:'c'.repeat(64),next:null,merkle:'d'.repeat(64),transactions:[],offset:0};
const response=(data,status=200)=>({ok:status>=200&&status<300,status,json:async()=>data});
test('revealed spending conditions are escaped and translated in all languages',async()=>{
  const h=await boot();
  for(const [code] of h.run('languageChoices')){
    h.run('lang='+JSON.stringify(code));
    const output=h.run("spendingConditions({spending_conditions:{required_signatures:2,lock_kind:'height',lock_value:100,decoded_only:true,witness_script:'<img src=x onerror=alert(1)>'}})");
    assert.ok(output.includes('required_signatures'));assert.ok(output.includes('&lt;img'));
    assert.ok(!output.includes('<img'));assert.ok(!output.includes('undefined'));
  }
  assert.equal(h.run('spendingConditions({})'),'');
});
async function boot({blockedStorage=false,savedLanguage="ko"}={}){
  const elements=new Map();
  function element(id){if(!elements.has(id))elements.set(id,{hidden:false,textContent:'',innerHTML:'',value:'',disabled:false,dataset:{},listeners:{},setAttribute(k,v){this[k]=v;},addEventListener(k,v){this.listeners[k]=v;},querySelector(){return element('submit');}});return elements.get(id);}
  const context=vm.createContext({console,AbortController,URLSearchParams,Date,encodeURIComponent,decodeURIComponent,
    setTimeout,clearTimeout,setInterval(){return 0;},
    localStorage:{getItem(){if(blockedStorage)throw Error('blocked');return savedLanguage;},setItem(){if(blockedStorage)throw Error('blocked');}},
    location:{hash:'#/'},navigator:{clipboard:{writeText:async()=>{}}},
    document:{hidden:false,documentElement:{lang:'ko'},getElementById:element,querySelectorAll(){return [];},addEventListener(){}},
    window:{addEventListener(){},scrollTo(){}},fetch:async()=>response(overview())});
  vm.runInContext(fs.readFileSync(__dirname+'/dist/languages.js','utf8'),context);
  vm.runInContext(fs.readFileSync(__dirname+'/dist/advanced.js','utf8'),context);
  vm.runInContext(source,context);
  await vm.runInContext('render()',context);
  return {context,element,run:s=>vm.runInContext(s,context)};
}
test('amount display preserves one smallest unit and the exact maximum',async()=>{
  const h=await boot();assert.equal(h.run("money('0.00000001')"),'0.00000001');
  assert.equal(h.run("money('17999999.97690000')"),'17,999,999.9769');
});
test('chain text cannot inject HTML or javascript links',async()=>{
  const h=await boot();assert.equal(h.run("esc('<img src=x onerror=alert(1)>')"),'&lt;img src=x onerror=alert(1)&gt;');
  const value=h.run("link('address','javascript:alert(1)','<script>bad</script>')");
  assert.ok(!value.includes('<script>'));assert.ok(value.includes('href="#/address/javascript%3A'));
});
test('blocked localStorage still allows initialization and language changes',async()=>{
  const h=await boot({blockedStorage:true});h.element('language').value='en';await h.element('language').listeners.change();
  assert.equal(h.context.document.documentElement.lang,'en');
});
test('snapshot conflict retries the entire page before publishing either part',async()=>{
  const h=await boot();h.context.location.hash='#/block/2';let calls=0;
  h.context.fetch=async url=>{calls++;if(url.includes('/overview'))return response(overview(2,calls===1?'a'.repeat(64):'b'.repeat(64)));if(calls===2)return response({code:'snapshot_changed'},409);assert.ok(url.includes('snapshot='+'b'.repeat(64)));return response(block);};
  await h.run('render()');assert.equal(calls,4);assert.ok(h.element('view').innerHTML.includes('블록 #2'));assert.equal(h.element('notice').hidden,true);
});
test('three snapshot conflicts stop with an error and hide stale statistics',async()=>{
  const h=await boot();h.context.location.hash='#/block/2';let calls=0;
  h.context.fetch=async url=>{calls++;return url.includes('/overview')?response(overview()):response({code:'snapshot_changed'},409);};
  await h.run('render()');assert.equal(calls,6);assert.equal(h.element('stats').hidden,true);assert.equal(h.element('notice').hidden,false);
});
test('network failure hides old numbers and recovery restores the page',async()=>{
  const h=await boot();h.context.fetch=async()=>{throw Error('offline');};await h.run('render()');
  assert.equal(h.element('stats').hidden,true);assert.equal(h.element('notice').hidden,false);
  h.context.fetch=async()=>response(overview(3));await h.run('render({auto:true})');
  assert.equal(h.element('stats').hidden,false);assert.equal(h.element('notice').hidden,true);
});
test('slow requests time out and restore the refresh control',async()=>{
  const h=await boot();h.context.setTimeout=(fn,ms)=>setTimeout(fn,ms===15000?1:ms);
  h.context.fetch=async(_url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true}));
  await h.run('render()');assert.ok(h.element('notice').textContent.includes('초과'));assert.equal(h.element('refresh').disabled,false);
});
test('invalid JSON responses show a read failure, not a successful empty page',async()=>{
  const h=await boot();h.context.fetch=async()=>({ok:true,status:200,json:async()=>{throw Error('bad json');}});
  await h.run('render()');assert.equal(h.element('stats').hidden,true);assert.equal(h.element('notice').hidden,false);
});
test('automatic refresh does not erase a search validation error',async()=>{
  const h=await boot();h.context.fetch=async url=>url.includes('/search')?response({},400):response(overview());
  h.element('query').value='bad';await h.element('search').listeners.submit({preventDefault(){},currentTarget:h.element('search')});
  const message=h.element('notice').textContent;await h.run('render({auto:true})');
  assert.equal(h.element('notice').textContent,message);assert.equal(h.element('notice').hidden,false);
  await h.run('render()');assert.equal(h.element('notice').hidden,true);
});
test('old search responses cannot navigate after the user changes pages',async()=>{
  const h=await boot();let complete;h.context.fetch=()=>new Promise(resolve=>complete=resolve);
  const task=h.element('search').listeners.submit({preventDefault(){},currentTarget:h.element('search')});
  h.run('routeVersion++;searchSequence++');h.context.location.hash='#/mempool';complete(response({type:'block',key:'2'}));await task;
  assert.equal(h.context.location.hash,'#/mempool');assert.equal(h.element('submit').disabled,false);
});
test('a superseded render cannot overwrite the newer result',async()=>{
  const h=await boot();let complete;h.context.fetch=()=>new Promise(resolve=>complete=resolve);
  const old=h.run('render()');h.context.fetch=async()=>response(overview(3));await h.run('render()');
  complete(response(overview(1)));await old;assert.ok(h.element('stats').innerHTML.includes('>3</div>'));
});
test('background refresh cannot pile up requests while a render is pending',async()=>{
  const h=await boot();let complete,calls=0;h.context.fetch=()=>{calls++;return new Promise(resolve=>complete=resolve);};
  const task=h.run('render()');await h.run('render({auto:true})');assert.equal(calls,1);
  complete(response(overview()));await task;
});
test('malformed encoded routes fail as invalid input',async()=>{
  const h=await boot();h.context.location.hash='#/address/%E0%A4%A';await h.run('render()');
  assert.ok(h.element('notice').textContent.includes('올바른 SUMUWW 주소'));assert.equal(h.element('stats').hidden,true);
});
test('mempool pages send the selected offset and snapshot',async()=>{
  const h=await boot();h.context.location.hash='#/mempool?offset=25';let path;
  h.context.fetch=async url=>{if(url.includes('/overview'))return response(overview());path=url;return response({transactions:[],offset:25,total:55});};
  await h.run('render()');assert.ok(path.includes('offset=25&snapshot='));assert.ok(h.element('view').innerHTML.includes('offset=50'));
});
test('block zero remains a navigable value',async()=>{
  const h=await boot();h.context.tx={txid:'a'.repeat(64),height:0,coinbase:true,output_total:'50.00000000',size:10};
  assert.ok(h.run('transactionTable([tx])').includes('#/block/0'));
});
test('address history shows received, spent and exact signed change',async()=>{
  const h=await boot();h.context.tx={txid:'a'.repeat(64),height:2,coinbase:false,output_total:'48.00000000',size:10,received:'18.00000000',spent:'49.00000000',net_change:'-31.00000000'};
  const html=h.run('transactionTable([tx],{address:true})');
  assert.ok(html.includes('받은 출력'));assert.ok(html.includes('사용한 입력'));assert.ok(html.includes('-31'));
  assert.ok(!html.includes('출력 합계'));assert.equal(h.run("signedMoney('-0.00000001')"),'-0.00000001');
  assert.equal(h.run("signedMoney('0.00000001')"),'+0.00000001');assert.equal(h.run('signedMoney(null)'),'—');
});
test('confirmed transaction shows proof and raw controls, pending shows raw only',async()=>{
  const h=await boot();h.context.tx={txid:'a'.repeat(64),height:2,confirmations:1,coinbase:true,output_total:'50.00000000',size:100,weight:400,inputs:[],outputs:[],pending:false};
  let html=h.run('transactionPage(tx)');assert.ok(html.includes('#/proof/'));assert.ok(html.includes('/api/transaction/'));assert.ok(html.includes('/raw'));
  h.context.tx.pending=true;html=h.run('transactionPage(tx)');assert.ok(!html.includes('#/proof/'));
});
test('statistics route includes selected range, charts and CSV control',async()=>{
  const h=await boot();h.context.location.hash='#/statistics?limit=24';let requested;
  const detail={limit:24,from_height:1,to_height:2,ordinary_transactions:0,total_claimed_rewards:'100.00000000',points:[{height:1,difficulty_ratio:1,interval_seconds:600,transactions:1},{height:2,difficulty_ratio:1,interval_seconds:-10,transactions:1}]};
  h.context.fetch=async url=>{if(url.includes('/overview'))return response(overview());requested=url;return response(detail);};
  await h.run('render()');const html=h.element('view').innerHTML;
  assert.ok(requested.includes('limit=24&snapshot='));assert.equal((html.match(/<svg /g)||[]).length,3);
  assert.ok(html.includes('statistics/export?limit=24'));assert.ok(!html.includes('NaN'));
});
test('flat, singleton and unavailable chart series render safely',async()=>{
  const h=await boot();h.context.chartData={points:[{height:1,difficulty_ratio:1}]};
  assert.ok(!h.run("chart(chartData,'difficulty_ratio','Example')").includes('NaN'));
  assert.ok(h.run("chart(chartData,'interval_seconds','Example')").includes('표시할 데이터'));
});
test('proof page uses a snapshot and offers a JSON download',async()=>{
  const h=await boot();h.context.location.hash='#/proof/'+'a'.repeat(64);let requested;
  h.context.fetch=async url=>{if(url.includes('/overview'))return response(overview());requested=url;return response({txid:'a'.repeat(64),block_hash:'b'.repeat(64),block_height:2,merkle_root:'c'.repeat(64),transaction_index:0,transaction_count:1,siblings:[],proof_valid:true});};
  await h.run('render()');assert.ok(requested.includes('/proof?snapshot='));assert.ok(!requested.includes('offset='));
  assert.ok(h.element('view').innerHTML.includes('/proof?download=1'));assert.ok(h.element('view').innerHTML.includes('헤더에 대한 포함 확인'));
});
test('freshness separates block timestamp, data read time and unobserved synchronization',async()=>{
  const h=await boot();h.context.data={last_block_time:1,updated_at:3601,last_block_age_seconds:3600};h.run('freshness(data)');
  const html=h.element('freshness').innerHTML;assert.ok(html.includes('마지막 블록 시각'));assert.ok(html.includes('데이터 조회 시각'));
  assert.ok(html.includes('1 시간'));assert.ok(html.includes('일치 여부는 확인되지 않았습니다'));
});
test('raw and CSV links use local API download responses',async()=>{
  const h=await boot();assert.ok(h.run("download('export/blocks.csv?limit=1000','CSV')").includes('href="/api/export/blocks.csv?limit=1000" download'));
});


test('all page download controls retain the displayed snapshot',async()=>{
  const h=await boot();const snapshot='e'.repeat(64);
  h.context.data={...overview(),snapshot};
  const controls=[];
  controls.push(h.run('home(data)'));
  h.context.data={...block,snapshot};controls.push(h.run('blockPage(data)'));
  h.context.data={snapshot,txid:'a'.repeat(64),height:2,confirmations:1,coinbase:true,output_total:'50.00000000',size:100,weight:400,inputs:[],outputs:[],pending:false};
  controls.push(h.run('transactionPage(data)'));
  h.context.data={snapshot,address:'sumuww1test',confirmed:'0',available:'0',immature:'0',utxos:[],utxo_count:0,total_transactions:0,transactions:[],pending:[],offset:0};
  controls.push(h.run('addressPage(data)'));
  h.context.data={snapshot,limit:24,from_height:0,to_height:0,ordinary_transactions:0,total_claimed_rewards:'50',points:[]};
  controls.push(h.run('statisticsPage(data)'));
  h.context.data={snapshot,txid:'a'.repeat(64),block_hash:'b'.repeat(64),block_height:2,merkle_root:'c'.repeat(64),transaction_index:0,transaction_count:1,siblings:[],proof_valid:true};
  controls.push(h.run('proofPage(data)'));
  for(const html of controls){
    const downloads=[...html.matchAll(/href="([^"]+)" download/g)].map(m=>m[1]);
    assert.ok(downloads.length>0);
    for(const href of downloads)assert.ok(href.includes('snapshot='+snapshot),href);
  }
});

test('download query construction and invalid tokens cannot inject markup',async()=>{
  const h=await boot();h.context.token='a'.repeat(64);
  assert.ok(h.run("download('block/2/raw','Raw',token)").includes('/raw?snapshot='));
  assert.ok(h.run("download('statistics/export?limit=24','CSV',token)").includes('limit=24&amp;snapshot='));
  h.context.token='" onmouseover="alert(1)';
  assert.ok(!h.run("download('block/2/raw','Raw',token)").includes('onmouseover'));
});

test('empty address, mempool and genesis-only statistics are valid screens',async()=>{
  const h=await boot();
  h.context.data={address:'sumuww1test',confirmed:'0.00000000',available:'0.00000000',immature:'0.00000000',utxos:[],utxo_count:0,total_transactions:0,transactions:[],pending:[],offset:0};
  assert.ok(h.run('addressPage(data)').includes('아직 거래 내역이 없습니다'));
  h.context.data={limit:24,from_height:0,to_height:0,ordinary_transactions:0,total_claimed_rewards:'50.00000000',points:[{height:0,difficulty_ratio:1,interval_seconds:null,transactions:1}]};
  const html=h.run('statisticsPage(data)');assert.ok(!html.includes('NaN'));assert.ok(!html.includes('Infinity'));
});


test('transaction history filters keep their kind when paginating',async()=>{
 const h=await boot();h.context.location.hash='#/transactions?kind=coinbase&offset=25';let requested;
 h.context.fetch=async url=>{if(url.includes('/overview'))return response(overview());requested=url;return response({kind:'coinbase',total:70,offset:25,transactions:[]});};
 await h.run('render()');assert.ok(requested.includes('kind=coinbase&offset=25&snapshot='));
 const html=h.element('view').innerHTML;assert.ok(html.includes('채굴 보상 거래'));assert.ok(html.includes('일반 거래'));
 assert.ok(html.includes('kind=coinbase&amp;offset=0'));assert.ok(html.includes('kind=coinbase&amp;offset=50'));
});

test('transaction count links expose all, rewards and ordinary history',async()=>{
 const h=await boot();h.context.data={...overview(),coinbase_transactions:3,ordinary_transactions:1};h.run('stats(data)');
 const html=h.element('stats').innerHTML;assert.ok(html.includes('#/transactions?kind=all'));
 assert.ok(html.includes('#/transactions?kind=coinbase'));assert.ok(html.includes('#/transactions?kind=ordinary'));
});

test('every language has all strings and can render history, charts and freshness',async()=>{
 const h=await boot();const languages=h.run('languageChoices.map(item=>item[0])');assert.equal(languages.length,34);
 const expected=h.run('Object.keys(strings.en).sort().join()');
 for(const language of languages){
  h.context.code=language;assert.equal(h.run('Object.keys(strings[code]).sort().join()'),expected,language);
  assert.ok(h.run('Object.values(strings[code]).every(value=>typeof value==="string"&&value.trim().length>0)'),language);
  h.element('language').value=language;await h.element('language').listeners.change();await h.run('render()');
  assert.equal(h.context.document.documentElement.lang,language);assert.equal(h.context.document.documentElement.dir,['ar','ur'].includes(language)?'rtl':'ltr');
  h.context.data={kind:'ordinary',offset:0,total:1,transactions:[{txid:'a'.repeat(64),height:2,timestamp:1,confirmations:1,coinbase:false,output_total:'0.00000001'}]};
  const html=h.run('transactionsPage(data)');assert.ok(html.includes('#/transaction/'));assert.ok(html.includes('0.00000001'));
  h.context.data={limit:24,from_height:0,to_height:0,ordinary_transactions:0,total_claimed_rewards:'50',points:[{height:0,difficulty_ratio:1,transactions:1,interval_seconds:null}]};
  assert.ok(!h.run('statisticsPage(data)').includes('NaN'));
 }
});


test('numbered history shows current, first, last and nearby pages',async()=>{
 const h=await boot();const html=h.run("pagination(250,7501,25,'#/transactions?kind=coinbase')");
 assert.ok(html.includes('페이지 11 / 301'));assert.ok(html.includes('aria-current="page">11</a>'));
 assert.ok(html.includes('kind=coinbase&amp;offset=0'));assert.ok(html.includes('kind=coinbase&amp;offset=7500'));
 for(const page of [9,10,11,12,13])assert.ok(html.includes('>'+page+'</a>'));
 assert.equal((html.match(/page-gap/g)||[]).length,2);
});

test('first, last and empty histories keep valid navigation bounds',async()=>{
 const h=await boot();
 let html=h.run("pagination(0,51,25,'#/mempool')");assert.ok(!html.includes('이전 페이지'));assert.ok(html.includes('다음 페이지'));
 html=h.run("pagination(50,51,25,'#/mempool')");assert.ok(html.includes('이전 페이지'));assert.ok(!html.includes('다음 페이지'));
 html=h.run("pagination(0,0,25,'#/transactions?kind=ordinary')");assert.ok(html.includes('페이지 1 / 1'));
 assert.ok(!html.includes('offset=-'));assert.ok(!html.includes('다음 페이지'));
});

test('direct page input preserves the selected kind and navigates in one step',async()=>{
 const h=await boot();let prevented=false;
 const input={value:'42',reportValidity(){return true;}};
 const form={dataset:{pageBase:'#/transactions?kind=coinbase',pageSize:'25',pageCount:'301'},querySelector(){return input;}};
 h.context.event={preventDefault(){prevented=true;},target:{closest(){return form;}}};h.run('jumpPage(event)');
 assert.equal(prevented,true);assert.equal(h.context.location.hash,'#/transactions?kind=coinbase&offset=1025');
});

test('invalid direct page numbers cannot navigate outside the list',async()=>{
 const h=await boot();const input={value:'',reportValidity(){return true;}};
 const form={dataset:{pageBase:'#/transactions?kind=coinbase',pageSize:'25',pageCount:'301'},querySelector(){return input;}};
 h.context.event={preventDefault(){},target:{closest(){return form;}}};
 for(const value of ['0','-1','1.5','302','NaN','999999999999999999999']){input.value=value;h.run('jumpPage(event)');assert.equal(h.context.location.hash,'#/');}
 input.value='2';input.reportValidity=()=>false;h.run('jumpPage(event)');assert.equal(h.context.location.hash,'#/');
});

test('page URLs preserve unrelated queries and replace the old offset',async()=>{
 const h=await boot();assert.equal(h.run("pageUrl('#/transactions?kind=all&offset=50',250)"),'#/transactions?kind=all&offset=250');
 assert.equal(h.run("pageUrl('#/block/abc',100)"),'#/block/abc?offset=100');
 assert.equal(h.run("pageUrl('#/address/sumuww1example',25)"),'#/address/sumuww1example?offset=25');
 const html=h.run("pagination(50,120,50,'#/block/abc')");assert.ok(html.includes('offset=100'));
});

test('page number windows stay ordered, bounded and small across large lists',async()=>{
 const h=await boot();
 for(const [current,pages] of [[1,1],[1,3],[2,3],[11,301],[301,301],[5000,10000]]){
  h.context.current=current;h.context.pages=pages;const values=Array.from(h.run('pageNumbers(current,pages)'));
  assert.ok(values.length<=7);assert.equal(values[0],1);assert.equal(values.at(-1),pages);
  assert.ok(values.includes(current));assert.deepEqual(values,[...new Set(values)].sort((a,b)=>a-b));
 }
});


test('automatic refresh leaves the page-jump input intact while it has focus',async()=>{
 const h=await boot();let calls=0;h.context.fetch=async()=>{calls++;return response(overview());};
 h.context.document.activeElement={closest(){return {};}};await h.run('render({auto:true})');assert.equal(calls,0);
 h.context.document.activeElement={closest(){return null;}};await h.run('render({auto:true})');assert.equal(calls,1);
});

test('fresh launch is English even on non-English systems',async()=>{
 const h=await boot({savedLanguage:null});assert.equal(h.run('lang'),'en');assert.equal(h.context.document.documentElement.lang,'en');assert.equal(h.run("t('search')"),'Search ↗');
});

test('block reward components show zero fees and do not fabricate an underclaim split',async()=>{
 const h=await boot({savedLanguage:'en'});
 h.context.reward={allocation:'full',subsidy_reward_smw:'50.00000000',fee_reward_smw:'0.00000000',claimed_reward_smw:'50.00000000'};
 let html=h.run('rewardBreakdown(reward)');
 assert.ok(html.includes('New issuance (block)'));assert.ok(html.includes('Transaction fees (block)'));assert.ok(html.includes('>0 SMW<'));
 h.context.reward={allocation:'underclaimed',subsidy_reward_smw:null,fee_reward_smw:null,claimed_reward_smw:'49.00000000',subsidy_limit_smw:'50.00000000',transaction_fees_smw:'0.00000000',unclaimed_reward_smw:'1.00000000'};
 html=h.run('rewardBreakdown(reward)');assert.ok(html.includes('Reward not fully claimed'));assert.ok(html.includes('Unclaimed reward'));assert.ok(html.includes('>49 SMW<'));assert.ok(!html.includes('undefined'));
});

test('all 34 reward translations render with exact decimal amounts',async()=>{
 const h=await boot();h.context.reward={allocation:'full',subsidy_reward_smw:'0.00000000',fee_reward_smw:'0.00000001',claimed_reward_smw:'0.00000001'};
 for(const code of h.run('languageChoices.map(item=>item[0])')){
  h.element('language').value=code;await h.element('language').listeners.change();
  const html=h.run('rewardBreakdown(reward)');assert.ok(html.includes('0.00000001'));assert.ok(!html.includes('undefined'));
 }
});
test('invalid saved choice and blocked storage retain English fallback',async()=>{
 for(const options of [{savedLanguage:'invalid'},{blockedStorage:true,savedLanguage:null}]){const h=await boot(options);assert.equal(h.run('lang'),'en');}
});
test('explicit saved language is restored and all 34 choices preserve identifiers',async()=>{
 const h=await boot({savedLanguage:'de'});assert.equal(h.run('lang'),'de');
 const choices=h.run('languageChoices.map(item=>item[0])');assert.equal(choices.length,34);
 for(const code of choices){h.element('language').value=code;await h.element('language').listeners.change();assert.equal(h.context.document.documentElement.lang,code);assert.equal(h.run("money('123.00000001')"),'123.00000001');}
});
