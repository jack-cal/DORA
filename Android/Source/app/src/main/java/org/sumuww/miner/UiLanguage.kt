package org.sumuww.miner

import android.content.Context
import org.json.JSONObject

/** Android UI language selection; shared catalogs with the desktop app. */
object UiLanguage {
    val languages = linkedMapOf(
        "en" to "English", "fr" to "Français", "es" to "Español",
        "ar" to "العربية", "zh" to "中文（普通话）", "pt" to "Português",
        "ru" to "Русский", "de" to "Deutsch", "sw" to "Kiswahili",
        "hi" to "हिन्दी", "ko" to "한국어",
        "ja" to "日本語",
        "id" to "Bahasa Indonesia",
        "vi" to "Tiếng Việt",
        "tr" to "Türkçe",
        "th" to "ไทย",
        "it" to "Italiano",
        "bn" to "বাংলা",
        "ur" to "اردو",
        "pl" to "Polski",
        "nl" to "Nederlands",
        "fil" to "Filipino",
        "ta" to "தமிழ்",
        "zh-TW" to "繁體中文（台灣）",
        "zh-HK" to "繁體中文（香港）",
        "mn-Mong" to "Mongolian (traditional)",
        "mn" to "Монгол (Кирилл)",
        "sr" to "Српски",
        "sv" to "Svenska",
        "no" to "Norsk (bokmål)",
        "el" to "Ελληνικά",
        "fi" to "Suomi",
        "da" to "Dansk",
        "cs" to "Čeština"
    )
    private val catalogs = mutableMapOf<String, JSONObject>()
    private var mobileCatalog: JSONObject? = null

    private fun mobileData(context: Context): JSONObject = synchronized(catalogs) {
        mobileCatalog ?: JSONObject(context.assets.open("mobile_ui.json")
            .bufferedReader(Charsets.UTF_8).use { it.readText() }).also { mobileCatalog = it }
    }

    private fun mobileText(context: Context, language: String, source: String): String? = synchronized(catalogs) {
        val catalog = mobileData(context)
        val languages = catalog.getJSONArray("languages")
        val index = (0 until languages.length()).firstOrNull { languages.getString(it) == language }
            ?: return@synchronized null
        catalog.getJSONObject("strings").optJSONArray(source)?.optString(index)?.takeIf { it.isNotBlank() }
    }

