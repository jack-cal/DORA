"""Directly authored edition captions. No external translation service."""
KEYS = 'Bitcoin: full node|Bitcoin: light client|Bitcoin server|Light mode checks proofs but relies on servers for complete transaction history.|Bitcoin headers'.split('|')
ROWS = {
'en': '|'.join(KEYS),
'ko': '비트코인: 풀노드 방식|비트코인: 경량 방식|비트코인 서버|경량 방식은 증명을 검사하지만, 거래 내역이 빠짐없이 제공되는지는 서버에 의존합니다.|비트코인 블록 헤더',
'ja': 'ビットコイン：フルノード方式|ビットコイン：軽量方式|ビットコインサーバー|軽量方式は証明を検証しますが、取引履歴がすべて提供されるかはサーバーに依存します。|ビットコインのブロックヘッダー',
'zh': '比特币：全节点模式|比特币：轻客户端模式|比特币服务器|轻客户端会验证证明，但仍依赖服务器提供完整的交易记录。|比特币区块头',
'zh-TW': '比特幣：完整節點模式|比特幣：輕量模式|比特幣伺服器|輕量模式會驗證證明，但仍依賴伺服器提供完整的交易紀錄。|比特幣區塊標頭',
'zh-HK': '比特幣：完整節點模式|比特幣：輕量模式|比特幣伺服器|輕量模式會驗證證明，但仍依賴伺服器提供完整的交易紀錄。|比特幣區塊標頭',
'fr': 'Bitcoin : nœud complet|Bitcoin : client léger|Serveur Bitcoin|Le mode léger vérifie les preuves, mais dépend des serveurs pour obtenir tout l’historique des transactions.|En-têtes Bitcoin',
'es': 'Bitcoin: nodo completo|Bitcoin: cliente ligero|Servidor Bitcoin|El modo ligero verifica las pruebas, pero depende de los servidores para obtener el historial completo de transacciones.|Cabeceras de Bitcoin',
'ar': 'بيتكوين: عقدة كاملة|بيتكوين: عميل خفيف|خادم بيتكوين|يتحقق الوضع الخفيف من الإثباتات، لكنه يعتمد على الخوادم للحصول على سجل المعاملات كاملاً.|ترويسات كتل بيتكوين',
'pt': 'Bitcoin: nó completo|Bitcoin: cliente leve|Servidor Bitcoin|O modo leve verifica as provas, mas depende dos servidores para obter o histórico completo de transações.|Cabeçalhos Bitcoin',
'ru': 'Биткоин: полный узел|Биткоин: лёгкий клиент|Сервер Биткоина|Лёгкий режим проверяет доказательства, но полнота истории транзакций зависит от серверов.|Заголовки блоков Биткоина',
'de': 'Bitcoin: vollständiger Knoten|Bitcoin: schlanker Client|Bitcoin-Server|Der schlanke Modus prüft Nachweise, ist für eine vollständige Transaktionshistorie jedoch auf Server angewiesen.|Bitcoin-Blockheader',
'sw': 'Bitcoin: nodi kamili|Bitcoin: programu nyepesi|Seva ya Bitcoin|Hali nyepesi hukagua uthibitisho, lakini hutegemea seva kutoa historia yote ya miamala.|Vichwa vya vitalu vya Bitcoin',
'hi': 'बिटकॉइन: पूर्ण नोड|बिटकॉइन: हल्का क्लाइंट|बिटकॉइन सर्वर|हल्का मोड प्रमाणों की जाँच करता है, लेकिन लेनदेन का पूरा इतिहास पाने के लिए सर्वरों पर निर्भर है।|बिटकॉइन ब्लॉक हेडर',
'id': 'Bitcoin: node penuh|Bitcoin: klien ringan|Server Bitcoin|Mode ringan memeriksa bukti, tetapi bergantung pada server untuk mendapatkan riwayat transaksi yang lengkap.|Header blok Bitcoin',
'vi': 'Bitcoin: nút đầy đủ|Bitcoin: ứng dụng nhẹ|Máy chủ Bitcoin|Chế độ nhẹ kiểm tra bằng chứng nhưng phụ thuộc vào máy chủ để nhận đầy đủ lịch sử giao dịch.|Tiêu đề khối Bitcoin',
'tr': 'Bitcoin: tam düğüm|Bitcoin: hafif istemci|Bitcoin sunucusu|Hafif mod kanıtları doğrular, ancak işlem geçmişinin eksiksiz olması için sunuculara bağımlıdır.|Bitcoin blok başlıkları',
'th': 'บิตคอยน์: โหนดเต็ม|บิตคอยน์: ไคลเอนต์ขนาดเบา|เซิร์ฟเวอร์บิตคอยน์|โหมดขนาดเบาตรวจสอบหลักฐาน แต่ยังต้องพึ่งเซิร์ฟเวอร์เพื่อให้ได้ประวัติธุรกรรมครบถ้วน|ส่วนหัวบล็อกบิตคอยน์',
'it': 'Bitcoin: nodo completo|Bitcoin: client leggero|Server Bitcoin|La modalità leggera verifica le prove, ma dipende dai server per ottenere la cronologia completa delle transazioni.|Intestazioni dei blocchi Bitcoin',
'bn': 'বিটকয়েন: পূর্ণ নোড|বিটকয়েন: লাইট ক্লায়েন্ট|বিটকয়েন সার্ভার|লাইট মোড প্রমাণ যাচাই করে, তবে লেনদেনের সম্পূর্ণ ইতিহাস পেতে সার্ভারের ওপর নির্ভর করে।|বিটকয়েন ব্লক হেডার',
'ur': 'بٹ کوائن: مکمل نوڈ|بٹ کوائن: ہلکا کلائنٹ|بٹ کوائن سرور|ہلکا موڈ ثبوتوں کی جانچ کرتا ہے، لیکن لین دین کی مکمل تاریخ حاصل کرنے کے لیے سرورز پر انحصار کرتا ہے۔|بٹ کوائن بلاک ہیڈر',
'pl': 'Bitcoin: pełny węzeł|Bitcoin: lekki klient|Serwer Bitcoin|Tryb lekki weryfikuje dowody, ale kompletność historii transakcji zależy od serwerów.|Nagłówki bloków Bitcoin',
'nl': 'Bitcoin: volledige node|Bitcoin: lichte client|Bitcoin-server|De lichte modus controleert bewijzen, maar is afhankelijk van servers voor de volledige transactiegeschiedenis.|Bitcoin-blokheaders',
'fil': 'Bitcoin: buong node|Bitcoin: magaan na client|Bitcoin server|Sinusuri ng magaan na mode ang mga patunay, ngunit umaasa ito sa mga server para sa kumpletong kasaysayan ng transaksyon.|Mga header ng bloke ng Bitcoin',
'ta': 'பிட்காயின்: முழு முனை|பிட்காயின்: இலகு செயலி|பிட்காயின் சேவையகம்|இலகு முறை சான்றுகளைச் சரிபார்க்கிறது; ஆனால் முழு பரிவர்த்தனை வரலாற்றைப் பெற சேவையகங்களைச் சார்ந்துள்ளது.|பிட்காயின் தொகுதித் தலைப்புகள்',
'mn': 'Биткойн: бүрэн зангилаа|Биткойн: хөнгөн клиент|Биткойны сервер|Хөнгөн горим нотолгоог шалгадаг боловч гүйлгээний түүхийг бүрэн авахын тулд серверүүдэд найддаг.|Биткойны блокийн толгой',
'mn-Mong': 'Bitcoin: ᠪᠦᠷᠢᠨ ᠵᠠᠩᠭᠢᠯᠠᠭ᠎ᠠ|Bitcoin: ᠬᠥᠩᠭᠡᠨ ᠺᠯᠢᠶᠧᠨᠲ|Bitcoin ᠰᠧᠷᠸᠧᠷ|ᠬᠥᠩᠭᠡᠨ ᠭᠣᠷᠢᠮ ᠨᠣᠲᠠᠯᠭ᠎ᠠ ᠶᠢ ᠰᠢᠯᠭᠠᠳᠠᠭ᠃ ᠭᠡᠪᠡᠴᠦ ᠭᠦᠶᠦᠯᠭᠡᠭᠡ ᠶᠢᠨ ᠲᠡᠦᠬᠡ ᠶᠢ ᠪᠦᠷᠢᠨ ᠠᠪᠬᠤ ᠳᠤ ᠰᠧᠷᠸᠧᠷ ᠲᠦ ᠲᠦᠰᠢᠭᠯᠡᠳᠡᠭ᠃|Bitcoin ᠪᠯᠣᠺ ᠤᠨ ᠲᠣᠯᠤᠭᠠᠢ',
'sr': 'Биткоин: пуни чвор|Биткоин: лаки клијент|Биткоин сервер|Лаки режим проверава доказе, али се за потпуну историју трансакција ослања на сервере.|Заглавља Биткоин блокова',
'sv': 'Bitcoin: fullständig nod|Bitcoin: lätt klient|Bitcoin-server|Det lätta läget kontrollerar bevis men är beroende av servrar för en fullständig transaktionshistorik.|Bitcoin-blockhuvuden',
'no': 'Bitcoin: full node|Bitcoin: lett klient|Bitcoin-server|Lett modus kontrollerer bevis, men er avhengig av servere for å få hele transaksjonshistorikken.|Bitcoin-blokkhoder',
'el': 'Bitcoin: πλήρης κόμβος|Bitcoin: ελαφρύς πελάτης|Διακομιστής Bitcoin|Η ελαφριά λειτουργία ελέγχει τις αποδείξεις, αλλά εξαρτάται από διακομιστές για το πλήρες ιστορικό συναλλαγών.|Κεφαλίδες μπλοκ Bitcoin',
'fi': 'Bitcoin: täysi solmu|Bitcoin: kevyt asiakas|Bitcoin-palvelin|Kevyt tila tarkistaa todisteet, mutta on riippuvainen palvelimista saadakseen täydellisen tapahtumahistorian.|Bitcoin-lohkojen otsakkeet',
'da': 'Bitcoin: fuld node|Bitcoin: let klient|Bitcoin-server|Let tilstand kontrollerer beviser, men er afhængig af servere for at få hele transaktionshistorikken.|Bitcoin-blokhoveder',
'cs': 'Bitcoin: plný uzel|Bitcoin: lehký klient|Bitcoinový server|Lehký režim ověřuje důkazy, ale úplnost historie transakcí závisí na serverech.|Hlavičky bitcoinových bloků',
}


def extend(result):
    assert set(ROWS) == set(result)
    for code, row in ROWS.items():
        values = row.split('|')
        assert len(values) == len(KEYS), code
        result[code].update(zip(KEYS, values))
