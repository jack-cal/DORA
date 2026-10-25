"""Render directly authored translations; never calls a translation service.

Documentation-only dependency: Markdown==3.7. Run from the source distribution:
    python packaging/generate_exchange_documents.py
Application binaries, language preferences and user data are not touched.
"""
from pathlib import Path
import ast
import hashlib
import html
import json
import os
import re
import markdown

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / 'programs/PC/docs/translations/exchange'
TOPICS = ('README', 'EXCHANGE_INTEGRATION', 'RPC_API', 'NETWORK_RUNBOOK',
          'RELEASE_NOTES', 'EXCHANGE_EXAMPLES')
TITLE = (0, 1, 2, 3, 4, 15)
TEXT_HEADINGS = (4, 6, 8, 2, 11, 12, 13, 15)
STYLE = '''body{font:17px/1.75 system-ui,"Noto Sans",sans-serif;color:#183248;background:#f5f8fb;margin:0}
main,header{max-width:1080px;margin:auto;padding:28px}main{background:white;border-radius:16px;margin-bottom:32px}
h1,h2{line-height:1.35;color:#164967}h1{font-size:2rem}h2{margin-top:2em}a{color:#075f91}
nav{display:flex;flex-wrap:wrap;gap:10px 18px;margin:16px 0}nav a[aria-current=page]{font-weight:bold}
details{background:#eaf0f6;padding:12px;border-radius:8px}summary{cursor:pointer}
table{border-collapse:collapse;width:100%;display:block;overflow:auto;margin:20px 0}
td,th{border:1px solid #cad7e3;padding:10px;text-align:start;vertical-align:top}
pre{background:#edf2f7;padding:16px;overflow:auto;direction:ltr;text-align:left;unicode-bidi:isolate}
code{font:0.9em ui-monospace,Consolas,monospace;direction:ltr;unicode-bidi:isolate;overflow-wrap:anywhere}
p{overflow-wrap:anywhere}blockquote{border-inline-start:4px solid #a8bccc;padding-inline-start:16px;margin-inline:0}
.mongolian p{font-family:"Mongolian Baiti","Noto Sans Mongolian",serif;writing-mode:vertical-lr;height:34rem;max-width:100%;overflow:auto;line-height:2}
.mongolian p code{writing-mode:horizontal-tb}footer{padding-top:24px;border-top:1px solid #cad7e3;color:#46617a}
@media(max-width:650px){main,header{padding:18px}h1{font-size:1.6rem}}
'''

def put(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    # Preserve the existing newline style of tracked documents.
    ending = '\r\n' if path.exists() and b'\r\n' in path.read_bytes() else '\n'
    path.write_bytes(text.replace('\r\n', '\n').replace('\n', ending).encode('utf-8'))

def relative(target, page):
    return os.path.relpath(target, page.parent).replace('\\', '/')

def relocate(text, source, dest):
    def link(m):
        url=m[1]
        if '://' in url or url.startswith('#'):
            return m[0]
        return '](' + relative(source.parent / url, dest) + ')'
    return re.sub(r'\]\(([^\s)]+)\)', link, text)

def languages():
    tree=ast.parse((ROOT/'sumuww/i18n.py').read_text(encoding='utf-8'))
    return next(ast.literal_eval(node.value) for node in tree.body
                if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id=='LANGUAGES' for t in node.targets))

LANGUAGES=languages()
DATA={lang:json.loads((CATALOG/f'{lang}.json').read_text(encoding='utf-8')) for lang,_ in LANGUAGES}
assert len(DATA)==34 and LANGUAGES[0][0]=='en'
assert set(p.stem for p in CATALOG.glob('*.json'))==set(DATA)
for lang, data in DATA.items():
    assert len(data['labels'])==19 and len(data['text'])==8, lang
    assert all(isinstance(s,str) and s.strip() for s in data['labels']+data['text']), lang

ENGLISH=ROOT/'EXCHANGE_INTEGRATION.md'
full_text=ENGLISH.read_text(encoding='utf-8')
examples=re.findall(r'```[^\n]*\n.*?```',full_text,re.S)
assert examples
rpc_text=(ROOT/'programs/PC/docs/RPC_API.md').read_text(encoding='utf-8')
route_rows=[line for line in rpc_text.splitlines() if re.match(r'\| `(GET|POST)`',line)]
assert len(route_rows)==11
contract=json.loads((ROOT/'API_CONTRACT.json').read_text(encoding='utf-8'))
assert len(contract['methods'])==28

