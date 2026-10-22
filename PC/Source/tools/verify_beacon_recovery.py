"""Owned local TCP processes: withheld DKG, complete old-group loss and late sync.

Uses fresh regtest databases only. Timing overrides shorten local liveness
checks, not consensus spacing, witness selection or proof probability.
"""
import argparse
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


async def worker(args):
    from sumuww.peer import PeerNode
    from sumuww.chain import Chain
    from sumuww.wallet import RegtestKey
    from sumuww.link_crypto import digest
    db=Path(args.work)/f'node-{args.index}.sqlite'
    node=PeerNode(db,boundary_activation=3,peers=[('127.0.0.1',args.peer)] if args.peer else [],
                  discover_peers=False,dht_enabled=False,auto_address=False,poll_interval=.1,timeout=30)
    r=None
    stop=asyncio.Event()
    def mine(count):
        with Chain(db,boundary_activation=3) as c:
            c.mine(RegtestKey.from_int(81000+args.index).script_pubkey,count)
    def status():
        c=node.chain;path=c._path(c.tip_hash);anchor=c.boundary.anchor(path);prepared=c.boundary.prepared_setup(path)
        return {'height':path[-1][0][2],'tip':c.tip_hash.hex(),'utxo':c.state_commitment(),
                'id':r.keys.node_id,'contacts':len(r.contacts),'pending':len(r.jobs),
                'proofs':sorted(digest(p) for p in c.boundary.all_proofs()),
                'anchor':anchor[0].hex() if anchor else None,
                'members':sorted(m['payload']['nodeId'] for m in anchor[1]['manifest']['context']['members']) if anchor else [],
                'prepared':digest(prepared['manifest']) if prepared else None,
                'prepared_members':sorted(m['payload']['nodeId'] for m in prepared['manifest']['context']['members']) if prepared else [],
                'recovery':r.recovery.info(),'error':r.last_error,'peer_error':str(node._last_error)}
    async def control(reader,writer):
        try:
            cmd=json.loads(await reader.readline());name=cmd['command']
            if name=='status':value=status()
            elif name=='enable':r.started=0;r.recovery.next_check=0;value=status()
            elif name=='mine':
                before=time.monotonic();await asyncio.to_thread(mine,cmd.get('count',1));value={'seconds':time.monotonic()-before,**status()}
            elif name=='fault':
                for option,attr in [('beacon','omit_beacon'),('dkg','omit_dkg'),('probe','omit_dkg_probe'),('delay','signature_delay')]:
                    if option in cmd:setattr(r,attr,cmd[option])
                r.recovery.next_check=0;value=status()
            elif name=='verify':
                c=node.chain;c.boundary.verify_storage();value={'integrity':c.connection.execute('PRAGMA integrity_check').fetchone()[0],**status()}
            elif name=='stop':value={'stopping':True};stop.set()
            else:raise ValueError(name)
            writer.write(json.dumps({'ok':True,'value':value}).encode()+b'\n');await writer.drain()
        except Exception as e:
            writer.write(json.dumps({'ok':False,'error':repr(e)}).encode()+b'\n');await writer.drain()
        finally:writer.close();await writer.wait_closed()
    server=None
    try:
        await node.start();r=node.boundary_runtime;r.started=time.monotonic()+3600
        r.recovery.interval=3;r.recovery.request_timeout=5;r.recovery.setup_timeout=45;r.recovery.cooldown=90
        server=await asyncio.start_server(control,'127.0.0.1',0)
        (Path(args.work)/f'ready-{args.index}.json').write_text(json.dumps({'control':server.sockets[0].getsockname()[1],'peer':node.address[1]}))
        await stop.wait()
    finally:
        if server:server.close();await server.wait_closed()
        await node.stop()


