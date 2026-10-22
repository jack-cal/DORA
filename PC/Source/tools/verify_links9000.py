"""Isolated real TCP/process integration. Never opens a production wallet."""
import argparse,asyncio,json,os,pathlib,shutil,sqlite3,subprocess,sys,time
from contextlib import closing
SOURCE=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(SOURCE))

async def worker(args):
    from sumuww.peer import PeerNode
    from sumuww.chain import Chain
    from sumuww.wallet import RegtestKey
    db=pathlib.Path(args.work)/f'node-{args.index}.sqlite'
    node=PeerNode(db,boundary_activation=9000,peers=[('127.0.0.1',args.peer)] if args.peer else [],
                  discover_peers=False,dht_enabled=False,auto_address=False,poll_interval=.1,timeout=30)
    stopped=asyncio.Event()
    def mine(count):
        with Chain(db,boundary_activation=9000) as c:
            return [b.block_hash().hex() for b in c.mine(RegtestKey.from_int(40000+args.index).script_pubkey,count)]
    def status():
        from sumuww.link_crypto import digest
        r=node.boundary_runtime;c=node.chain;setup=c.boundary.local('ready_setup')
        return {'height':c._row(c.tip_hash)[2],'tip':c.tip_hash.hex(),'links':len(c.boundary.all_proofs()),
                'proof_ids':sorted(digest(p) for p in c.boundary.all_proofs()),
                'peers':len([s for s in node._sessions.values() if s.ready]),'contacts':len(r.contacts),'pending':len(r.jobs),
                'setup_members':len(setup['manifest']['context']['members']) if setup else 0,
                'error':r.last_error,'peer_error':str(node._last_error),'metrics':r.metrics}
    async def control(reader,writer):
        try:
            command=json.loads(await reader.readline());name=command['command']
            if name=='status':value=status()
            elif name=='mine':
                before=time.monotonic();blocks=await asyncio.to_thread(mine,command.get('count',1));value={'blocks':blocks,'seconds':time.monotonic()-before,**status()}
            elif name=='fault':
                r=node.boundary_runtime;r.omit_beacon=command.get('beacon',False);r.omit_witness=command.get('witness',False);r.signature_delay=command.get('delay',0);value=status()
            elif name=='disconnect':
                for s in node._sessions.values():s.writer.close()
                value={'disconnected':True}
            elif name=='stop':value={'stopping':True};stopped.set()
            else:raise ValueError('Unknown laboratory command')
            writer.write(json.dumps({'ok':True,'value':value}).encode()+b'\n');await writer.drain()
        except Exception as e:
            writer.write(json.dumps({'ok':False,'error':repr(e)}).encode()+b'\n');await writer.drain()
        finally:writer.close();await writer.wait_closed()
    server=None
    try:
        await node.start();server=await asyncio.start_server(control,'127.0.0.1',0)
        ready={'control':server.sockets[0].getsockname()[1],'peer':node.address[1],'pid':os.getpid()}
        (pathlib.Path(args.work)/f'ready-{args.index}.json').write_text(json.dumps(ready))
        await stopped.wait()
    finally:
        if server:server.close();await server.wait_closed()
        await node.stop()

