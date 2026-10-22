"""Explorer-only witness-v0 address codec; does not validate spending scripts."""
from sumuww.address import AddressError, _bech32_encode, _bech32_decode, _convert_bits
from sumuww.profiles import SUMUWW, get_network

def encode_address(script_pubkey, *, network='regtest'):
    profile=get_network(network)
    if not isinstance(script_pubkey,bytes) or len(script_pubkey) not in (22,34) or script_pubkey[:2] != bytes([0,len(script_pubkey)-2]):
        raise AddressError('Expected a native witness-v0 P2WPKH or P2WSH output')
    return _bech32_encode(profile.address_hrp,[0]+_convert_bits(script_pubkey[2:],8,5,pad=True))

def decode_address(text, *, network='regtest'):
    profile=get_network(network)
    hrp,data=_bech32_decode(text)
    accepted=(profile.address_hrp,'dora') if profile is SUMUWW else (profile.address_hrp,)
    if hrp not in accepted:raise AddressError('Address belongs to a different network')
    if not data or data[0] != 0:raise AddressError('Only witness version 0 is supported')
    program=bytes(_convert_bits(data[1:],5,8,pad=False))
    if len(program) not in (20,32):raise AddressError('Expected a 20- or 32-byte witness-v0 program')
    return bytes([0,len(program)])+program