    private val mobileEnglish = mapOf(
        "IP 보호" to "IP protection", "로컬 서비스 포트" to "Local router port",
        "Tor/I2P 로컬 서비스를 먼저 실행하세요. 연결 실패 시 직접 연결로 전환하지 않습니다. I2P는 b32.i2p 피어가 필요합니다." to "Tor and I2P are optional and bundled with SUMUWW. Only the selected router runs; Direct runs neither. No separate router installation or port setting is needed. If a private connection fails, it does not switch to Direct. I2P requires b32.i2p peers.",
        "복구 단어 표시" to "Show recovery words", "비밀번호가 일치하지 않습니다" to "The passwords do not match.",
        "연결된 노드" to "Connected peers", "지갑 잠금" to "Lock wallet",
        "업데이트 확인" to "Check for updates",
        "다운로드 페이지 열기" to "Open download page",
        "업데이트 페이지를 열 수 없습니다." to "Cannot open the update page.",
        "업데이트 주소가 아직 등록되지 않았습니다." to "The update source has not been configured yet.",
        "스토어에서 최신 버전을 확인하세요." to "Check the store for the latest version.",
        "기존 앱을 삭제하지 말고 새 APK를 덮어 설치하세요." to "Install the new APK over the existing app without uninstalling it.",
        "업데이트를 확인할 수 없습니다. 잠시 후 다시 시도하세요." to "Cannot check for updates. Please try again later.",
        "최근 활동" to "Recent activity", "거래 내역이 없습니다" to "No transactions yet",
        "전체 거래내역" to "All transactions", "네트워크 상태" to "Network status", "블록" to "blocks",
        "지갑을 열고 동기화된 노드에 연결해 시작하세요" to "Open your wallet and connect to a synchronized peer to start.",
        "완료 블록" to "blocks completed", "총 보유 자산" to "Total assets", "자산" to "Assets",
        "SMW 보유량" to "SMW balance", "보낼 수량" to "Amount to send", "사용 가능한 잔액" to "Available balance",
        "다음 화면에서 수수료와 전송 내용을 확인합니다" to "Review the fee and transfer details on the next screen.",
        "설정" to "Settings", "계정" to "Account", "보안 설정" to "Security", "채굴 설정" to "Mining settings",
        "알림 설정" to "Notifications", "앱 정보" to "App information", "앱 버전" to "App version",
        "지갑 비밀번호와 복구 단어를 안전하게 보관하세요" to "Keep your wallet password and recovery words safe.",
        "앱 알림" to "App notifications", "허용됨" to "Allowed", "허용되지 않음" to "Not allowed",
        "백그라운드 노드 및 채굴 상태는 Android 알림에 표시됩니다" to "Background node and mining status appear in the Android notification.",
        "Android 알림 설정 열기" to "Open Android notification settings", "색상 테마" to "Color themes",
        "라벤더" to "Lavender", "크리스마스" to "Christmas", "적용" to "Apply",
        "내 자산" to "My assets", "SMW와 함께" to "With SMW",
        "내 자산 총액" to "Total assets", "SMW 네트워크" to "SMW network",
        "동기화 완료" to "Synchronized", "동기화 대기" to "Waiting for sync",
        "오프라인 채굴" to "Offline mining", "로컬 체인 잔액" to "Local chain balance",
        "내 노드에서 블록을 검증하고 채굴하기" to "Verify and mine blocks on your node",
        "내 SMW" to "My SMW", "안내" to "Guide", "처음 사용 안내" to "First-use tour",
        "내 SMW 현황" to "Your SMW overview", "보내기" to "Send", "받기" to "Receive",
        "거래내역" to "History", "더보기" to "More", "주요 기능" to "Main features",
        "채굴 중" to "Mining", "채굴 대기" to "Ready to mine",
        "SMW 전송" to "Send SMW", "확인 화면에서 계산" to "Calculated on review",
        "내 SMW 주소" to "Your SMW address", "지갑을 먼저 열어 주세요" to "Open a wallet first",
        "이 주소로 받은 SMW는 블록에서 확인된 뒤 잔액에 표시됩니다." to "Incoming SMW appears in your balance after block confirmation.",
        "주소 복사" to "Copy address", "주소를 복사했습니다" to "Address copied", "공유하기" to "Share",
        "현재 지갑에서 확인된 거래" to "Transactions for this wallet", "전체" to "All",
        "불러오는 중" to "Loading", "해당 내역이 없습니다" to "No matching transactions", "새로고침" to "Refresh",
        "이전" to "Previous", "다음" to "Next", "설정 및 노드 관리" to "Settings and node",
        "화면 설정" to "Appearance", "라이트·다크" to "Light or dark",
        "테마 선택" to "Color theme", "노드 관리" to "Node settings",
        "상세 통계" to "Node details", "받는 주소와 금액을 입력하세요" to "Enter a recipient and amount",
        "최근 피어 연결 오류" to "Last peer connection error",
        "기본 · SMW" to "Default · SMW", "봄" to "Spring", "여름" to "Summer",
        "가을" to "Autumn", "겨울" to "Winter",
        "골드" to "Gold", "그린" to "Green", "네이비" to "Navy",
        "레드" to "Red", "민트" to "Mint", "시얀" to "Cyan",
        "블루" to "Blue", "실버" to "Silver", "오렌지" to "Orange",
        "퍼플" to "Purple", "핑크" to "Pink",
        "홈" to "Home", "통계" to "Statistics", "언어" to "Language", "SMW 모바일 노드" to "SMW mobile node",
        "테마" to "Appearance", "시스템 설정" to "Use device setting", "라이트 모드" to "Light mode", "다크 모드" to "Dark mode",
        "총 보유량" to "Total balance", "연결 피어" to "Connected peers", "상태 확인 불가" to "Status unavailable",
        "동기화" to "Synchronization", "현재 블록 보상" to "Block reward",
        "상태 새로고침" to "Refresh status", "CPU 사용률" to "CPU usage",
        "채굴 시간" to "Mining time", "진행 블록" to "Blocks completed",
        "채굴 준비" to "Mining readiness", "준비됨" to "Ready", "대기" to "Waiting",
        "채굴할 블록 수를 지정해 시작" to "Choose the number of blocks to mine",
        "휴대폰에서 SMW 블록을 탐색 중" to "Mining SMW blocks on this phone",
        "● 채굴 중" to "● Mining", "채굴 중지" to "Stop mining",
        "채굴할 블록 수 (1–10000)" to "Blocks to mine (1–10000)",
        "1–10000 사이 블록 수를 입력하세요." to "Enter 1–10000 blocks.",
        "현재 노드에서 확인 가능한 실제 값" to "Actual values reported by this node",
        "동기화 피어" to "Synchronized peers", "다음 난이도 bits" to "Next difficulty bits",
        "이번 채굴 완료" to "Blocks mined in this batch", "이번 채굴 목표" to "Batch target",
        "채굴 상태" to "Mining status", "최근 블록" to "Latest block",
        "SMW 자산 및 지갑 관리" to "SMW wallet and funds", "대기 중" to "Pending",
        "주소" to "Address", "SMW 보내기" to "Send SMW",
        "지갑 열기 / 생성 / 복구" to "Open, create or recover wallet",
        "최근 거래" to "Recent transactions", "복구 단어 보기" to "Show recovery words",
        "암호화 백업 내보내기" to "Export encrypted backup",
        "암호화 백업 가져오기" to "Import encrypted backup",
        "24개 복구 단어" to "24 recovery words", "24개 복구 단어 저장" to "Save 24 recovery words",
        "스크린샷 허용" to "Allow screenshot", "오프라인에 안전하게 보관하세요. 누구든 이 단어를 알면 SMW를 사용할 수 있습니다." to
            "Store these words safely offline. Anyone with them can spend your SMW.",
        "피어 추가" to "Add peer", "SMW 피어 추가" to "Add SMW peer",
        "SMW 관리" to "SMW settings", "지갑 관리" to "Wallet management",
        "파일 선택" to "Select file", "전송 확인" to "Review transfer",
        "수수료 확인" to "Review fee", "받는 SMW 주소" to "Recipient SMW address",
        "기존 지갑이 있습니다. 먼저 백업하세요." to "An existing wallet is present. Back it up first.",
        "먼저 지갑을 생성하거나 복구하세요." to "Create or recover a wallet first.",
        "암호화 지갑 백업을 저장했습니다." to "Encrypted wallet backup saved.",
        "복구 시 24개 단어" to "24 words for recovery",
        "복원할 지갑 비밀번호" to "Password for restored wallet",
        "지갑 비밀번호 (12자 이상)" to "Wallet password (12+ characters)",
        "Peer IP 또는 domain:port" to "Peer IP or domain:port",
        "받는 주소" to "Recipient address", "금액" to "Amount SMW",
        "현지 대기 수수료" to "Local queue: {0} vB · {1} yugeon/vB · target: {2} blocks",
        "수수료율 (yugeon/vB)" to "Fee rate (yugeon/vB)", "느림" to "Slow", "보통" to "Normal", "빠름" to "Fast",
        "수수료율과 지갑의 수수료 한도를 확인하세요." to "Check the fee rate and wallet limits.",
        "수수료" to "Fee SMW", "합계" to "Total debit",
        "열기" to "Open", "추가" to "Add", "전송" to "Send",
        "확인" to "Confirm", "복구" to "Restore", "새 지갑" to "New wallet",
        "닫기" to "Close", "취소" to "Cancel"
    )

