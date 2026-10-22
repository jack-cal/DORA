import asyncio,json,tempfile,time
from pathlib import Path
from sumuww.app_service import AppService
from sumuww.profiles import get_network
from sumuww import keystore
import pc_runtime
keystore._publish_no_replace=pc_runtime._publish_android
config=json.loads(Path(config_path).read_text())
async def exercise():
    report={'scope':'Android 0.6.26 emulator and eight actual frozen Windows PC 0.51 daemons; isolated regtest; ADB TCP tunnels','cases':[]}
    async def control(op,**args):
        reader,writer=await asyncio.open_connection('127.0.0.1',config['control'])
        writer.write((json.dumps({'op':op,**args})+'\n').encode());await writer.drain()
        value=json.loads(await asyncio.wait_for(reader.readline(),30));writer.close();await writer.wait_closed()
        assert 'error' not in value,value
        return value
    with tempfile.TemporaryDirectory(prefix='owned-mixed-android-') as tmp:
        folder=Path(tmp);manifest=folder/'bootstrap.json'
        manifest.write_text(json.dumps({'schema_version':2,'network':'regtest',
            'genesis':get_network('regtest').genesis.block_hash().hex(),'dns_seeds':[],
            'fallback_peers':[{'host':'127.0.0.1','port':config['ports'][0]}]}))
        service=AppService(folder/'android',network='regtest',listen='127.0.0.1:0',peers=[],
            allow_lan=False,allow_internet=True,auto_address=False,
            bootstrap_scope='loopback',bootstrap_manifest=manifest)
        async def status():return await asyncio.to_thread(service.status().result,30)
        async def identities():
            async def read():return [s.nonce for s in service._node._sessions.values() if s.ready and not s.writer.is_closing()]
            return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(read(),service._loop))
        async def wait(check,label,seconds=45):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                value=await status()
                if check(value):return value
                await asyncio.sleep(.2)
            raise AssertionError(label+': '+json.dumps(value['node']))
        try:
            await asyncio.to_thread(service.start().result,30)
            pc_runtime._service=service;pc_runtime._runtime_state='running'
            first=await wait(lambda v:v['node']['peers']>=2 and v['node']['mining_ready'] and v['node']['height']==3,'discover PC peers')
            report['cases'].append({'case':'one_PC_seed_discovers_another_PC_and_receives_three_blocks','passed':True,'connected':first['node']['peers'],'candidates':first['node']['peer_discovery']['candidates']})
            for port in config['ports']:await asyncio.to_thread(pc_runtime.add_peer,f'127.0.0.1:{port}')
            full=await wait(lambda v:v['node']['peers']==8 and v['node']['mining_ready'],'eight frozen PCs')
            assert len(set(await identities()))==8
            report['cases'].append({'case':'eight_distinct_frozen_PCs_connected','passed':True})
            await asyncio.to_thread(service.create_wallet(folder/'fixture-wallet.json','Owned-mixed-test-only').result,30)
            await asyncio.to_thread(service.mine_one().result,45)
            await wait(lambda v:v['node']['height']==4 and v['node']['mining_ready'],'Android block accepted locally')
            end=time.monotonic()+30
            while time.monotonic()<end:
                remote=await control('state')
                if all(n['height']==4 for n in remote['nodes']):break
                await asyncio.sleep(.25)
            else:raise AssertionError('Android block not received by all frozen PCs')
            report['cases'].append({'case':'Android_mines_block_and_all_eight_PCs_validate_it','passed':True,'height':4})
            await control('stop')
            await wait(lambda v:v['node']['peers']==7 and v['node']['mining_ready'],'PC loss')
            samples=[]
            for _ in range(10):
                node=(await status())['node'];unique=len(set(await identities()))
                samples.append({'peers':node['peers'],'unique':unique,'ready':node['mining_ready']})
                await asyncio.sleep(.5)
            assert all(s['peers']==s['unique']==7 and s['ready'] for s in samples),samples
            report['cases'].append({'case':'one_frozen_PC_stops_seven_remain_without_duplicates','passed':True,'samples':samples})
            await control('restart')
            await wait(lambda v:v['node']['peers']==8 and v['node']['mining_ready'],'frozen PC restart',60)
            assert len(set(await identities()))==8
            report['cases'].append({'case':'restarted_frozen_PC_automatically_reconnects','passed':True})
            await control('stop')
            current=await wait(lambda v:v['node']['peers']==7 and v['node']['mining_ready'],'make room for inbound PC')
            await control('incoming',port=current['node']['listen']['port'])
            inbound=await wait(lambda v:v['node']['peers']==8 and v['node']['mining_ready'] and any(c['direction']=='incoming' for c in v['node']['peer_connections']),'PC-originated inbound connection',60)
            assert len(set(await identities()))==8
            end=time.monotonic()+30
            while time.monotonic()<end:
                remote=await control('state')
                if next(n for n in remote['nodes'] if n['index']==8)['height']==4:break
                await asyncio.sleep(.25)
            else:raise AssertionError('Inbound PC did not synchronize from Android')
            report['cases'].append({'case':'new_PC_dials_Android_and_synchronizes','passed':True,'incoming':sum(c['direction']=='incoming' for c in inbound['node']['peer_connections'])})
            report['passed']=True;return report
        finally:
            await asyncio.to_thread(service.stop().result,60)
            pc_runtime._service=None;pc_runtime._runtime_state='stopped'
            await control('finish')
report=json.dumps(asyncio.run(exercise()))


