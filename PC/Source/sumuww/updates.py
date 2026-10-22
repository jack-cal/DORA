"""Explicit, read-only GitHub checks; no installer or wallet access."""
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

MANIFEST_URL='https://raw.githubusercontent.com/jack-cal/SUMUWW/main/updates.json'
RELEASES_URL='https://github.com/jack-cal/SUMUWW/releases'
MAX_BYTES=65536

def release_url(value):
    if not isinstance(value,str) or len(value)>2048:raise ValueError('Invalid release URL')
    u=urlsplit(value)
    if (u.scheme!='https' or u.hostname!='github.com' or u.username is not None or
        u.password is not None or u.port not in (None,443) or u.query or u.fragment or
        not re.fullmatch(r'/jack-cal/SUMUWW/releases(?:/tag/[A-Za-z0-9._-]+)?',u.path)):
        raise ValueError('Untrusted release URL')
    return value

def version(value):
    if not isinstance(value,str):raise ValueError('Invalid version')
    match=re.fullmatch(r'(\d{1,5})\.(\d{1,5})\.(\d{1,5})(?:-[A-Za-z0-9._-]+)?',value)
    if not match:raise ValueError('Invalid version')
    return tuple(map(int,match.groups()))

def parse_manifest(raw,installed,platform='windows'):
    if not isinstance(raw,bytes) or len(raw)>MAX_BYTES:raise ValueError('Update response size')
    def unique(pairs):
        value={}
        for key,item in pairs:
            if key in value:raise ValueError('Duplicate update field')
            value[key]=item
        return value
    value=json.loads(raw,object_pairs_hook=unique)
    if type(value.get('schema_version')) is not int or value['schema_version']!=1:raise ValueError('Update schema')
    row=value[platform];latest=row['version'];url=release_url(row['release_url'])
    return {'version':latest,'url':url,'available':version(latest)>version(installed)}

class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected update redirect')

def check(installed):
    request=Request(MANIFEST_URL,headers={'User-Agent':'SUMUWW-update-check','Accept':'application/json'})
    with build_opener(_NoRedirect()).open(request,timeout=7) as response:
        if response.status!=200:raise ValueError('Update response status')
        raw=response.read(MAX_BYTES+1)
    return parse_manifest(raw,installed)