async def orchestrate(args):
    root=Path(args.work).resolve();root.mkdir(parents=True,exist_ok=False)
    nodes={};processes={};logs=[];events=[]
    async def call(i,command,**kw):
        reader,writer=await asyncio.open_connection('127.0.0.1',nodes[i]['control'])
        try:
            writer.write(json.dumps({'command':command,**kw}).encode()+b'\n');await writer.drain()
            answer=json.loads(await asyncio.wait_for(reader.readline(),120));assert answer['ok'],answer
            return answer['value']
        finally:writer.close();await writer.wait_closed()
    async def states():return await asyncio.gather(*(call(i,'status') for i in nodes))
    def record(name,**kw):
        row={'name':name,**kw};events.append(row)
        (root/'progress.json').write_text(json.dumps(events,indent=2));print(json.dumps(row),flush=True)
    async def until(predicate,label,timeout=180):
        deadline=time.monotonic()+timeout;last=None
        while time.monotonic()<deadline:
            last=await states()
            if predicate(last):return last
            await asyncio.sleep(.5)
        raise AssertionError(label+': '+json.dumps(last))
    async def start(i,peer=None):
        ready=root/f'ready-{i}.json'
        if ready.exists():ready.unlink()
        log=(root/f'node-{i}.log').open('a',encoding='utf-8');logs.append(log)
        cmd=[sys.executable,'-u',__file__,'--worker','--work',str(root),'--index',str(i)]
        if peer is not None:cmd+=['--peer',str(nodes[peer]['peer'])]
        p=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT);processes[i]=p
        deadline=time.monotonic()+60
        while not ready.exists():
            assert p.poll() is None,(root/f'node-{i}.log').read_text()
            assert time.monotonic()<deadline,'startup timeout'
            await asyncio.sleep(.2)
        nodes[i]=json.loads(ready.read_text())
    async def stop(i):
        await call(i,'stop');await asyncio.to_thread(processes[i].wait,timeout=30);del nodes[i]
    async def mine(i,count=1):
        result=await call(i,'mine',count=count)
        await until(lambda s:len({x['tip'] for x in s})==1 and min(x['height'] for x in s)>=result['height'],'tip sync')
        return result
    async def proofs_after(i,baseline):
        for attempt in range(100):
            await mine(i,2)
            await asyncio.sleep(1)
            values=await states()
            if all(set(x['proofs'])-baseline for x in values):return values
        return await until(lambda s:all(set(x['proofs'])-baseline for x in s),'new proof',timeout=180)
    try:
        for i in range(4):await start(i,i-1 if i else None)
        await until(lambda s:all(x['contacts']==4 for x in s),'initial discovery')
        await call(3,'fault',dkg=True)
        await mine(0,2)
        for i in nodes:await call(i,'enable')
        # First attempt includes the fourth contact. It acknowledges probes
        # but selectively withholds its encrypted DKG contribution.
        await until(lambda s:any(x['recovery']['attempts'] for x in s),'initial attempt')
        before=(await states())[0]['height'];advance=await mine(0,3)
        assert advance['height']==before+3
        ready=await until(lambda s:all(len(x['prepared_members'])==3 for x in s),'withheld DKG recovery',timeout=240)
        withheld=(await call(3,'status'))['id']
        assert all(withheld not in x['prepared_members'] for x in ready)
        assert any(x['recovery']['timed_out_setups'] for x in ready)
        record('selective_dkg_withholding_recovered',participants=3,discovered=4,mining_advanced=3,seconds=advance['seconds'])
        await mine(0)
        first=(await states())[0]['anchor'];assert first
        initial=await proofs_after(0,set());old_proofs=set(initial[0]['proofs'])
        record('initial_generation_proofs',proofs=len(old_proofs),anchor=first)
        for i in range(4,7):await start(i,i-1 if i>4 else 0)
        await until(lambda s:all(x['contacts']==7 for x in s),'transitive seven-node discovery')
        for i in range(4):await call(i,'fault',beacon=True,probe=True)
        for i in range(4,7):await call(i,'enable')
        await mine(4,12)
        # Witness latency must not become a wait on the next block.
        for i in nodes:await call(i,'fault',delay=8)
        advance=await mine(4,5)
        assert advance['seconds']<8,advance
        record('mining_during_old_beacon_loss_and_delayed_signatures',blocks=5,seconds=advance['seconds'])
        for i in nodes:await call(i,'fault',delay=0)
        # Unmined proposals can legitimately differ. Agreement is required on
        # the generation committed to the selected PoW branch, checked below.
        fresh_ids={(await call(i,'status'))['id'] for i in range(4,7)}
        # Membership can change while new nodes arrive. Keep ordinary PoW
        # progressing through the spacing of any intermediate generation.
        for _ in range(120):
            ready=await states()
            if set(ready[4]['prepared_members'])==fresh_ids or set(ready[4]['members'])==fresh_ids:break
            await mine(4);await asyncio.sleep(1)
        else:raise AssertionError('Replacement was not prepared while PoW progressed: '+json.dumps(ready))
        record('replacement_prepared',participants=3,nodes=len(ready))
        await mine(4)
        values=await until(lambda s:len({x['anchor'] for x in s})==1 and all(set(x['members'])==fresh_ids for x in s),'anchored generation convergence')
        second=values[0]['anchor']
        baseline=set().union(*(set(x['proofs']) for x in values))
        values=await proofs_after(4,baseline)
        record('new_proofs_with_all_old_beacon_shares_withheld',anchor=second,proofs=len(values[0]['proofs']))
        for i in range(4):await stop(i)
        await mine(4,3)
        record('old_processes_stopped',remaining_nodes=len(nodes))
        await stop(6);await start(6,4)
        await until(lambda s:len({x['tip'] for x in s})==1,'replacement restart sync')
        await start(7,4)
        values=await until(lambda s:len({x['tip'] for x in s})==1 and len({tuple(x['proofs']) for x in s})==1 and all(old_proofs<=set(x['proofs']) for x in s),'late node full history',timeout=300)
        checks=await asyncio.gather(*(call(i,'verify') for i in nodes))
        assert all(x['integrity']=='ok' and x['anchor']==second for x in checks)
        assert len({x['utxo'] for x in checks})==1
        record('late_node_and_restart_verify_both_generations',nodes=len(checks),proofs=len(checks[0]['proofs']),height=checks[0]['height'])
        report={'status':'passed','network':'local-isolated-regtest','distinct_process_identities':8,'events':events,'nodes':checks}
        (root/'result.json').write_text(json.dumps(report,indent=2));print(json.dumps({'status':'passed'}),flush=True)
    finally:
        for i in list(nodes):
            try:await call(i,'stop')
            except Exception:pass
        for p in processes.values():
            try:await asyncio.to_thread(p.wait,timeout=20)
            except subprocess.TimeoutExpired:p.terminate();await asyncio.to_thread(p.wait,timeout=10)
        for log in logs:log.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--work',required=True);parser.add_argument('--worker',action='store_true')
    parser.add_argument('--index',type=int,default=0);parser.add_argument('--peer',type=int,default=0)
    options=parser.parse_args();asyncio.run(worker(options) if options.worker else orchestrate(options))
