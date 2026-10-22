"""Build-time translation preparation. The packaged explorer has no translation requests."""
from pathlib import Path
import concurrent.futures
import argparse
import json
import re
import urllib.parse
import urllib.request

ROOT=Path(__file__).resolve().parent
LANGUAGES=[('ko','한국어'),('en','English'),('ja','日本語'),('zh','简体中文'),('zh-TW','繁體中文（台灣）'),
 ('zh-HK','繁體中文（香港）'),('fr','Français'),('es','Español'),('pt','Português'),('de','Deutsch'),
 ('it','Italiano'),('ru','Русский'),('ar','العربية'),('sw','Kiswahili'),('hi','हिन्दी'),('id','Bahasa Indonesia'),
 ('vi','Tiếng Việt'),('tr','Türkçe'),('th','ไทย'),('bn','বাংলা'),('ur','اردو'),('pl','Polski'),('nl','Nederlands'),
 ('fil','Filipino'),('ta','தமிழ்'),('cs','Čeština'),('da','Dansk'),('fi','Suomi'),('el','Ελληνικά'),
 ('no','Norsk (bokmål)'),('sv','Svenska'),('sr','Српски'),('mn','Монгол (Кирилл)'),('mn-Mong','Mongolian (traditional)')]

def build(allow_network=False):
    base=json.loads((ROOT/'i18n-base.json').read_text(encoding='utf-8'))
    folder=ROOT/'locales';folder.mkdir(exist_ok=True)
    keys=list(base['en'])
    def prepare(language):
        code,_=language
        path=folder/(code+'.json')
        if code in base:
            values=base[code]
        elif path.exists():
            values=json.loads(path.read_text(encoding='utf-8'))
        else:
            values={}
        missing=[key for key in keys if key not in values]
        if missing:
            if not allow_network:
                raise ValueError('Missing bundled locale: '+code+'. Use --translate-missing only to prepare new translation assets.')
            for start in range(0,len(missing),45):
                chunk=missing[start:start+45]
                text='\n'.join('@@'+str(keys.index(key))+'@@ '+base['en'][key] for key in chunk)
                target={'zh':'zh-CN','fil':'tl'}.get(code,code)
                url='https://translate.googleapis.com/translate_a/single?'+urllib.parse.urlencode(
                    {'client':'gtx','sl':'en','tl':target,'dt':'t','q':text})
                with urllib.request.urlopen(url,timeout=30) as response:
                    translated=json.load(response)
                text=''.join(part[0] for part in translated[0] if part[0])
                matches=list(re.finditer(r'@@\s*(\d{1,3})\s*@@',text))
                for i,match in enumerate(matches):
                    index=int(match[1])
                    if index>=len(keys) or keys[index] not in chunk:continue
                    end=matches[i+1].start() if i+1<len(matches) else len(text)
                    values[keys[index]]=text[match.end():end].strip()
            # Some languages alter delimiters. Translate only affected entries
            # individually instead of accepting merged or incomplete messages.
            for key in keys:
                if key not in values or '@@' in values[key] or not values[key].strip():
                    target={'zh':'zh-CN','fil':'tl'}.get(code,code)
                    url='https://translate.googleapis.com/translate_a/single?'+urllib.parse.urlencode(
                        {'client':'gtx','sl':'en','tl':target,'dt':'t','q':base['en'][key]})
                    with urllib.request.urlopen(url,timeout=30) as response:
                        translated=json.load(response)
                    values[key]=''.join(part[0] for part in translated[0] if part[0]).strip()
        if set(values)!=set(keys) or any(not isinstance(v,str) or not v.strip() for v in values.values()):
            raise ValueError('Incomplete translation: '+code)
        # Fixed protocol names and address examples remain literal identifiers.
        values['placeholder']=values['placeholder'].replace('SUMUWW1','sumuww1')
        if code not in ('ko','en'):
            values['nonce']='Nonce'
        path.write_text(json.dumps(values,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(code,'complete',flush=True)
        return code,values
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        translations=dict(executor.map(prepare,LANGUAGES))
    data={'languages':LANGUAGES,'strings':translations}
    (ROOT/'dist/languages.js').write_text('"use strict";\nconst explorerLanguages='+json.dumps(data,ensure_ascii=False,separators=(',',':'))+';\n',encoding='utf-8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--translate-missing',action='store_true',help='Use Google Translate at build time for missing locale files')
    build(parser.parse_args().translate_missing)
