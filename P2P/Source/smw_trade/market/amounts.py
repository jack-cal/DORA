"""Exact, bounded decimal amounts; floats never enter signed trade terms."""
from decimal import Decimal, localcontext
import re
from sumuww.primitives import MAX_MONEY as SMW_MAX_MONEY

DECIMALS = {'SMW': 8, 'BTC': 8}
QUOTES = ('BTC',)
MAX_UNITS = {'SMW': SMW_MAX_MONEY, 'BTC': 21_000_000 * 10**8}

def decimal(text):
    if not isinstance(text, str) or len(text) > 80 or not re.fullmatch(r'(0|[1-9][0-9]*)(\.[0-9]+)?', text):
        raise ValueError('Enter a positive decimal number without exponent notation.')
    value = Decimal(text)
    if value <= 0:
        raise ValueError('Amount must be positive.')
    return value

def units(text, coin):
    if coin not in DECIMALS:raise ValueError('Unsupported asset.')
    with localcontext() as ctx:
        ctx.prec = 100
        scaled = decimal(text) * 10**DECIMALS[coin]
        if scaled != scaled.to_integral_value() or scaled > MAX_UNITS[coin]:
            raise ValueError('Amount exceeds the asset precision or supply bound.')
        return int(scaled)

def show(value, coin):
    if coin not in DECIMALS:raise ValueError('Unsupported asset.')
    if type(value) is not int or value < 0:
        raise ValueError('Invalid integer amount.')
    n = DECIMALS[coin]
    return (f'{value // 10**n}.{value % 10**n:0{n}d}').rstrip('0').rstrip('.')

def quote_total(quantity, price, coin):
    if coin not in QUOTES:
        raise ValueError('Unsupported quote asset.')
    smw = units(quantity, 'SMW')
    with localcontext() as ctx:
        ctx.prec = 100
        price_value = decimal(price)
        total = Decimal(smw) / 10**8 * price_value
        result = units(format(total, 'f'), coin)
        canonical_price = format(price_value, 'f').rstrip('0').rstrip('.') if '.' in format(price_value, 'f') else format(price_value, 'f')
    return smw, result, canonical_price