async def orchestrate(args):
    root=pathlib.Path(args.work).resolve();root.mkdir(parents=True,exist_ok=True)
    processes=[];nodes=[];logs=[];events=[]
    async def call(index,command,**options):
        reader,writer=await asyncio.open_connection('127.0.0.1',nodes[index]['control'])
        try:
            writer.write(json.dumps({'command':command,**options}).encode()+b'\n');await writer.drain()
            reply=json.loads(await asyncio.wait_for(reader.readline(),120));assert reply['ok'],reply
            return reply['value']
        finally:writer.close();await writer.wait_closed()
    async def states():return await asyncio.gather(*(call(i,'status') for i in range(len(nodes))))
    async def wait(predicate,label,seconds=150):
        until=time.monotonic()+seconds;current=None
        while time.monotonic()<until:
            current=await states()
            if predicate(current):return current
            await asyncio.sleep(.5)
        raise AssertionError(label+': '+json.dumps(current))
    def record(name,value):
        events.append({'name':name,**value});(root/'progress.json').write_text(json.dumps(events,indent=2));print(json.dumps(events[-1]),flush=True)
    async def start(seed=True):
        i=len(nodes);db=root/f'node-{i}.sqlite'
        if seed:
            with closing(sqlite3.connect(args.seed)) as old,closing(sqlite3.connect(db)) as new:old.backup(new)
        log=open(root/f'node-{i}.log','w',encoding='utf-8');logs.append(log)
        command=[sys.executable,'-u',__file__,'--worker','--work',str(root),'--index',str(i)]
        if nodes:command+=['--peer',str(nodes[-1]['peer'])]
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT);processes.append(process)
        ready=root/f'ready-{i}.json';until=time.monotonic()+90
        while not ready.exists():
            assert process.poll() is None,(root/f'node-{i}.log').read_text()
            assert time.monotonic()<until,'Node startup timeout'
            await asyncio.sleep(.2)
        nodes.append(json.loads(ready.read_text()));return i
    async def mine(index,count=1):
        result=await call(index,'mine',count=count);height=result['height']
        await wait(lambda s:len({v['tip'] for v in s})==1 and all(v['height']>=height for v in s),'block synchronization')
        return result
    try:
        for _ in range(4):await start()
        await wait(lambda s:all(v['contacts']==4 and v['setup_members']==4 for v in s),'transitive discovery and distributed setup')
        record('preactivation_same_ip_four_nodes',{'height':8999,'nodes':4,'all_discovered':True})
        result=await mine(0);assert result['height']==9000
        record('first_new_block_is_9000',{'height':result['height']})
        for i in range(12):await mine(i%4)
        # A 20% event is probabilistic, not one mandatory proof every five
        # blocks. Extend the test history naturally when the first sample has
        # no event; do not redraw or modify production randomness.
        for i in range(80):
            if all(v['links']>=1 for v in await states()):break
            await mine(i%4)
        current=await wait(lambda s:all(v['links']>=1 for v in s),'completed paired signatures')
        record('completed_link_gossip',{'height':current[0]['height'],'proof_counts':[v['links'] for v in current]})
        await asyncio.gather(*(call(i,'fault',delay=8) for i in range(4)))
        await mine(0,2)
        current=await wait(lambda s:any(v['pending'] for v in s),'signature jobs pending')
        before=current[0]['height'];result=await mine(1,3)
        record('mining_while_signatures_delayed',{'before':before,'after':result['height'],'seconds':round(result['seconds'],3)})
        await asyncio.gather(*(call(i,'fault',beacon=True,witness=True) for i in range(4)))
        before=(await states())[0]['height'];result=await mine(2,5)
        record('all_responses_omitted',{'before':before,'after':result['height']})
        await asyncio.gather(*(call(i,'fault') for i in range(4)))
        await mine(3,2)
        await start(seed=args.late_history)
        current=await wait(lambda s:len({v['tip'] for v in s})==1 and min(v['links'] for v in s)>0 and len({tuple(v['proof_ids']) for v in s})==1 and all(v['contacts']==5 for v in s),'late full proof convergence',seconds=900)
        record('late_node_from_8999_history' if args.late_history else 'late_node_from_genesis',{'nodes':5,'height':current[-1]['height'],'proofs':current[-1]['links'],'all_proof_inventories_identical':True})
        await call(2,'disconnect')
        await wait(lambda s:all(v['peers']>=1 for v in s),'connection recovery')
        result=await mine(4,2);record('new_node_mines_after_reconnect',{'height':result['height']})
        final=await wait(lambda s:len({v['tip'] for v in s})==1 and len({tuple(v['proof_ids']) for v in s})==1,'final inventory convergence')
        report={'status':'passed','network':'isolated-regtest','steps':events,'nodes':final}
        (root/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps({'status':'passed','steps':len(events)}),flush=True)
    finally:
        for i in range(len(nodes)):
            try:await call(i,'stop')
            except Exception:pass
        for process in processes:
            try:await asyncio.to_thread(process.wait,timeout=20)
            except subprocess.TimeoutExpired:process.terminate();await asyncio.to_thread(process.wait,timeout=10)
        for log in logs:log.close()

parser=argparse.ArgumentParser();parser.add_argument('--worker',action='store_true');parser.add_argument('--work',required=True)
parser.add_argument('--late-history',action='store_true',help='Late peer starts from independently verified preactivation history')
parser.add_argument('--seed');parser.add_argument('--index',type=int,default=0);parser.add_argument('--peer',type=int,default=0)
args=parser.parse_args()
asyncio.run(worker(args) if args.worker else orchestrate(args))
