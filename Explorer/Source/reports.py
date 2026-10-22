"""Local PDF exports from an immutable explorer snapshot; no network calls."""
from datetime import datetime, timezone
from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape
import json
import threading

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ROOT=Path(__file__).resolve().parent
LOCK=threading.RLock()

def make_pdf(data):
    with LOCK:
        return _make_pdf(data)

def _make_pdf(data):
    raw=(ROOT/'dist/languages.js').read_text(encoding='utf-8')
    languages=json.loads(raw.split('const explorerLanguages=',1)[1].strip().rstrip(';'))['strings']
    lang=data.get('report_language','en')
    if lang not in languages:raise ValueError('Unsupported report language')
    fontname='Arial';fontfile='arial.ttf'
    if lang=='ko':fontname,fontfile='Malgun','malgun.ttf'
    elif lang=='ja':fontname,fontfile='Japanese','YuGothR.ttc'
    elif lang=='zh':fontname,fontfile='Chinese','msyh.ttc'
    elif lang in ('zh-TW','zh-HK'):fontname,fontfile='TraditionalChinese','msjh.ttc'
    elif lang in ('hi','bn','ta'):fontname,fontfile='Nirmala','Nirmala.ttc'
    elif lang=='th':fontname,fontfile='Thai','LeelawUI.ttf'
    elif lang=='mn-Mong':fontname,fontfile='Mongolian','monbaiti.ttf'
    fontpath=Path('C:/Windows/Fonts')/fontfile
    fallback=not fontpath.exists()
    if fallback:fontname='Helvetica';lang='en'
    elif fontname not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(fontname,str(fontpath),shapable=lang in ('hi','bn','ta')))
    if 'Arial' not in pdfmetrics.getRegisteredFontNames() and Path('C:/Windows/Fonts/arial.ttf').exists():
        pdfmetrics.registerFont(TTFont('Arial','C:/Windows/Fonts/arial.ttf',shapable=False))
    tr=languages[lang];rtl=lang in ('ar','ur')
    def visual(text):
        text=str(text)
        if rtl:
            import arabic_reshaper
            from bidi.algorithm import get_display
            text=get_display(arabic_reshaper.reshape(text))
        return escape(text)
    normal=ParagraphStyle('Body',fontName=fontname,fontSize=9,leading=14,spaceAfter=6,
        textColor=colors.HexColor('#26364a'),wordWrap='CJK',shaping=int(lang in ('hi','bn','ta')),
        alignment=TA_RIGHT if rtl else TA_LEFT)
    title=ParagraphStyle('Title',parent=normal,fontSize=19,leading=26,spaceAfter=14,textColor=colors.HexColor('#153b6d'))
    small=ParagraphStyle('Small',parent=normal,fontSize=7,leading=11)
    def label(key):return tr.get(key,key)
    def p(text,style=normal):
        # Keep hashes, decimal amounts and identifiers outside Indic shaping.
        if str(text).isascii():
            style=ParagraphStyle('Identifier',parent=style,fontName='Arial' if 'Arial' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',shaping=0,alignment=TA_LEFT)
        return Paragraph(visual(text),style)
    def table(headers,rows,widths):
        cells=[[p(x,small) for x in headers]]+[[p('—' if x is None else x,small) for x in row] for row in rows]
        result=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
        result.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e9f0fa')),
            ('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.7,colors.HexColor('#afbed1')),
            ('LINEBELOW',(0,1),(-1,-1),.25,colors.HexColor('#dce3ec')),
            ('LEFTPADDING',(0,0),(-1,-1),6),('RIGHTPADDING',(0,0),(-1,-1),6),
            ('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
        return result
    kind=data['report_kind'];heading={'receipt':'receipt','address':'periodreport','transactions':'transactionhistory'}[kind]
    story=[p('SUMUWW · '+label(heading),title),p(label('reportscope'),small)]
    if fallback:story.append(p('English labels used because the selected language font is unavailable.',small))
    stamp=datetime.fromtimestamp(data.get('updated_at',0),timezone.utc).isoformat()
    story += [table([label('readtime'),label('snapshot')],[(stamp,str(data.get('chain_tip','—')))],[220,295]),Spacer(1,10)]
    if kind=='receipt':
        values=[('txid',data['txid']),('type',label('coinbase' if data['coinbase'] else 'ordinary')),
            ('block',label('pending') if data.get('pending') else str(data['height'])),('confirmations',str(data['confirmations'])),
            ('total',data['output_total']+' SMW'),('fee',(data.get('fee') or '—')+' SMW'),
            ('feerate',str(data.get('fee_rate') or '—')+' smallest units/vB'),('size',str(data['size'])+' B')]
        story.append(table([label('details'),label('value')],[(label(k),v) for k,v in values],[125,390]))
        for key in ('inputs','outputs'):
            story += [Spacer(1,14),p(label(key))]
            rows=[]
            for item in data[key]:
                identifier=item.get('address') or item.get('previous') or item.get('script') or label('coinbase')
                if key=='inputs' and item.get('previous'):
                    identifier+=' / '+item['previous']+':'+str(item['previous_n'])
                elif key=='outputs':identifier='#'+str(item['n'])+' / '+identifier
                rows.append((identifier,item.get('value','—')))
            story.append(table([label('address')+' / '+label('txid'),'SMW'],rows or [(label('coinbase'),'—')],[395,120]))
    elif kind=='address':
        story += [p(data['address']),p(label('height')+': '+str(data['from_height'])+'–'+str(data['to_height'])),p(label('periodnote'),small)]
        fields=['opening','closing','received','spentinputs','netchange']
        keys=['opening_balance','closing_balance','received','spent','net_change']
        story.append(table([label('details'),'SMW'],[(label(k),data[v]) for k,v in zip(fields,keys)],[300,215]))
        rows=[(r['height'],r['txid'],r['received'],r['spent'],r['balance_after']) for r in data['transactions']]
        story += [Spacer(1,14),p(label('history')),table([label(k) for k in ['height','txid','received','spentinputs','balanceafter']],rows,[40,190,95,95,95])]
    else:
        story.append(p(label('filters')+': '+json.dumps(data.get('filters',{}),ensure_ascii=False),small))
        rows=[(r['height'],r['txid'],r['output_total'],r['fee'],r['fee_rate']) for r in data['transactions']]
        story.append(table([label(k) for k in ['height','txid','total','fee','feerate']],rows,[40,190,95,95,95]))
    if kind!='receipt':story.append(p(label('includedrows')+': '+str(len(data['transactions']))+' / '+str(data['total']),small))
    story += [Spacer(1,12),p(label('reportscope'),small)]
    output=BytesIO()
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont(fontname,8);canvas.setFillColor(colors.HexColor('#52647b'))
        canvas.drawString(40,25,'SUMUWW Explorer · '+str(doc.page));canvas.restoreState()
    SimpleDocTemplate(output,pagesize=A4,rightMargin=40,leftMargin=40,topMargin=38,bottomMargin=42,
        title='SUMUWW '+kind,author='SUMUWW Explorer').build(story,onFirstPage=footer,onLaterPages=footer)
    return output.getvalue()
