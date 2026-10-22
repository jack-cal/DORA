"""Read-only explorer analytics; observations are saved only in the explorer index."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fractions import Fraction
import json
import heapq
import math
import re
import time

from witness_address import decode_address, encode_address
from sumuww.primitives import MAX_MONEY, Header, hash_to_display, valid_target, block_work
from sumuww.difficulty import expected_bits
from sumuww.profiles import SUMUWW

FILTER_KEYS={'date_from','date_to','min_height','max_height','min_amount','max_amount','sort','order'}
BLOCK_BUDGET=3_996_000  # Reserve space for header, coinbase and commitments.

def money(value):
    return ('-' if value<0 else '')+f'{abs(value)//100000000}.{abs(value)%100000000:08d}'

def units(text):
    if not isinstance(text,str) or not re.fullmatch(r'(0|[1-9][0-9]*)(?:\.[0-9]{1,8})?',text):
        raise ValueError('Use an unsigned amount with up to eight decimal places')
    value=int(Decimal(text)*100000000)
    if value>MAX_MONEY:raise ValueError('Amount exceeds the maximum supply')
    return value

def day(text,end=False):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(text)):
        raise ValueError('Use a YYYY-MM-DD UTC date')
    value=datetime.strptime(text,'%Y-%m-%d').replace(tzinfo=timezone.utc)
    if end:value+=timedelta(days=1)
    return int(value.timestamp())

def rate(fee,vsize):
    return format(Decimal(fee)/Decimal(vsize),'.8f') if fee is not None and vsize else None

def checked_filters(filters):
    filters=dict(filters or {})
    if set(filters)-FILTER_KEYS:raise ValueError('Unknown transaction filter')
    result={k:v for k,v in filters.items() if v!=''}
    for key in ('min_height','max_height'):
        if key in result:
            if not re.fullmatch(r'[0-9]{1,10}',str(result[key])):raise ValueError('Invalid block-height filter')
            result[key]=int(result[key])
            if result[key]>0x7fffffff:raise ValueError('Block height is outside the supported range')
    for key in ('min_amount','max_amount'):
        if key in result:result[key]=units(result[key])
    for key in ('date_from','date_to'):
        if key in result:result[key]=day(result[key],key=='date_to')
    for a,b in [('min_height','max_height'),('min_amount','max_amount')]:
        if a in result and b in result and result[a]>result[b]:raise ValueError('Minimum exceeds maximum')
    if 'date_from' in result and 'date_to' in result and result['date_from']>=result['date_to']:
        raise ValueError('Start date exceeds end date')
    if result.get('sort','height') not in ('height','time','amount','fee','rate'):raise ValueError('Unknown sort field')
    if result.get('order','desc') not in ('asc','desc'):raise ValueError('Unknown sort direction')
    return result

FINANCIAL_CTE='''WITH totals AS (SELECT txid,sum(value) output_units FROM outputs GROUP BY txid),
 spending AS (SELECT i.txid,sum(o.value) input_units,count(*) n,count(o.value) resolved
 FROM inputs i LEFT JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n GROUP BY i.txid),
 history AS (SELECT t.*,b.height,b.timestamp,totals.output_units,
 CASE WHEN t.coinbase=0 AND spending.n=spending.resolved THEN spending.input_units-totals.output_units END fee_units,
 CAST((t.weight+3)/4 AS INTEGER) vsize FROM txs t JOIN blocks b ON b.hash=t.blockhash
 JOIN totals ON totals.txid=t.txid LEFT JOIN spending ON spending.txid=t.txid) '''

class AdvancedExplorer:
    def financials(self,c,txid,coinbase=False):
        row=c.execute('''SELECT count(*) n,count(o.value) resolved,coalesce(sum(o.value),0) amount
          FROM inputs i LEFT JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n WHERE i.txid=?''',(txid,)).fetchone()
        total=c.execute('SELECT coalesce(sum(value),0) FROM outputs WHERE txid=?',(txid,)).fetchone()[0]
        fee=row['amount']-total if not coinbase and row['n'] and row['n']==row['resolved'] else None
        return fee if fee is None or fee>=0 else None

    def filtered_transactions(self,c,kind='ordinary',offset=0,filters=None,limit=25):
        if kind not in ('all','ordinary','coinbase'):raise ValueError('Unknown transaction kind')
        if type(offset) is not int or not 0<=offset<=1000000:raise ValueError('Invalid offset')
        if type(limit) is not int or not 1<=limit<=10000:raise ValueError('Invalid limit')
        f=checked_filters(filters);where=[];args=[]
        if kind!='all':where.append('coinbase=?');args.append(int(kind=='coinbase'))
        for key,column,operator in [('min_height','height','>='),('max_height','height','<='),
          ('date_from','timestamp','>='),('date_to','timestamp','<'),('min_amount','output_units','>='),('max_amount','output_units','<=')]:
            if key in f:where.append(column+operator+'?');args.append(f[key])
        clause=' WHERE '+' AND '.join(where) if where else ''
        sort={'height':'height','time':'timestamp','amount':'output_units','fee':'fee_units','rate':'CAST(fee_units AS REAL)/vsize'}[f.get('sort','height')]
        order=f.get('order','desc').upper()
        total=c.execute(FINANCIAL_CTE+'SELECT count(*) FROM history'+clause,args).fetchone()[0]
        rows=c.execute(FINANCIAL_CTE+'SELECT * FROM history'+clause+
            f' ORDER BY ({sort}) IS NULL,({sort}) {order},height {order},position {order},txid {order} LIMIT ? OFFSET ?',args+[limit,offset])
        height=self.tip_height(c);items=[]
        for row in rows:
            value=dict(row);fee=value.pop('fee_units');output=value.pop('output_units')
            value.update(output_total=money(output),fee=money(fee) if fee is not None else None,
                         fee_rate=rate(fee,row['vsize']),confirmations=height-row['height']+1)
            items.append(value)
        return {'kind':kind,'offset':offset,'total':total,'transactions':items,'filters':dict(filters or {}),'limit':limit}

    def pool_model(self,c,pool=None,coins=None):
        pool=self.pool if pool is None else pool
        records={};parents={};children=defaultdict(set)
        for txid,tx in pool.items():
            resolved=True;input_total=0;dependencies=set()
            for item in tx.inputs:
                parentid=hash_to_display(item.prev_txid)
                if parentid in pool:
                    dependencies.add(parentid)
                    output=pool[parentid].outputs[item.prev_index] if item.prev_index<len(pool[parentid].outputs) else None
                    value=output.value if output is not None else None
                else:
                    row=c.execute('SELECT value FROM outputs WHERE txid=? AND n=?',(parentid,item.prev_index)).fetchone()
                    value=row[0] if row is not None else None
                if value is None:resolved=False
                else:input_total+=value
            fee=input_total-sum(output.value for output in tx.outputs) if resolved else None
            if fee is not None and fee<0:fee=None
            parents[txid]=dependencies
            for parent in dependencies:children[parent].add(txid)
            vsize=(tx.weight()+3)//4
            records[txid]={'txid':txid,'fee_units':fee,'fee':money(fee) if fee is not None else None,
                'vsize':vsize,'weight':tx.weight(),'fee_rate':rate(fee,vsize),'parents':sorted(dependencies),
                'output_total':money(sum(output.value for output in tx.outputs)),
                'rbf_signal':any(item.sequence<0xfffffffe for item in tx.inputs)}
        def reach(start,graph):
            seen=set();pending=list(graph.get(start,()))
            while pending:
                current=pending.pop()
                if current in seen:continue
                seen.add(current);pending.extend(graph.get(current,()))
            return seen
        for txid,item in records.items():
            ancestors=reach(txid,parents);descendants=reach(txid,children);cyclic=txid in ancestors
            package=ancestors|{txid}
            fee=sum(records[x]['fee_units'] or 0 for x in package)
            complete=not cyclic and all(records[x]['fee_units'] is not None for x in package)
            vsize=sum(records[x]['vsize'] for x in package)
            item.update(ancestors=sorted(ancestors-{txid}),descendants=sorted(descendants-{txid}),cyclic=cyclic,
                package_fee=money(fee) if complete else None,package_fee_units=fee if complete else None,
                package_vsize=vsize,effective_fee_rate=rate(fee,vsize) if complete else None)
        return records

    def projected_transactions(self,model):
        selected=[];chosen=set();weight=0;heap=[];packages={};order={key:i for i,key in enumerate(model)}
        def enqueue(key):
            package=packages[key];members=package['members']
            fee=sum(model[x]['fee_units'] for x in members);size=sum(model[x]['vsize'] for x in members)
            heapq.heappush(heap,(-Fraction(fee,size),order[key],key,package['version']))
        for key,item in model.items():
            if item['package_fee_units'] is None:continue
            packages[key]={'members':set(item['ancestors'])|{key},'version':0};enqueue(key)
        while heap:
            _,_,key,version=heapq.heappop(heap)
            if key in chosen or version!=packages[key]['version']:continue
            members=packages[key]['members'];w=sum(model[x]['weight'] for x in members)
            if weight+w>BLOCK_BUDGET:continue
            added=sorted(members,key=lambda x:(len(model[x]['ancestors']),order[x]))
            selected.extend(added);chosen.update(added);weight+=w
            affected=set()
            for added_key in added:affected.update(model[added_key]['descendants'])
            for child in affected-chosen:
                if child in packages:
                    package=packages[child];package['members']-=chosen;package['version']+=1;enqueue(child)
        return selected,weight

    def record_observation(self,c,path,pool,coins,tip):
        if not path and tip==self.tip and pool==self.pool and coins==self.coins and c.execute('SELECT 1 FROM observations WHERE parent=?',(tip,)).fetchone():
            return
        # Only observations actually made before receipt are used for comparisons.
        for row in path:
            blockhash=hash_to_display(row[0]);parent=hash_to_display(row[1])
            observation=c.execute('SELECT observed_at,txids,template FROM observations WHERE parent=?',(parent,)).fetchone()
            if observation is None:continue
            actual=[r[0] for r in c.execute('SELECT txid FROM txs WHERE blockhash=? AND coinbase=0 ORDER BY position',(blockhash,))]
            expected=json.loads(observation['template']);observed=json.loads(observation['txids'])
            c.execute('INSERT OR REPLACE INTO block_audits VALUES (?,?,?,?,?,?)',
                (blockhash,observation['observed_at'],json.dumps(expected),json.dumps(actual),json.dumps(observed),time.time()))
        model=self.pool_model(c,pool,coins);projected,_=self.projected_transactions(model)
        old=c.execute('SELECT txids,template FROM observations WHERE parent=?',(tip,)).fetchone()
        txids,template=json.dumps(list(pool)),json.dumps(projected)
        if old is None or (old['txids'],old['template'])!=(txids,template):
            c.execute('INSERT OR REPLACE INTO observations VALUES (?,?,?,?)',
                (tip,time.time(),txids,template))

    def fee_analysis(self,c):
        model=self.pool_model(c);projected,weight=self.projected_transactions(model)
        known=[item for item in model.values() if item['fee_units'] is not None]
        buckets=[{'minimum':str(low),'maximum':str(high) if high is not None else None,'count':0,'vsize':0}
                 for low,high in [(0,1),(1,2),(2,5),(5,10),(10,20),(20,50),(50,100),(100,None)]]
        for item in known:
            value=Fraction(item['fee_units'],item['vsize'])
            for bucket in buckets:
                if value>=Decimal(bucket['minimum']) and (bucket['maximum'] is None or value<Decimal(bucket['maximum'])):
                    bucket['count']+=1;bucket['vsize']+=item['vsize'];break
        recent=c.execute(FINANCIAL_CTE+'SELECT fee_units,vsize FROM history WHERE coinbase=0 AND fee_units>=0 ORDER BY height DESC,position DESC LIMIT 200').fetchall()
        samples=sorted([Fraction(item['fee_units'],item['vsize']) for item in known]+[Fraction(row[0],row[1]) for row in recent])
        congested=sum(item['weight'] for item in model.values())>BLOCK_BUDGET
        recommendations=[]
        for name,percentile in [('economy',.25),('normal',.5),('priority',.9)]:
            value=samples[min(len(samples)-1,int((len(samples)-1)*percentile))] if samples else None
            if congested and projected:
                cutoff=min(Fraction(model[key]['package_fee_units'],model[key]['package_vsize']) for key in projected)
                if value is not None:value=max(value,cutoff)
            recommendations.append({'level':name,'fee_rate':rate(value.numerator,value.denominator) if value is not None else None})
        ordered=sorted(model.values(),key=lambda item:-(float(item['effective_fee_rate']) if item['effective_fee_rate'] is not None else -1))
        return {'total':len(model),'known_fees':len(known),'unresolved_fees':len(model)-len(known),
            'vsize':sum(item['vsize'] for item in model.values()),'weight':sum(item['weight'] for item in model.values()),
            'total_known_fees':money(sum(item['fee_units'] for item in known)),'buckets':buckets,
            'recommendations':recommendations,'sample_count':len(samples),'congested':congested,
            'projected':projected,'projected_weight':weight,'transactions':[{k:v for k,v in item.items() if k not in ('fee_units','package_fee_units')} for item in ordered],
            'scope':'local_pool_and_recent_confirmed_samples','fee_unit':'smallest_unit/vB','minimum_unit_per_SMW':100000000,
            'estimate_only':True,'zero_fee_valid':True,'selection':'ancestor-package rate, FIFO ties; conservative weight reserve; not a node template or consensus validation'}

    def related(self,c,txid):
        detail=self.transaction(c,txid);txid=detail['txid']
        direct_parents=sorted({item['previous'] for item in detail['inputs']})
        confirmed_children=[row[0] for row in c.execute('SELECT DISTINCT txid FROM inputs WHERE previous=?',(txid,))]
        model=self.pool_model(c);item=model.get(txid)
        pool_children=sorted(key for key,value in model.items() if txid in value['parents'])
        return {'txid':txid,'parents':direct_parents,'children':sorted(set(confirmed_children+pool_children)),
            'pending_ancestors':item['ancestors'] if item else [],'pending_descendants':item['descendants'] if item else [],
            'package_fee':item['package_fee'] if item else detail.get('fee'),'package_vsize':item['package_vsize'] if item else detail.get('vsize'),
            'effective_fee_rate':item['effective_fee_rate'] if item else detail.get('fee_rate'),
            'rbf_signal':item['rbf_signal'] if item else None,'replacement_policy_verified':False}

    def mining_analysis(self,c,limit=144):
        if type(limit) is not int or not 2<=limit<=2016:raise ValueError('Mining sample must be between 2 and 2016 blocks')
        rows=c.execute('SELECT * FROM blocks ORDER BY height DESC LIMIT ?',(limit,)).fetchall()[::-1]
        elapsed=rows[-1]['timestamp']-rows[0]['timestamp'] if len(rows)>1 else 0
        work=sum(block_work(row['bits'],SUMUWW.pow_limit) for row in rows[1:])
        lo,hi=rows[0]['height'],rows[-1]['height']
        fee_row=c.execute(FINANCIAL_CTE+'SELECT coalesce(sum(fee_units),0),count(*),count(fee_units) FROM history WHERE coinbase=0 AND height BETWEEN ? AND ?',(lo,hi)).fetchone()
        distributions=c.execute('''SELECT o.address,count(DISTINCT t.blockhash) blocks,sum(o.value) amount FROM outputs o
          JOIN txs t ON t.txid=o.txid JOIN blocks b ON b.hash=t.blockhash
          WHERE t.coinbase=1 AND b.height BETWEEN ? AND ? AND o.value>0 GROUP BY o.address ORDER BY blocks DESC,amount DESC LIMIT 100''',(lo,hi)).fetchall()
        initial=valid_target(SUMUWW.initial_bits,SUMUWW.pow_limit)
        def lookup(digest):
            row=c.execute('SELECT * FROM blocks WHERE hash=?',(hash_to_display(digest),)).fetchone()
            return Header(row['version'],bytes.fromhex(row['parent'])[::-1],bytes.fromhex(row['merkle'])[::-1],row['timestamp'],row['bits'],row['nonce']) if row else None
        nxt=expected_bits(hi,bytes.fromhex(rows[-1]['hash'])[::-1],lookup,SUMUWW.pow_limit,SUMUWW.initial_bits,
            no_retarget=SUMUWW.no_retarget,interval=SUMUWW.retarget_interval,target_timespan=SUMUWW.target_timespan,
            asert_activation_height=SUMUWW.asert_activation_height,dgw_activation_height=SUMUWW.dgw_activation_height,
            dgw_interval_activation_height=SUMUWW.dgw_interval_activation_height,
            dgw_retarget_interval=SUMUWW.dgw_retarget_interval)
        current_target=valid_target(rows[-1]['bits'],SUMUWW.pow_limit);next_target=valid_target(nxt,SUMUWW.pow_limit)
        changes=[]
        previous=None
        for row in rows:
            if previous is not None and row['bits']!=previous['bits']:
                changes.append({'height':row['height'],'timestamp':row['timestamp'],'bits':f'{row["bits"]:08x}',
                    'change_percent':(valid_target(previous['bits'],SUMUWW.pow_limit)/valid_target(row['bits'],SUMUWW.pow_limit)-1)*100})
            previous=row
        audits=[{'blockhash':r['blockhash'],'height':r['height'],'observed_at':r['observed_at']} for r in c.execute(
            'SELECT a.blockhash,b.height,a.observed_at FROM block_audits a JOIN blocks b ON b.hash=a.blockhash ORDER BY b.height DESC LIMIT 25')]
        return {'limit':limit,'block_count':len(rows),'from_height':lo,'to_height':hi,'elapsed_seconds':elapsed,
            'estimated_hashrate':work/elapsed if elapsed>0 else None,'claimed_rewards':money(sum(row['reward'] for row in rows)),
            'maximum_subsidies':money(sum(row['subsidy'] for row in rows)),'known_fees':money(fee_row[0]),
            'resolved_fee_transactions':fee_row[2],'ordinary_transactions':fee_row[1],
            'payouts':[{'address':r['address'],'blocks':r['blocks'],'amount':money(r['amount']),'block_share_percent':100*r['blocks']/len(rows)} for r in distributions],
            'current_bits':f'{rows[-1]["bits"]:08x}','next_bits':f'{nxt:08x}','current_difficulty':initial/current_target,
            'next_difficulty':initial/next_target,'next_change_percent':(current_target/next_target-1)*100,
            'next_height':hi+1,'dgw_activation':SUMUWW.dgw_activation_height,'dgw_remaining':max(0,SUMUWW.dgw_activation_height-hi-1),
            'changes':changes,'audits':audits,'payouts_are_not_miner_identities':True,'hashrate_is_estimate':True}

    def block_audit(self,c,key):
        block=self.block_row(c,key);row=c.execute('SELECT * FROM block_audits WHERE blockhash=?',(block['hash'],)).fetchone()
        if row is None:return {'blockhash':block['hash'],'height':block['height'],'available':False}
        expected=json.loads(row['expected']);actual=json.loads(row['actual']);observed=json.loads(row['observed'])
        matching=[txid for txid in expected if txid in set(actual)]
        return {'blockhash':block['hash'],'height':block['height'],'available':True,'observed_at':row['observed_at'],
            'captured_at':row['captured_at'],'expected':expected,'actual':actual,'matching':matching,
            'missing':[txid for txid in expected if txid not in set(actual)],
            'added':[txid for txid in actual if txid not in set(expected)],
            'unseen':[txid for txid in actual if txid not in set(observed)],
            'match_percent':100*len(matching)/len(expected) if expected else None,
            'scope':'local_observation_not_evidence_of_misconduct'}

    def ledger(self,c,text,filters=None,offset=0,limit=25):
        canonical=encode_address(decode_address(text,network=SUMUWW),network=SUMUWW)
        if type(offset) is not int or not 0<=offset<=1000000:raise ValueError('Invalid ledger offset')
        if type(limit) is not int or not 1<=limit<=10000:raise ValueError('Invalid ledger limit')
        f=checked_filters(filters)
        if set(f)-{'date_from','date_to','min_height','max_height'}:raise ValueError('Unsupported address-period filter')
        tip=self.tip_height(c);start=f.get('min_height',0);end=min(tip,f.get('max_height',tip))
        if 'date_from' in f:
            row=c.execute('SELECT min(height) FROM blocks WHERE timestamp>=?',(f['date_from'],)).fetchone()
            start=max(start,row[0] if row[0] is not None else tip+1)
        if 'date_to' in f:
            row=c.execute('SELECT max(height) FROM blocks WHERE timestamp<?',(f['date_to'],)).fetchone()
            end=min(end,row[0] if row[0] is not None else -1)
        if start>end:start=end+1
        cte='''WITH movements AS (
          SELECT o.txid,sum(o.value) received,0 spent FROM outputs o JOIN txs t ON t.txid=o.txid
          JOIN blocks b ON b.hash=t.blockhash WHERE o.address=? AND b.height>0 GROUP BY o.txid
          UNION ALL SELECT i.txid,0,sum(o.value) FROM inputs i JOIN outputs o ON o.txid=i.previous AND o.n=i.previous_n
          WHERE o.address=? GROUP BY i.txid), entries AS (
          SELECT t.txid,t.coinbase,t.position,b.height,b.timestamp,sum(m.received) received,sum(m.spent) spent
          FROM movements m JOIN txs t ON t.txid=m.txid JOIN blocks b ON b.hash=t.blockhash GROUP BY t.txid) '''
        args=[canonical,canonical]
        opening=c.execute(cte+'SELECT coalesce(sum(received-spent),0) FROM entries WHERE height<?',args+[start]).fetchone()[0]
        totals=c.execute(cte+'''SELECT count(*),coalesce(sum(received),0),coalesce(sum(spent),0),
          coalesce(sum(CASE WHEN coinbase=1 THEN received ELSE 0 END),0) FROM entries WHERE height BETWEEN ? AND ?''',args+[start,end]).fetchone()
        records=c.execute(cte+'''SELECT *,sum(received-spent) OVER (ORDER BY height,position,txid ROWS UNBOUNDED PRECEDING) balance
          FROM entries WHERE height BETWEEN ? AND ? ORDER BY height DESC,position DESC,txid DESC LIMIT ? OFFSET ?''',args+[start,end,limit,offset]).fetchall()
        bucket=max(1,math.ceil(max(1,end-start+1)/512))
        grouped=c.execute(cte+'''SELECT max(height) height,max(timestamp) timestamp,sum(received-spent) delta FROM entries
          WHERE height BETWEEN ? AND ? GROUP BY CAST((height-?)/? AS INTEGER) ORDER BY height''',args+[start,end,start,bucket]).fetchall()
        balance=opening;points=[{'height':max(0,start-1),'balance':money(balance),'value':balance/100000000}]
        for row in grouped:
            balance+=row['delta'];points.append({'height':row['height'],'timestamp':row['timestamp'],'balance':money(balance),'value':balance/100000000})
        if end>=0 and points[-1]['height']!=end:points.append({'height':end,'balance':money(balance),'value':balance/100000000})
        return {'address':canonical,'from_height':start,'to_height':end,'opening_balance':money(opening),
            'closing_balance':money(opening+totals[1]-totals[2]),'received':money(totals[1]),'spent':money(totals[2]),
            'mining_received':money(totals[3]),'net_change':money(totals[1]-totals[2]),'total':totals[0],
            'offset':offset,'limit':limit,'filters':dict(filters or {}),'points':points,'sampled':bucket>1,
            'transactions':[{'txid':r['txid'],'coinbase':r['coinbase'],'height':r['height'],'timestamp':r['timestamp'],
                'received':money(r['received']),'spent':money(r['spent']),'net_change':money(r['received']-r['spent']),
                'balance_after':money(opening+r['balance'])} for r in records],
            'date_mapping':'dates_resolve_to_contiguous_block_height_range','genesis_reward_excluded':True}

    def past_balance(self,c,text,height):
        if type(height) is not int or not 0<=height<=self.tip_height(c):raise ValueError('Snapshot height is outside this chain')
        result=self.ledger(c,text,{'max_height':str(height)},limit=1)
        return {'address':result['address'],'height':height,'balance':result['closing_balance']}

    def address_report(self,c,text,filters=None,lang='en'):
        result=self.ledger(c,text,filters,limit=10000)
        result.update(report_kind='address',report_language=lang)
        return result

    def receipt(self,c,txid,lang='en'):
        result=self.transaction(c,txid);result.update(report_kind='receipt',report_language=lang)
        return result

    def transaction_report(self,c,kind='all',filters=None,lang='en'):
        result=self.filtered_transactions(c,kind,0,filters,10000)
        result.update(report_kind='transactions',report_language=lang)
        return result
