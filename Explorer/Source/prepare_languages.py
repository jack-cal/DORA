"""Validate and bundle directly authored local translations. No translation service is used."""
from pathlib import Path
import concurrent.futures
import argparse
import json

ROOT=Path(__file__).resolve().parent
LANGUAGES=[('ko','한국어'),('en','English'),('ja','日本語'),('zh','简体中文'),('zh-TW','繁體中文（台灣）'),
 ('zh-HK','繁體中文（香港）'),('fr','Français'),('es','Español'),('pt','Português'),('de','Deutsch'),
 ('it','Italiano'),('ru','Русский'),('ar','العربية'),('sw','Kiswahili'),('hi','हिन्दी'),('id','Bahasa Indonesia'),
 ('vi','Tiếng Việt'),('tr','Türkçe'),('th','ไทย'),('bn','বাংলা'),('ur','اردو'),('pl','Polski'),('nl','Nederlands'),
 ('fil','Filipino'),('ta','தமிழ்'),('cs','Čeština'),('da','Dansk'),('fi','Suomi'),('el','Ελληνικά'),
 ('no','Norsk (bokmål)'),('sv','Svenska'),('sr','Српски'),('mn','Монгол (Кирилл)'),('mn-Mong','Mongolian (traditional)')]

def build():
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
            raise ValueError('Missing directly authored locale entries: '+code+': '+', '.join(missing))
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
    parser.parse_args()
    build()
