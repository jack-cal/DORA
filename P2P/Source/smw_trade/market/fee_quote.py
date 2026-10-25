"""Live queue fee quotes; no confirmed-block fee history is sampled."""
from fractions import Fraction

TARGETS={'fast':1,'normal':3,'slow':6}
MAX_FEE=1_000_000


def validate_settings(config):
    if config.get('fee_mode','normal') not in TARGETS:raise ValueError('Invalid fee mode.')
    if config.get('fee_rate') is not None:rate(config['fee_rate'])


def rate(value):
    try:result=Fraction(str(value))
    except (ValueError,ZeroDivisionError):raise ValueError('Invalid fee rate.') from None
    if not 0<result<=1_000_000:raise ValueError('Invalid fee rate.')
    return result


def quote(size,bins,floor,mode='normal',manual=None):
    if type(size) is not int or not 1<=size<=1_000_000:raise ValueError('Invalid transaction size.')
    if mode not in TARGETS:raise ValueError('Invalid fee mode.')
    floor=rate(floor)
    if manual is not None:
        chosen=rate(manual)
        if chosen<floor:raise ValueError('Fee rate is below the current relay minimum.')
    else:
        parsed=[]
        if not isinstance(bins,list) or len(bins)>1_000_000:raise ValueError('Invalid live fee histogram.')
        for item in bins:
            if not isinstance(item,(list,tuple)) or len(item)!=2:raise ValueError('Invalid live fee histogram.')
            r,n=item
            if type(n) is not int or n<0:raise ValueError('Invalid live fee size.')
            if Fraction(str(r))<0:raise ValueError('Invalid live fee rate.')
            parsed.append((Fraction(str(r)),n))
        chosen=floor;available=TARGETS[mode]*1_000_000-size;used=0
        for r,n in sorted(parsed,reverse=True):
            used+=n
            if used>available:
                chosen=max(floor,r+Fraction(1,10));break
    fee=(chosen.numerator*size+chosen.denominator-1)//chosen.denominator
    if fee>MAX_FEE:raise ValueError('Fee quote exceeds the spending limit; no transaction was signed.')
    return fee
