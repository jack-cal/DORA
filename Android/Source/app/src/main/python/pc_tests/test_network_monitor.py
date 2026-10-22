"""Independent on-wire observation, grouped identities and lifecycle checks."""
import asyncio,json,tempfile,time,unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from sumuww.network_monitor import NetworkSurvey,inspect_node,ACTIVE_SECONDS
from sumuww.peer import PeerNode


class NetworkMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='sumuww-network-survey-')
        self.directory=Path(self.temp.name);self.nodes=[]
        self.loop_errors=[]
        asyncio.get_running_loop().set_exception_handler(lambda loop,context:self.loop_errors.append(context))
    async def asyncTearDown(self):
        # Let observer EOF/accept callbacks settle before closing the fixture
        # listeners; also fail if a loop callback raised outside an assertion.
        deadline=time.monotonic()+2
        await asyncio.sleep(.05)
        while any(node._sessions for node in self.nodes) and time.monotonic()<deadline:
            await asyncio.sleep(.02)
        for node in reversed(self.nodes):await node.stop()
        await asyncio.sleep(0)
        self.temp.cleanup()
        self.assertFalse(self.loop_errors,self.loop_errors)
    async def node(self,network='regtest',**options):
        node=PeerNode(self.directory/f'{len(self.nodes)}.sqlite',network=network,host=options.pop('host','127.0.0.1'),port=0,
                      timeout=1,poll_interval=.03,discovery_scope='loopback',**options)
        self.nodes.append(node);await node.start();return node
    async def test_direct_peer_response_and_block_body_without_miner_rpc_or_wallet(self):
        node=await self.node()
        row=await inspect_node(node.address,network='regtest',scope='loopback',timeout=2)
        self.assertTrue(row['responding']);self.assertEqual(row['peer_id'],f'{node.nonce:016x}')
        self.assertEqual(row['height'],0);self.assertTrue(row['tip_pow_merkle_checked'])
        self.assertEqual(row['tip'],node.chain.info()['tip'])
        self.assertTrue(node.running)
        self.assertFalse(list(self.directory.glob('wallet*')))
    async def test_foreign_network_is_not_a_working_sumuww_node(self):
        node=await self.node(network='retarget-lab')
        row=await inspect_node(node.address,network='regtest',scope='loopback',timeout=1)
        self.assertFalse(row['responding']);self.assertIsNone(row['peer_id'])
    async def test_p2p_contacts_extend_discovery_beyond_initial_node(self):
        a=await self.node();b=await self.node(peers=[a.address])
        deadline=time.monotonic()+3
        while not a.synchronization_info()['mining_ready']:
            if time.monotonic()>deadline:self.fail('Peer fixture synchronization')
            await asyncio.sleep(.02)
        a._addresses.verified(b.address)
        row=await inspect_node(a.address,network='regtest',scope='loopback',timeout=2)
        self.assertIn(b.address,row['contacts'])
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',initial=[a.address],discover=False,listen=False)
        survey.start()
        try:
            await self.wait_for(lambda:b.address in survey.contacts)
        finally:await self.stop(survey)
    async def test_same_node_aliases_group_once_failed_and_expired_observations_do_not_count(self):
        node=await self.node()
        row=await inspect_node(node.address,network='regtest',scope='loopback',timeout=2)
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',discover=False)
        aliases=[node.address,('127.0.0.2',node.address[1])]
        for target in aliases:
            survey.add(target,'test');survey.observations[target]={**row,'seen':time.time(),'tip_updates':0,'aliases':set(aliases)}
            survey.connections[id(target)]=SimpleNamespace(ready=True,row=survey.observations[target],target=target)
        survey._publish();value=survey.snapshot()
        self.assertEqual(len(value['nodes']),1);self.assertEqual(len(value['nodes'][0]['addresses']),2)
        survey.failures[aliases[0]]='Connection failed';survey.connections[id(aliases[0])].ready=False;survey._publish()
        self.assertEqual(len(survey.snapshot()['nodes']),1)
        survey.observations[aliases[1]]['seen']-=ACTIVE_SECONDS+1;survey._publish()
        self.assertEqual(survey.snapshot()['nodes'],[])

    async def wait_for(self,predicate,seconds=8):
        deadline=time.monotonic()+seconds
        while not predicate():
            if time.monotonic()>deadline:self.fail('Observer fixture deadline')
            await asyncio.sleep(.03)

    async def stop(self,survey):
        survey.stop()
        await self.wait_for(lambda:survey.stopped)

    async def test_full_peer_stays_visible_without_opening_repeated_query_connections(self):
        node=await self.node(max_peers=1)
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',initial=[node.address],discover=False,listen=False)
        survey.start()
        try:
            await self.wait_for(lambda:bool(survey.snapshot()['nodes']))
            rejected=await inspect_node(node.address,network='regtest',scope='loopback',timeout=1)
            self.assertFalse(rejected['responding'])
            await asyncio.sleep(1.5)
            self.assertEqual(len(survey.snapshot()['nodes']),1)
            self.assertEqual(node.info()['active_connections'],1)
            from sumuww.wallet import RegtestKey
            node.chain.mine(RegtestKey.from_int(1).script_pubkey,1)
            await self.wait_for(lambda:survey.snapshot()['nodes'][0]['height']==1)
            self.assertEqual(survey.snapshot()['nodes'][0]['tip_updates'],1)
            await node.stop()
            await self.wait_for(lambda:not survey.snapshot()['nodes'])
            self.assertTrue(survey.snapshot()['history'])
        finally:await self.stop(survey)

    async def test_outgoing_only_peer_is_observed_through_observer_listener(self):
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',discover=False,
                             listen_host='127.0.0.1',listen_port=0)
        survey.start()
        try:
            await self.wait_for(lambda:bool(survey.snapshot().get('listeners')))
            listener=next(iter(survey.own_contacts))
            node=await self.node(peers=[listener],max_peers=1)
            await self.wait_for(lambda:bool(survey.snapshot()['nodes']) and survey.snapshot()['nodes'][0]['height']==0)
            row=survey.snapshot()['nodes'][0]
            self.assertEqual(row['peer_id'],f'{node.nonce:016x}')
            self.assertEqual(row['direction'],'incoming')
            self.assertTrue(row['tip_pow_merkle_checked'])
            self.assertEqual(node.info()['active_connections'],1)
            self.assertFalse(list((self.directory/'monitor').glob('*.sqlite')))
        finally:await self.stop(survey)

    async def test_failed_contacts_back_off_and_do_not_count_as_nodes(self):
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',
                             initial=[('127.0.0.1',1)],discover=False,listen=False)
        survey.start()
        try:
            await self.wait_for(lambda:bool(survey.snapshot().get('attempts')) and survey.snapshot()['attempts'][0]['error'])
            self.assertEqual(survey.snapshot()['nodes'],[])
            self.assertGreater(survey.contacts[('127.0.0.1',1)]['next'],time.monotonic()+30)
        finally:await self.stop(survey)

    async def test_persistent_observer_rejects_wrong_chain_and_keeps_searching(self):
        foreign=await self.node(network='retarget-lab')
        valid=await self.node()
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',
                             initial=[foreign.address,valid.address],discover=False,listen=False)
        survey.start()
        try:
            await self.wait_for(lambda:bool(survey.snapshot()['nodes']) and bool(survey.snapshot()['errors']))
            self.assertEqual([row['peer_id'] for row in survey.snapshot()['nodes']],[f'{valid.nonce:016x}'])
            self.assertIn(survey.snapshot()['attempts'][0]['error'],('Wrong network','Network magic mismatch'))
        finally:await self.stop(survey)

    async def test_real_alias_connections_group_and_keep_existing_peer(self):
        node=await self.node(host='0.0.0.0',allow_lan=True,allow_internet=True,dht_enabled=False)
        aliases=[('127.0.0.1',node.address[1]),('127.0.0.2',node.address[1])]
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',
                             initial=aliases,discover=False,listen=False)
        survey.start()
        try:
            await self.wait_for(lambda:bool(survey.snapshot()['nodes']) and len(survey.snapshot()['nodes'][0]['addresses'])==2)
            self.assertEqual(len(survey.snapshot()['nodes']),1)
            self.assertEqual(node.info()['peers'],1)
            self.assertEqual(survey.snapshot()['nodes'][0]['peer_id'],f'{node.nonce:016x}')
        finally:await self.stop(survey)
    async def test_cancellation_closes_observer_without_stopping_remote_node(self):
        node=await self.node()
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',initial=[node.address],discover=False)
        survey.start();deadline=time.monotonic()+4
        while not survey.snapshot()['nodes']:
            if time.monotonic()>deadline:self.fail('Observer fixture deadline')
            await asyncio.sleep(.05)
        survey.stop();deadline=time.monotonic()+3
        while not survey.stopped:
            if time.monotonic()>deadline:self.fail('Observer stop deadline')
            await asyncio.sleep(.05)
        self.assertTrue(node.running)
        files={p.name for p in (self.directory/'monitor').iterdir()}
        self.assertEqual(files,{'network-contacts.json'})

    async def test_monitor_can_observe_more_than_eight_distinct_nodes(self):
        nodes=[await self.node() for _ in range(9)]
        survey=NetworkSurvey(self.directory/'monitor',network='regtest',scope='loopback',
                             initial=[node.address for node in nodes],discover=False)
        survey.start()
        try:
            deadline=time.monotonic()+12
            while len(survey.snapshot()['nodes'])<9:
                if time.monotonic()>deadline:self.fail('Nine independent responder deadline')
                await asyncio.sleep(.05)
            self.assertEqual(len(survey.snapshot()['nodes']),9)
            self.assertEqual({row['peer_id'] for row in survey.snapshot()['nodes']},{f'{node.nonce:016x}' for node in nodes})
        finally:
            survey.stop()
            while not survey.stopped:await asyncio.sleep(.01)


if __name__=='__main__':unittest.main()