    fun code(context: Context): String = context.getSharedPreferences("sumuww-ui", Context.MODE_PRIVATE)
        .getString("language", "en")?.takeIf { it in languages } ?: "en"

    fun set(context: Context, language: String) {
        require(language in languages)
        context.getSharedPreferences("sumuww-ui", Context.MODE_PRIVATE)
            .edit().putString("language", language).apply()
        LocaleBrand.syncLauncher(context, language)
    }

    private fun catalog(context: Context, language: String): JSONObject = synchronized(catalogs) {
        catalogs.getOrPut(language) {
            JSONObject(context.assets.open("locales/$language.json").bufferedReader(Charsets.UTF_8).use { it.readText() })
        }
    }

    fun text(context: Context, korean: String): String {
        val language = code(context)
        if (language == "ko") {
            return mobileData(context).optJSONObject("korean_overrides")
                ?.optString(korean)?.takeIf { it.isNotBlank() } ?: korean
        }
        mobileText(context, language, korean)?.let { return it }
        val ko = catalog(context, "ko")
        val keys = ko.keys()
        var english: String? = mobileData(context).optJSONObject("source_keys")
            ?.optString(korean)?.takeIf { it.isNotBlank() }
        while (english == null && keys.hasNext()) {
            val key = keys.next()
            if (ko.optString(key) == korean) { english = key; break }
        }
        val base = english ?: mobileEnglish[korean] ?: korean
        return catalog(context, language).optString(base, base)
    }
}