def machine_reference():
    defaults={'verbose':'true','include_mempool':'true','start_height':'0','limit':'100','offset':'0','vsize':'140','mode':'normal'}
    lines=['| method | params |','|---|---|']
    for method, info in contract['methods'].items():
        params=[p if i<info['required'] else p+'='+defaults[p] for i,p in enumerate(info['parameters'])]
        lines.append('| `'+method+'` | `'+(', '.join(params) or '{} / []')+'` |')
    lines += ['','| HTTP | URI | JSON |','|---|---|---|',*route_rows]
    return '\n'.join(lines)

def section(data,index):
    return '## '+data['labels'][TEXT_HEADINGS[index]]+'\n\n'+data['text'][index]+'\n\n'

def body(topic,lang,page):
    data=DATA[lang]; labels=data['labels']
    result='# SUMUWW · '+labels[TITLE[TOPICS.index(topic)]]+'\n\n'
    result+=data['text'][0]+'\n\n'
    indices = {'README':[2,3,7], 'EXCHANGE_INTEGRATION':[1,2,3,4,5,6,7],
               'RPC_API':[3,4,5,6], 'NETWORK_RUNBOOK':[1,4,6,7],
               'RELEASE_NOTES':[2,3,7], 'EXCHANGE_EXAMPLES':[2,7]}[topic]
    for i in indices: result += section(data,i)
    if topic == 'RPC_API': result += machine_reference()+'\n\n'
    if topic == 'EXCHANGE_EXAMPLES':
        result += '```powershell\npython examples/node_contract.py\npython -m unittest tests.test_node_contract tests.test_rpc -v\n```\n\n'
    if topic in ('README','EXCHANGE_INTEGRATION','NETWORK_RUNBOOK'):
        result+='```text\nnetwork: sumuww (dora)\ngenesis: 00000032e243a8c71b449b13c2da733dd329f308a75aa4358f3f22707a28af97\nHRP: sumuww\nP2P magic: d052470c\n1 SMW = 100000000 yugeon\n```\n\n'
    result+=' · '.join(f'[{labels[TITLE[i]]}]({name}.html)' for i,name in enumerate(TOPICS) if name!=topic)+'\n\n'
    result+=f'[{labels[5]}]({relative(ENGLISH.with_suffix(".html"),page)}) · '
    result+=f'[API_CONTRACT.json]({relative(ROOT/"API_CONTRACT.json",page)}) · '
    result+=f'[vectors.json]({relative(ROOT/"examples/exchange/vectors.json",page)})\n'
    return result

def render(text,page,lang='en',topic='EXCHANGE_INTEGRATION',locale_root=None):
    label=DATA[lang]['labels']; root=locale_root or ROOT/'docs/i18n'
    nav='<details><summary>'+html.escape(label[0])+' · 34</summary><nav>'
    for code,name in LANGUAGES:
        url=relative(root/code/(topic+'.html'),page)
        current=' aria-current="page"' if code==lang else ''
        nav+=f'<a href="{html.escape(url)}" lang="{code}"{current}><bdi>{html.escape(name)}</bdi></a>'
    nav+='</nav></details><nav>'
    for i,name in enumerate(TOPICS):
        nav+=f'<a href="{html.escape(relative(root/lang/(name+".html"),page))}">{html.escape(label[TITLE[i]])}</a>'
    nav+='</nav>'
    title=next((s[2:] for s in text.splitlines() if s.startswith('# ')),'SUMUWW')
    direction='rtl' if lang in ('ar','ur') else 'ltr'
    css=' class="mongolian"' if lang=='mn-Mong' else ''
    return f'<!doctype html><html lang="{lang}" dir="{direction}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="sumuww-doc-revision" content="52"><title>{html.escape(title)}</title><style>{STYLE}</style></head><body><header>{nav}</header><main{css}>'+markdown.markdown(text,extensions=['fenced_code','tables'])+'<footer>SUMUWW · 0.57.46 · 2026-10-25</footer></main></body></html>\n'

