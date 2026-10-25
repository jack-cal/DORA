"""Derived block reward information. Never part of consensus or wallet balance."""
from .primitives import subsidy, format_amount


def reward_info(block, height, fees):
    return reward_amounts(sum(output.value for output in block.transactions[0].outputs), height, fees)


def reward_amounts(claimed, height, fees):
    limit = subsidy(height)
    known = type(fees) is int and fees >= 0
    full = known and claimed == limit + fees and height != 0
    state = 'genesis_unspendable' if height == 0 else 'unavailable' if not known else 'full' if full else 'underclaimed'
    values = {'subsidy_limit': limit, 'transaction_fees': fees if known else None,
              'claimed_reward': claimed, 'unclaimed_reward': limit + fees - claimed if known else None,
              'subsidy_reward': limit if full else None, 'fee_reward': fees if full else None}
    result = {'scope': 'block', 'allocation': state, 'amount_unit': 'yugeon'}
    for key, value in values.items():
        result[key + '_units'] = value
        result[key + '_smw'] = format_amount(value) if value is not None and value >= 0 else None
    return result


def read_reward(connection, block, height):
    """Read a validated derived fee index; old read-only databases stay readable."""
    if height == 0:
        return reward_info(block, height, 0)
    table = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='block_reward_fees'").fetchone()
    row = connection.execute('SELECT fees FROM block_reward_fees WHERE blockhash=?', (block.block_hash(),)).fetchone() if table else None
    # Empty blocks have exactly zero fees, even before the derived index exists.
    fees = row[0] if row else 0 if len(block.transactions) == 1 else None
    return reward_info(block, height, fees)


def reward_columns(transaction):
    reward = transaction.get('mining_reward') or {}
    if not transaction.get('coinbase'):
        return ('', '', '')
    return tuple((reward[key + '_smw'] + ' SMW') if reward.get(key + '_smw') is not None else '—' for key in ('subsidy_reward', 'fee_reward', 'claimed_reward'))


def reward_rows(reward):
    if not reward:
        return []
    rows = [('New issuance (block)', reward.get('subsidy_reward_smw')),
            ('Transaction fees (block)', reward.get('fee_reward_smw')),
            ('Total block reward', reward.get('claimed_reward_smw'))]
    if reward.get('allocation') == 'underclaimed':
        rows += [('Issuance limit (block)', reward.get('subsidy_limit_smw')),
                 ('Available fees (block)', reward.get('transaction_fees_smw')),
                 ('Unclaimed reward', reward.get('unclaimed_reward_smw'))]
    return [(label, value + ' SMW' if value is not None else '—') for label, value in rows]
