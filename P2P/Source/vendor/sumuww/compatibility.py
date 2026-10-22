"""Public SUMUWW names with compatibility for already published clients.

Wire identities, chain bytes, encrypted wallet formats and HD derivation values
are deliberately not rewritten by presentation or API field renaming.
"""

def compatibility_fields(value):
    if isinstance(value, dict):
        result = {key: compatibility_fields(item) for key, item in value.items()}
        for key, item in tuple(result.items()):
            if isinstance(key, str) and key.endswith('_smw'):
                result.setdefault(key[:-4] + '_dora', item)
        return result
    if isinstance(value, list): return [compatibility_fields(item) for item in value]
    if isinstance(value, tuple): return tuple(compatibility_fields(item) for item in value)
    return value

def public_view(value):
    """Project the logical SUMUWW identity; do not modify stored/wire identity."""
    if isinstance(value, dict):
        result = {key: public_view(item) for key, item in value.items()
                  if not isinstance(key, str) or not key.endswith('_dora')}
        if result.get('network') == 'dora': result['network'] = 'sumuww'
        if result.get('profile') == 'dora-independent-v0.12-p2wpkh':
            result['profile'] = 'sumuww-independent-v0.12-p2wpkh'
        return result
    if isinstance(value, list): return [public_view(item) for item in value]
    if isinstance(value, tuple): return tuple(public_view(item) for item in value)
    if value == 'no_dora_contacts': return 'no_sumuww_contacts'
    return value