def main():
    paths=[]
    for root in [ROOT/'programs/PC/docs/i18n',ROOT/'docs/i18n']:
        for lang,_ in LANGUAGES:
            for topic in TOPICS:
                page=root/lang/(topic+'.md');text=body(topic,lang,page)
                put(page,text);put(page.with_suffix('.html'),render(text,page.with_suffix('.html'),lang,topic,root))
                paths += [page,page.with_suffix('.html')]
    # Root entry remains English, independent of OS/browser locale.
    for page in [ROOT/'docs/index.html',ROOT/'docs/INTEGRATION.html']:
        text=body('README','en',ROOT/'docs/i18n/en/README.md')
        text=relocate(text,ROOT/'docs/i18n/en/README.md',page)
        put(page,render(text,page,'en','README')); paths.append(page)
    for src,topic in [(ROOT/'EXCHANGE_INTEGRATION.md','EXCHANGE_INTEGRATION'),
                      (ROOT/'programs/PC/docs/RPC_API.md','RPC_API'),
                      (ROOT/'programs/PC/docs/NETWORK_RUNBOOK.md','NETWORK_RUNBOOK'),
                      (ROOT/'programs/PC/README.md','README'),
                      (ROOT/'programs/PC/RELEASE_NOTES.md','RELEASE_NOTES'),
                      (ROOT/'examples/exchange/README.md','EXCHANGE_EXAMPLES')]:
        put(src.with_suffix('.html'),render(src.read_text(encoding='utf-8'),src.with_suffix('.html'),'en',topic))
        paths.append(src.with_suffix('.html'))
    # Retain the previous Korean entry path while giving it the same complete content.
    source=ROOT/'docs/i18n/ko/EXCHANGE_INTEGRATION.md'
    page=ROOT/'EXCHANGE_INTEGRATION.ko.md'
    text=relocate(source.read_text(encoding='utf-8'),source,page)
    put(page,text);put(page.with_suffix('.html'),render(text,page.with_suffix('.html'),'ko'))
    paths += [page,page.with_suffix('.html')]
    page=ROOT/'RPC_API.html';src=ROOT/'programs/PC/docs/RPC_API.md'
    put(page,render(relocate(src.read_text(encoding='utf-8'),src,page),page,'en','RPC_API'));paths.append(page)
    layout=json.loads((ROOT/'DOCUMENT_LAYOUT.json').read_text(encoding='utf-8'))
    layout.update(documentation_revision=52,publication_language='en',default_document_language='en',
        documentation_languages=[code for code,_ in LANGUAGES],
        translation_policy='English default. Directly authored editions of the current integration update in all 34 UI languages. No external automatic translation. Existing UI preferences are preserved.',
        localized_update_topics=list(TOPICS),
        localized_update_scope='The 0.57.46 / Android 0.6.95 yugeon fee policy, RBF, block reward breakdown, data records and isolated multisig/lock activation tests. Historical whitepapers and other topics retain their separately recorded translation scope.',
        documentation_edition='0.57.46',
        legacy_html_paths='Current integration topics contain localized content in both document layouts. Other historical coin-document paths retain their previous scope.')
    layout['exchange_integration'].update(rpc_methods=len(contract['methods']), rest_routes=11, languages=[code for code,_ in LANGUAGES],index='docs/index.html',localized_path='docs/i18n/{language}/EXCHANGE_INTEGRATION.html')
    put(ROOT/'DOCUMENT_LAYOUT.json',json.dumps(layout,ensure_ascii=False,indent=2)+'\n')
    paths += [ROOT/'DOCUMENT_LAYOUT.json',*CATALOG.glob('*.json')]
    manifest={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
    put(ROOT/'docs/EXCHANGE_DOCUMENTS.json',json.dumps({'revision':52,'default_language':'en','languages':[c for c,_ in LANGUAGES],'topics':list(TOPICS),'files':manifest},indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'languages':len(DATA),'localized_pages':len(DATA)*len(TOPICS)*2,'manifest_files':len(manifest),'default':'en'}))

if __name__=='__main__':main()
