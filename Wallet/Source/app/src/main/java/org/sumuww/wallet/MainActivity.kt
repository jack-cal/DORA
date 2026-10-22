package org.sumuww.wallet

import android.app.Activity
import android.app.AlertDialog
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Color
import android.graphics.Typeface
import android.graphics.drawable.GradientDrawable
import android.net.Uri
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.text.InputFilter
import android.text.InputType
import android.text.Editable
import android.text.TextWatcher
import android.util.Base64
import android.view.Gravity
import android.view.View
import android.view.WindowManager
import android.view.inputmethod.InputMethodManager
import android.widget.*
import com.google.zxing.*
import com.google.zxing.common.HybridBinarizer
import com.google.zxing.qrcode.QRCodeWriter
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.math.BigDecimal
import java.util.Locale

class MainActivity : Activity() {
    private val handler = Handler(Looper.getMainLooper())
    private val preferences by lazy { getSharedPreferences("wallet-ui", MODE_PRIVATE) }
    private var state = JSONObject()
    private var resumed = false
    private var working = false
    private var epoch = 0
    private var page = "wallet"
    private var dialog: AlertDialog? = null
    private var secretFields = mutableListOf<EditText>()
    private var statusLabel: TextView? = null
    private var amountLabel: TextView? = null
    private var pendingLabel: TextView? = null
    private var immatureLabel: TextView? = null
    private var recent: LinearLayout? = null
    private var historyList: LinearLayout? = null
    private var historyLoading = false
    private var statusLoading = false
    private var addressInput: EditText? = null
    private var amountInput: EditText? = null
    private var feeInput: EditText? = null
    private var sendAmount = ""
    private var sendAddress = ""
    private var sendFee = ""
    private var historyOffset = 0
    private var pendingExport: ByteArray? = null
    private var pendingImport: Pair<Int, ByteArray>? = null
    private lateinit var root: LinearLayout
    private lateinit var body: LinearLayout
    private val blue = Color.rgb(52, 94, 235)
    private val muted get() = if (dark) Color.rgb(164, 178, 204) else Color.rgb(111, 126, 152)
    private val ink get() = if (dark) Color.rgb(237, 242, 255) else Color.rgb(23, 43, 76)
    private val background get() = if (dark) Color.rgb(13, 22, 39) else Color.rgb(246, 248, 252)
    private val surface get() = if (dark) Color.rgb(25, 39, 61) else Color.WHITE
    private val dark get() = preferences.getBoolean("dark", false)
    private val language get() = WalletLanguages.code(this)
    private fun t(ko: String, en: String) = WalletLanguages.text(this, ko, en)
    private fun tf(source: String, vararg args: Any) = WalletLanguages.format(this, source, *args)
    private fun dp(value: Int) = (value * resources.displayMetrics.density).toInt()
    private fun wallet() = state.optJSONObject("wallet")
    private fun address() = wallet()?.optString("address").orEmpty()
    private fun unlocked() = wallet()?.optBoolean("unlocked") == true
    private val poll = object : Runnable {
        override fun run() {
            if (!resumed) return
            if (!working) readState()
            handler.postDelayed(this, 4000)
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
        render()
    }
    override fun onResume() {
        super.onResume()
        resumed = true
        val token = epoch
        WalletRuntime.executor.execute {
            try {
                WalletRuntime.start(this)
                WalletRuntime.call("foreground", "true")
                WalletRuntime.call("timeout", preferences.getInt("timeout", 300).toString())
                val value = WalletRuntime.call("status")
                handler.post {
                    if (resumed && epoch == token) { state = value; render(); presentImport() }
                }
            } catch (_: Exception) {
                handler.post { if (resumed) alert(t("시작 오류", "Startup error"), t("지갑을 시작하지 못했습니다. 앱을 다시 열어 주세요.", "The wallet could not start. Reopen the app.")) }
            }
        }
        handler.postDelayed(poll, 4000)
    }
    override fun onPause() {
        if (page == "send") {
            addressInput?.let { sendAddress = it.text.toString() }
            amountInput?.let { sendAmount = it.text.toString() }
            feeInput?.let { sendFee = it.text.toString() }
        }
        resumed = false
        epoch++
        handler.removeCallbacks(poll)
        dialog?.dismiss()
        dialog = null
        secretFields.forEach { it.text.clear() }
        secretFields.clear()
        pendingExport = null
        pendingImport = null
        WalletRuntime.executor.execute { runCatching { WalletRuntime.call("foreground", "false") } }
        super.onPause()
    }
    override fun onUserInteraction() {
        super.onUserInteraction()
        if (resumed && !working) WalletRuntime.executor.execute { runCatching { WalletRuntime.call("activity") } }
    }
    private fun readState() {
        if (statusLoading) return
        statusLoading = true
        val token = epoch
        WalletRuntime.executor.execute {
            val result = runCatching { WalletRuntime.call("status") }
            handler.post {
                statusLoading = false
                if (!resumed || epoch != token) return@post
                result.onSuccess { value ->
                    val wasUnlocked = unlocked()
                    val oldIdentity = address() + ":" + unlocked() + ":" + state.optBoolean("wallet_exists")
                    state = value
                    if (wasUnlocked && !unlocked()) dialog?.dismiss()
                    val newIdentity = address() + ":" + unlocked() + ":" + state.optBoolean("wallet_exists")
                    if (oldIdentity != newIdentity && page != "send") render() else refreshLabels()
                }.onFailure { statusLabel?.text = t("연결 상태를 확인하지 못했습니다", "Connection status unavailable") }
            }
        }
    }
    private fun work(method: String, vararg args: String, done: (JSONObject) -> Unit) {
        if (working) { toast(t("처리 중입니다", "Working…")); return }
        working = true
        val token = epoch
        WalletRuntime.executor.execute {
            val result = runCatching { WalletRuntime.call(method, *args) }
            if (method == "submit") {
                val saved = result.getOrElse { JSONObject().put("outcome", "unknown") }
                preferences.edit().putString("last-transfer", saved.toString()).apply()
            }
            val snapshot = runCatching { WalletRuntime.call("status") }.getOrNull()
            handler.post {
                working = false
                snapshot?.let { state = it }
                if (!resumed || epoch != token) return@post
                result.onSuccess(done).onFailure { error ->
                    alert(t("확인", "Check"), friendly(error.message.orEmpty()))
                }
            }
        }
    }
    private fun friendly(message: String): String {
        val lower = message.lowercase()
        return when {
            "password" in lower && "at least 12" in lower -> t("비밀번호는 12자 이상 입력해 주세요.", "Enter a password of at least 12 characters.")
            "authentication" in lower || "password or" in lower || "decrypt" in lower -> t("비밀번호 또는 백업 파일을 확인해 주세요.", "Check the password or backup file.")
            "different network" in lower || "address" in lower -> t("SUMUWW 받는 주소 전체를 확인해 주세요.", "Check the complete SUMUWW receiving address.")
            "insufficient" in lower -> t("수량과 수수료를 지불할 사용 가능 잔액이 부족합니다.", "Insufficient available balance for the amount and fee.")
            "unlock" in lower -> t("지갑 잠금을 해제한 뒤 다시 확인해 주세요.", "Unlock the wallet and try again.")
            "mnemonic" in lower || "recovery word" in lower -> t("복구 단어와 순서를 확인해 주세요.", "Check the recovery words and their order.")
            "amount" in lower -> t("수량을 확인해 주세요. 소수점은 최대 8자리입니다.", "Check the amount. Up to eight decimal places are supported.")
            "quote" in lower -> t("송금 확인이 만료되었습니다. 다시 확인해 주세요.", "The transfer review expired. Review it again.")
            else -> message
        }
    }

    private fun shape(color: Int, radius: Int = 20): GradientDrawable = GradientDrawable().apply {
        setColor(color); cornerRadius = dp(radius).toFloat()
    }
    private fun label(value: String, size: Int = 15, color: Int = ink, bold: Boolean = false): TextView = (if (language == "mn-Mong") SumuwwVerticalTextView(this) else TextView(this)).apply {
        text = value; textSize = size.toFloat(); setTextColor(color)
        if (bold) typeface = Typeface.create("sans-serif", Typeface.BOLD)
        setLineSpacing(dp(3).toFloat(), 1f)
        SumuwwVerticalCaptions.watch(this)
    }
    private fun column() = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL }
    private fun gap(container: LinearLayout, height: Int = 14) { container.addView(View(this), LinearLayout.LayoutParams(1, dp(height))) }
    private fun add(container: LinearLayout, view: View, height: Int = LinearLayout.LayoutParams.WRAP_CONTENT) {
        container.addView(view, LinearLayout.LayoutParams(-1, if (height >= 0) dp(height) else height))
    }
    private fun card(container: LinearLayout): LinearLayout = column().also {
        it.background = shape(surface); it.setPadding(dp(20), dp(20), dp(20), dp(20)); add(container, it); gap(container)
    }
    private fun button(value: String, primary: Boolean = true, action: () -> Unit): Button = Button(this).apply {
        text = value; isAllCaps = false; textSize = 15f; typeface = Typeface.create("sans-serif-medium", 0)
        minHeight = dp(50); minimumHeight = dp(50)
        background = shape(if (primary) blue else if (dark) Color.rgb(38, 55, 81) else Color.rgb(234, 240, 255), 15)
        setTextColor(if (primary) Color.WHITE else ink)
        setOnClickListener { if (!working) action() else toast(t("처리 중입니다", "Working…")) }
        SumuwwVerticalCaptions.watch(this)
    }
    private fun input(hint: String, password: Boolean = false, multiline: Boolean = false, sensitive: Boolean = password): EditText = EditText(this).apply {
        this.hint = hint; textSize = 16f; setTextColor(ink); setHintTextColor(muted)
        setPadding(dp(14), dp(12), dp(14), dp(12)); background = shape(this@MainActivity.background, 12)
        inputType = if (password) InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_VARIATION_PASSWORD else
            InputType.TYPE_CLASS_TEXT or InputType.TYPE_TEXT_FLAG_NO_SUGGESTIONS or if (multiline) InputType.TYPE_TEXT_FLAG_MULTI_LINE else 0
        maxLines = if (multiline) 5 else 1
        filters = arrayOf(InputFilter.LengthFilter(if (multiline) 1024 else 256))
        isSaveEnabled = false; importantForAutofill = View.IMPORTANT_FOR_AUTOFILL_NO_EXCLUDE_DESCENDANTS
        if (sensitive) secretFields.add(this)
    }
    private fun dialogBody() = column().apply { setPadding(dp(24), dp(12), dp(24), dp(20)); setBackgroundColor(surface) }
    private fun showDialog(title: String, content: View, positive: String? = null, onPositive: (() -> Unit)? = null): AlertDialog {
        dialog?.dismiss()
        val builder = SumuwwVerticalCaptions.builder(this).setTitle(title).setView(content).setNegativeButton(t("닫기", "Close"), null)
        if (positive != null) builder.setPositiveButton(positive, null)
        return builder.create().also { created ->
            dialog = created
            created.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
            created.setOnDismissListener { secretFields.forEach { it.text.clear() }; secretFields.clear(); if (dialog === created) dialog = null }
            created.show()
            created.window?.addFlags(WindowManager.LayoutParams.FLAG_SECURE)
            if (positive != null) created.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener { if (!working) onPositive?.invoke() }
        }
    }
    private fun alert(title: String, message: String) {
        val content = dialogBody(); add(content, label(message)); showDialog(title, content)
    }
    private fun toast(value: String) { Toast.makeText(this, value, Toast.LENGTH_SHORT).show() }
    private fun copy(value: String) {
        (getSystemService(CLIPBOARD_SERVICE) as ClipboardManager).setPrimaryClip(ClipData.newPlainText("SUMUWW", value))
        toast(t("복사했습니다", "Copied"))
    }
    private fun render() {
        window.decorView.layoutDirection = if (language in setOf("ar", "ur")) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
        statusLabel = null; amountLabel = null; pendingLabel = null; immatureLabel = null; recent = null; historyList = null; addressInput = null; amountInput = null; feeInput = null
        root = column().apply { setBackgroundColor(this@MainActivity.background) }
        root.setOnApplyWindowInsetsListener { view, insets ->
            view.setPadding(0, insets.systemWindowInsetTop, 0, insets.systemWindowInsetBottom); insets
        }
        setContentView(root)
        window.statusBarColor = background; window.navigationBarColor = background
        window.decorView.systemUiVisibility = if (dark) 0 else View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR
        val header = LinearLayout(this).apply { gravity = Gravity.CENTER_VERTICAL; setPadding(dp(22), dp(10), dp(22), dp(12)) }
        header.addView(ImageView(this).apply { setImageResource(R.drawable.sumuww_ui_logo); scaleType = ImageView.ScaleType.FIT_CENTER }, LinearLayout.LayoutParams(dp(47), dp(47)))
        header.addView(label("SUMUWW", 21, ink, true), LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = dp(12) })
        header.addView(button(if (unlocked()) t("잠금", "Lock") else "SMW", false) {
            if (unlocked()) work("lock") { render() }
        }, LinearLayout.LayoutParams(dp(74), LinearLayout.LayoutParams.WRAP_CONTENT))
        add(root, header)
        val scroll = ScrollView(this).apply { isFillViewport = true; clipToPadding = false }
        body = column().apply { setPadding(dp(22), dp(8), dp(22), dp(20)) }
        scroll.addView(body)
        root.addView(scroll, LinearLayout.LayoutParams(-1, 0, 1f))
        when (page) { "history" -> historyPage(); "settings" -> settingsPage(); "send" -> sendPage(); else -> walletPage() }
        val tabs = LinearLayout(this).apply { setBackgroundColor(surface); setPadding(dp(14), dp(10), dp(14), dp(10)) }
        listOf("wallet" to t("지갑", "Wallet"), "history" to t("내역", "Activity"), "settings" to t("설정", "Settings")).forEach { (key, value) ->
            tabs.addView(button(value, page == key) { page = key; render() }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { leftMargin = dp(4); rightMargin = dp(4) })
        }
        add(root, tabs)
        refreshLabels()
    }
    private fun networkLine(container: LinearLayout) {
        statusLabel = label("", 13, muted)
        add(container, statusLabel!!)
    }
    private fun walletPage() {
        if (wallet() == null) {
            gap(body, 25)
            add(body, label(t("나의 SUMUWW 지갑", "Your SUMUWW wallet"), 29, ink, true)); gap(body)
            add(body, label(t("SMW를 받고 보내세요.", "Receive and send SMW."), 17, muted)); gap(body, 26)
            val panel = card(body)
            if (!state.has("wallet_exists")) add(panel, label(t("지갑을 시작하고 있습니다…", "Starting your wallet…"), 16))
            else if (state.optBoolean("wallet_exists")) {
                add(panel, label(t("저장된 지갑", "Saved wallet"), 19, ink, true)); gap(panel)
                add(panel, button(t("잠금 해제", "Unlock wallet")) { passwordDialog("unlock") { page = "wallet"; render() } })
            } else {
                add(panel, button(t("새 지갑 만들기", "Create a wallet")) { createDialog(false) }); gap(panel)
                add(panel, button(t("복구 단어로 복원", "Restore recovery words"), false) { createDialog(true) }); gap(panel)
                add(panel, button(t("암호화 백업 가져오기", "Import encrypted backup"), false) { pickFile(IMPORT_BACKUP, "application/json") })
            }
            networkLine(body)
            return
        }
        val hero = card(body)
        hero.background = GradientDrawable(GradientDrawable.Orientation.TL_BR, intArrayOf(Color.rgb(48, 88, 223), Color.rgb(90, 77, 226))).apply { cornerRadius = dp(24).toFloat() }
        add(hero, label(t("사용 가능한 잔액", "Available balance"), 14, Color.rgb(222, 231, 255)))
        gap(hero, 10)
        amountLabel = label("", 35, Color.WHITE, true); add(hero, amountLabel!!)
        add(hero, label("SMW", 16, Color.rgb(222, 231, 255))); gap(hero, 16)
        add(hero, label(address().take(18) + "…" + address().takeLast(8), 13, Color.WHITE))
        gap(body, 5)
        val actions = LinearLayout(this)
        actions.addView(button(t("↑  보내기", "↑  Send")) {
            if (!unlocked()) passwordDialog("unlock") { page = "send"; render() } else { page = "send"; render() }
        }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { rightMargin = dp(7) })
        actions.addView(button(t("↓  받기", "↓  Receive"), false) { receiveDialog() }, LinearLayout.LayoutParams(0, LinearLayout.LayoutParams.WRAP_CONTENT, 1f).apply { leftMargin = dp(7) })
        add(body, actions); gap(body, 22)
        val details = card(body)
        pendingLabel = label(""); add(details, pendingLabel!!); gap(details, 10)
        immatureLabel = label("", 14, muted); add(details, immatureLabel!!)
        networkLine(details)
        gap(body, 5); add(body, label(t("최근 거래", "Recent activity"), 20, ink, true)); gap(body)
        recent = column(); add(body, recent!!)
        if (!unlocked()) {
            gap(body); add(body, button(t("지갑 잠금 해제", "Unlock wallet"), false) { passwordDialog("unlock") { render() } })
        }
    }
    private fun refreshLabels() {
        val node = state.optJSONObject("node")
        statusLabel?.text = if (node == null) t("연결 중…", "Connecting…") else
            tf("Peers: {0} · Block: {1} · ", node.optInt("peers"), node.optInt("height")) +
                when (node.optString("sync_state")) {
                    "synced", "synchronized", "ready" -> t("동기화 완료", "Synchronized")
                    "syncing", "updating" -> t("동기화 중", "Synchronizing")
                    else -> if (node.optInt("peers") == 0) t("피어 연결 대기", "Waiting for peers") else node.optString("sync_state")
                }
        wallet()?.let {
            amountLabel?.text = it.optString("available_dora", "0")
            pendingLabel?.text = t("미확인 잔액 변화", "Unconfirmed change") + "   " + it.optString("pending_dora", "0") + " SMW"
            immatureLabel?.text = t("미성숙 채굴 보상", "Immature mining rewards") + "   " + it.optString("immature_dora", "0") + " SMW"
        }
        recent?.let { container ->
            container.removeAllViews()
            val transactions = state.optJSONArray("transactions")
            if (transactions == null || transactions.length() == 0) add(container, label(t("아직 거래 내역이 없습니다.", "No transactions yet."), 15, muted))
            else for (i in 0 until minOf(transactions.length(), 5)) transactionRow(container, transactions.getJSONObject(i))
        }
        if (page == "history") historyList?.let { loadHistory(it) }
    }
    private fun createDialog(recover: Boolean) {
        val panel = dialogBody()
        val password = input(t("비밀번호 (12자 이상)", "Password (12+ characters)"), true)
        val confirm = input(t("비밀번호 확인", "Confirm password"), true)
        add(panel, password); gap(panel); add(panel, confirm)
        val words = if (recover) input(t("복구 단어를 순서대로 입력", "Recovery words in order"), multiline = true, sensitive = true) else null
        words?.let { gap(panel); add(panel, it) }
        showDialog(if (recover) t("지갑 복원", "Restore wallet") else t("새 지갑", "New wallet"), panel, t("계속", "Continue")) {
            val pass = password.text.toString()
            if (pass.length < 12 || pass != confirm.text.toString()) { toast(t("12자 이상 비밀번호와 확인을 일치시켜 주세요.", "Use a matching password of at least 12 characters.")); return@showDialog }
            val phrase = words?.text.toString()
            work(if (recover) "recover" else "create", *if (recover) arrayOf(pass, phrase) else arrayOf(pass)) {
                dialog?.dismiss(); page = "wallet"; render()
                if (!recover) work("phrase", pass) { result -> phraseDialog(result.optString("words")) }
            }
        }
    }
    private fun passwordDialog(method: String, callback: (JSONObject) -> Unit) {
        val panel = dialogBody()
        val password = input(t("지갑 비밀번호", "Wallet password"), true)
        add(panel, password)
        showDialog(t("비밀번호 확인", "Confirm password"), panel, t("확인", "Continue")) {
            work(method, password.text.toString()) { result -> dialog?.dismiss(); callback(result) }
        }
    }
    private fun phraseDialog(words: String) {
        val panel = dialogBody()
        add(panel, label(t("단어를 순서대로 기록하고 안전하게 보관하세요.", "Record the words in order and store them securely."), 14, muted)); gap(panel)
        val numbered = words.split(" ").mapIndexed { index, word -> "${index + 1}. $word" }.chunked(3).joinToString("\n") { it.joinToString("    ") }
        val secret = label(numbered, 16, ink, true)
        add(panel, secret)
        val created = showDialog(t("복구 단어", "Recovery words"), panel)
        created.setOnDismissListener { secret.text = ""; if (dialog === created) dialog = null }
    }
    private fun receiveDialog() {
        val value = address()
        if (value.isEmpty()) return
        val panel = dialogBody()
        val bitmap = qr(value)
        val image = ImageView(this).apply { setImageBitmap(bitmap); setBackgroundColor(Color.WHITE); contentDescription = "SUMUWW address QR"; scaleType = ImageView.ScaleType.FIT_CENTER }
        add(panel, image, 235); gap(panel)
        add(panel, label(value, 14).apply { setTextIsSelectable(true) }); gap(panel)
        add(panel, label(t("SUMUWW (SMW) 받는 주소", "SUMUWW (SMW) receiving address"), 13, muted)); gap(panel)
        add(panel, button(t("주소 복사", "Copy address")) { copy(value) }); gap(panel)
        add(panel, button(t("주소 공유", "Share address"), false) {
            startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).apply { type = "text/plain"; putExtra(Intent.EXTRA_TEXT, value) }, t("받는 주소 공유", "Share address")))
        })
        showDialog(t("SMW 받기", "Receive SMW"), panel)
    }
    private fun qr(value: String): Bitmap {
        val matrix = QRCodeWriter().encode(value, BarcodeFormat.QR_CODE, 720, 720, mapOf(EncodeHintType.MARGIN to 4))
        return Bitmap.createBitmap(720, 720, Bitmap.Config.ARGB_8888).also { bitmap ->
            val pixels = IntArray(720 * 720) { i -> if (matrix[i % 720, i / 720]) Color.BLACK else Color.WHITE }
            bitmap.setPixels(pixels, 0, 720, 0, 0, 720, 720)
        }
    }
    private fun sendPage() {
        add(body, label(t("SMW 보내기", "Send SMW"), 28, ink, true)); gap(body)
        add(body, label(t("사용 가능", "Available") + "  " + wallet()?.optString("available_dora", "0") + " SMW", 14, muted)); gap(body)
        val panel = card(body)
        add(panel, label(t("받는 주소", "Recipient"), 14, muted)); gap(panel, 7)
        val destination = input(t("sumuww1… 전체 주소", "Full sumuww1… address"), multiline = true).apply { setText(sendAddress); minLines = 2 }
        addressInput = destination; rememberDraft(destination) { sendAddress = it }; add(panel, destination); gap(panel, 10)
        add(panel, button(t("QR 이미지에서 주소 읽기", "Read address from QR image"), false) {
            sendAddress = destination.text.toString(); pickFile(IMPORT_QR, "image/*")
        }); gap(panel, 18)
        add(panel, label(t("수량 (SMW)", "Amount (SMW)"), 14, muted)); gap(panel, 7)
        val amount = input("0.00000000").apply { inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL; setText(sendAmount) }
        amountInput = amount; rememberDraft(amount) { sendAmount = it }
        add(panel, amount); gap(panel, 18)
        add(panel, label(t("수수료 (빈칸이면 자동 계산)", "Fee (leave empty to estimate)"), 13, muted)); gap(panel, 7)
        val fee = input(t("자동", "Automatic")).apply { inputType = InputType.TYPE_CLASS_NUMBER or InputType.TYPE_NUMBER_FLAG_DECIMAL; setText(sendFee) }
        feeInput = fee; rememberDraft(fee) { sendFee = it }
        add(panel, fee); gap(panel, 22)
        add(panel, button(t("송금 내용 확인", "Review transfer")) {
            sendAddress = destination.text.toString().trim(); sendAmount = amount.text.toString(); sendFee = fee.text.toString()
            if (!unlocked()) { passwordDialog("unlock") { render() }; return@button }
            (getSystemService(INPUT_METHOD_SERVICE) as InputMethodManager).hideSoftInputFromWindow(amount.windowToken, 0)
            work("parse_address", sendAddress) { parsed ->
                sendAddress = parsed.optString("address")
                work("prepare", sendAddress, sendAmount, sendFee) { quote -> confirmTransfer(quote) }
            }
        })
    }
    private fun rememberDraft(field: EditText, changed: (String) -> Unit) {
        field.addTextChangedListener(object : TextWatcher {
            override fun beforeTextChanged(s: CharSequence?, start: Int, count: Int, after: Int) {}
            override fun onTextChanged(s: CharSequence?, start: Int, before: Int, count: Int) { changed(s?.toString().orEmpty()) }
            override fun afterTextChanged(s: Editable?) {}
        })
    }
    private fun confirmTransfer(quote: JSONObject) {
        val panel = dialogBody()
        add(panel, label(t("받는 주소", "Recipient"), 13, muted)); add(panel, label(sendAddress, 15)); gap(panel)
        add(panel, label(t("보낼 수량", "Amount") + "  " + quote.optString("amount_dora") + " SMW", 18, ink, true)); gap(panel)
        add(panel, label(t("네트워크 수수료", "Network fee") + "  " + quote.optString("fee_dora") + " SMW", 14)); gap(panel)
        add(panel, label(t("합계", "Total") + "  " + quote.optString("total_dora") + " SMW", 18, ink, true))
        val confirmation = showDialog(t("송금 확인", "Confirm transfer"), panel, t("전송", "Send")) {
            dialog?.getButton(AlertDialog.BUTTON_POSITIVE)?.isEnabled = false
            work("submit", quote.optString("quote_id")) { result ->
                dialog?.dismiss()
                preferences.edit().putString("last-transfer", result.toString()).apply()
                sendAddress = ""; sendAmount = ""; sendFee = ""
                page = "history"; render(); showTransferResult(result)
            }
        }
        confirmation.getButton(AlertDialog.BUTTON_POSITIVE).id = 2003
    }
    private fun showTransferResult(result: JSONObject) {
        val message = when (result.optString("outcome")) {
            "accepted" -> t("거래를 제출했습니다. 블록에 포함되면 확인됩니다.\n\n거래 ID\n", "Transaction submitted. Confirmation follows inclusion in a block.\n\nTransaction ID\n") + result.optString("txid")
            "rejected" -> friendly(result.optString("error"))
            else -> t("전송 결과를 확인하지 못했습니다. 다시 보내기 전에 거래 내역을 확인해 주세요.", "Transfer outcome is unknown. Check activity before sending again.")
        }
        alert(t("전송 결과", "Transfer result"), message)
    }
    private fun transactionRow(container: LinearLayout, transaction: JSONObject) {
        val panel = card(container)
        val units = BigDecimal.valueOf(transaction.optLong("net_amount"), 8).stripTrailingZeros().toPlainString()
        val title = if (transaction.optBoolean("coinbase")) t("채굴 보상", "Mining reward") else if (transaction.optLong("net_amount") < 0) t("보냄", "Sent") else t("받음", "Received")
        add(panel, label("$title   $units SMW", 17, ink, true)); gap(panel, 7)
        add(panel, label(if (transaction.optString("status") == "pending") t("확인 대기", "Pending") else tf("{0} confirmations", transaction.optInt("confirmations")), 13, muted))
        gap(panel, 7)
        add(panel, label(transaction.optString("txid").take(20) + "…", 12, muted))
        panel.setOnClickListener {
            val content = dialogBody(); val txid = transaction.optString("txid")
            add(content, label(txid, 14).apply { setTextIsSelectable(true) }); gap(content)
            add(content, button(t("거래 ID 복사", "Copy transaction ID"), false) { copy(txid) })
            showDialog(t("거래 정보", "Transaction"), content)
        }
    }
    private fun historyPage() {
        add(body, label(t("거래 내역", "Activity"), 28, ink, true)); gap(body)
        if (wallet() == null) { add(body, label(t("지갑을 먼저 열어 주세요.", "Open your wallet first."), 15, muted)); return }
        val list = column(); historyList = list; add(body, list)
        add(list, label(t("불러오는 중…", "Loading…"), 14, muted))
        loadHistory(list)
    }
    private fun loadHistory(list: LinearLayout) {
        if (historyLoading) return
        historyLoading = true
        val token = epoch
        val offset = historyOffset
        WalletRuntime.executor.execute {
            val result = runCatching { WalletRuntime.call("history", offset.toString()) }
            handler.post {
                historyLoading = false
                if (!resumed || token != epoch || page != "history" || historyList !== list || offset != historyOffset) return@post
                list.removeAllViews()
                result.onSuccess { value ->
                    val rows = value.optJSONArray("transactions")
                    if (rows == null || rows.length() == 0) add(list, label(t("아직 거래 내역이 없습니다.", "No transactions yet."), 15, muted))
                    else for (i in 0 until rows.length()) transactionRow(list, rows.getJSONObject(i))
                    if (historyOffset > 0) add(list, button(t("이전 내역", "Previous page"), false) { historyOffset = maxOf(0, historyOffset - 50); render() })
                    if (historyOffset + 50 < value.optInt("total")) { gap(list); add(list, button(t("다음 내역", "Next page"), false) { historyOffset += 50; render() }) }
                }.onFailure { add(list, label(t("거래 내역을 불러오지 못했습니다.", "Could not load activity."), 15, muted)) }
            }
        }
    }
    private fun settingsPage() {
        add(body, label(t("설정", "Settings"), 28, ink, true)); gap(body)
        val security = card(body)
        add(security, label(t("지갑 관리", "Wallet management"), 19, ink, true)); gap(security)
        if (wallet() != null || state.optBoolean("wallet_exists")) {
            add(security, button(t("암호화 백업 내보내기", "Export encrypted backup"), false) {
                passwordDialog("backup") { result ->
                    pendingExport = Base64.decode(result.optString("encrypted"), Base64.NO_WRAP)
                    // The picker pauses the activity. The encrypted export is held separately.
                    exportData = pendingExport; pendingExport = null
                    startActivityForResult(Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                        addCategory(Intent.CATEGORY_OPENABLE); type = "application/json"
                        putExtra(Intent.EXTRA_TITLE, "SUMUWW-wallet-backup.json")
                    }, EXPORT_BACKUP)
                }
            }); gap(security)
            add(security, button(t("복구 단어 확인", "View recovery words"), false) { passwordDialog("phrase") { phraseDialog(it.optString("words")) } }); gap(security)
            add(security, button(t("마지막 전송 결과", "Last transfer result"), false) {
                val value = preferences.getString("last-transfer", null)
                if (value == null) toast(t("전송 내역이 없습니다.", "No transfer submitted.")) else showTransferResult(JSONObject(value))
            })
        } else add(security, label(t("지갑을 만들거나 복원해 주세요.", "Create or restore a wallet."), 15, muted))
        gap(security)
        add(security, button(t("자동 잠금", "Auto-lock") + " · " + (preferences.getInt("timeout", 300) / 60) + t("분", " min"), false) {
            SumuwwVerticalCaptions.builder(this).setTitle(t("자동 잠금", "Auto-lock")).setItems(arrayOf(t("1분", "1 minute"), t("5분", "5 minutes"), t("15분", "15 minutes"))) { _, index ->
                val timeout = intArrayOf(60, 300, 900)[index]
                preferences.edit().putInt("timeout", timeout).apply()
                work("timeout", timeout.toString()) { render() }
            }.show()
        })
        val network = card(body)
        add(network, label(t("네트워크", "Network"), 19, ink, true)); gap(network)
        networkLine(network); gap(network)
        add(network, button(t("IP 보호", "IP protection"), false) { choosePrivacy() }); gap(network)
        val endpoint = input(t("피어 주소 (호스트:포트)", "Peer address (host:port)"))
        add(network, endpoint); gap(network)
        add(network, button(t("피어 추가", "Add peer"), false) { work("peer", endpoint.text.toString()) { toast(t("피어를 추가했습니다", "Peer added")); readState() } })
        val appearance = card(body)
        add(appearance, label(t("화면과 언어", "Appearance & language"), 19, ink, true)); gap(appearance)
        add(appearance, button(if (dark) t("밝은 화면 사용", "Use light appearance") else t("어두운 화면 사용", "Use dark appearance"), false) { preferences.edit().putBoolean("dark", !dark).apply(); render() }); gap(appearance)
        add(appearance, button(t("언어", "Language") + " · " + WalletLanguages.languages.getValue(language), false) {
            val codes = WalletLanguages.languages.keys.toList()
            dialog = SumuwwVerticalCaptions.builder(this).setTitle(t("언어 선택", "Select language"))
                .setSingleChoiceItems(WalletLanguages.languages.values.toTypedArray(), codes.indexOf(language)) { selectedDialog, index ->
                    WalletLanguages.set(this, codes[index]); selectedDialog.dismiss(); dialog = null; render()
                }.setNegativeButton(t("취소", "Cancel"), null).create()
            dialog?.show()
        })
        val version = packageManager.getPackageInfo(packageName, 0).versionName.orEmpty()
        add(body, label("SUMUWW Wallet $version · SMW", 12, muted))
    }
    private fun pickFile(request: Int, type: String) {
        startActivityForResult(Intent(Intent.ACTION_OPEN_DOCUMENT).apply { this.type = type; addCategory(Intent.CATEGORY_OPENABLE) }, request)
    }

    private fun choosePrivacy() {
        dialog = SumuwwVerticalCaptions.builder(this).setTitle(t("IP 보호", "IP protection"))
            .setItems(arrayOf("Direct", "Tor", "I2P")) { _, index -> confirmPrivacy(arrayOf("direct", "tor", "i2p")[index]) }.create()
        dialog?.show()
    }

    private fun confirmPrivacy(mode: String) {
        val key = "privacy-help-hidden-$mode"
        fun activate() { work("privacy", mode) { readState() } }
        if (preferences.getBoolean(key, false)) { activate(); return }
        val ko = when(mode) {
            "tor" -> "장점: 상대 노드에게 실제 IP를 숨기는 데 도움이 됩니다.\n\n단점: 연결·동기화가 느려지고 배터리·데이터 사용이 늘 수 있습니다. 거래 기록은 공개됩니다. Tor 연결에 실패해도 일반 연결로 전환하지 않습니다."
            "i2p" -> "장점: I2P 노드끼리 실제 IP 노출을 줄여줍니다.\n\n단점: I2P 피어가 필요합니다. 연결·동기화가 느려지고 배터리·데이터 사용이 늘 수 있습니다. 거래 기록은 공개됩니다. I2P 연결에 실패해도 일반 연결로 전환하지 않습니다."
            else -> "Tor와 I2P를 사용하지 않습니다. 보통 연결이 빠르고 자원을 적게 쓰지만, 상대 노드에게 연결 IP가 보입니다."
        }
        val en = when(mode) {
            "tor" -> "Benefit: Tor helps hide your real IP from other peers.\n\nTrade-offs: Connecting and syncing may be slower, and battery and data use may increase. Transaction records remain public. If Tor fails, direct connections stay disabled."
            "i2p" -> "Benefit: I2P helps hide your real IP from other I2P peers.\n\nTrade-offs: I2P peers are required. Connecting and syncing may be slower, and battery and data use may increase. Transaction records remain public. If I2P fails, direct connections stay disabled."
            else -> "Direct connection uses neither Tor nor I2P. It usually connects faster and uses fewer resources. Other peers can see your connection IP."
        }
        val hide = CheckBox(this).apply { text = t("다음부터 도움말을 보지 않겠습니다.", "Do not show this help again."); isChecked = false; setTextColor(ink) }
        val view = LinearLayout(this).apply { orientation = LinearLayout.VERTICAL; setPadding(dp(16),0,dp(16),0); addView(hide) }
        dialog = SumuwwVerticalCaptions.builder(this).setTitle(t("IP 보호", "IP protection")+" · "+mode.uppercase())
            .setMessage(t(ko, en)).setView(view).setNegativeButton(t("취소", "Cancel"), null)
            .setPositiveButton(t("실행", "Run")) { _, _ -> preferences.edit().putBoolean(key, hide.isChecked).apply(); activate() }.create()
        dialog?.show()
    }
    @Deprecated("Android legacy result API")
    override fun onActivityResult(requestCode: Int, resultCode: Int, data: Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        val uri = data?.data
        if (resultCode != RESULT_OK || uri == null) { exportData = null; return }
        if (requestCode == EXPORT_BACKUP) {
            val bytes = exportData; exportData = null
            if (bytes == null) { toast(t("백업을 다시 선택해 주세요", "Please export the backup again")); return }
            WalletRuntime.executor.execute {
                val result = runCatching { contentResolver.openOutputStream(uri, "wt")!!.use { it.write(bytes); it.flush() } }
                handler.post { toast(if (result.isSuccess) t("암호화 백업을 저장했습니다", "Encrypted backup saved") else t("백업을 저장하지 못했습니다", "Backup could not be saved")) }
            }
        } else {
            if (requestCode != IMPORT_BACKUP && requestCode != IMPORT_QR) return
            val token = epoch
            WalletRuntime.executor.execute {
                val result = runCatching { contentResolver.openInputStream(uri)!!.use { stream ->
                    val max = if (requestCode == IMPORT_BACKUP) 4096 else 12 * 1024 * 1024
                    val output = ByteArrayOutputStream(); val buffer = ByteArray(4096)
                    while (true) { val read = stream.read(buffer); if (read < 0) break; if (read == 0) throw IllegalArgumentException("Unreadable file"); if (output.size() + read > max) throw IllegalArgumentException("File too large"); output.write(buffer, 0, read) }
                    output.toByteArray()
                } }
                handler.post {
                    if (epoch != token || isFinishing || isDestroyed) return@post
                    result.onSuccess { raw -> pendingImport = requestCode to raw; presentImport() }
                        .onFailure { if (resumed) alert(t("파일 확인", "Check file"), t("파일을 읽을 수 없거나 너무 큽니다.", "The file is unreadable or too large.")) }
                }
            }
        }
    }
    private fun presentImport() {
        if (!resumed) return
        val (request, raw) = pendingImport ?: return
        pendingImport = null
        if (request == IMPORT_BACKUP) restoreBackup(raw) else decodeQr(raw)
    }
    private fun restoreBackup(raw: ByteArray) {
        val panel = dialogBody(); val password = input(t("백업 비밀번호", "Backup password"), true); add(panel, password)
        showDialog(t("암호화 백업 복원", "Restore encrypted backup"), panel, t("복원", "Restore")) {
            work("restore", password.text.toString(), Base64.encodeToString(raw, Base64.NO_WRAP)) { dialog?.dismiss(); page = "wallet"; render() }
        }
    }
    private fun decodeQr(raw: ByteArray) {
        val token = epoch
        WalletRuntime.executor.execute {
          val result = runCatching {
            val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }; BitmapFactory.decodeByteArray(raw, 0, raw.size, bounds)
            require(bounds.outWidth > 0 && bounds.outHeight > 0)
            val options = BitmapFactory.Options().apply { inSampleSize = maxOf(1, maxOf(bounds.outWidth, bounds.outHeight) / 1600) }
            val image = BitmapFactory.decodeByteArray(raw, 0, raw.size, options) ?: error("Image unavailable")
            val pixels = IntArray(image.width * image.height); image.getPixels(pixels, 0, image.width, 0, 0, image.width, image.height)
            val source = RGBLuminanceSource(image.width, image.height, pixels)
            MultiFormatReader().decode(BinaryBitmap(HybridBinarizer(source)), mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE))).text
          }
          handler.post {
            if (!resumed || epoch != token) return@post
            result.onSuccess { text -> work("parse_address", text) { value -> sendAddress = value.optString("address"); page = "send"; render() } }
                .onFailure { alert(t("QR 확인", "Check QR"), t("SUMUWW 주소 QR을 읽지 못했습니다.", "Could not read a SUMUWW address QR.")) }
          }
        }
    }
    companion object {
        private const val IMPORT_BACKUP = 4101
        private const val EXPORT_BACKUP = 4102
        private const val IMPORT_QR = 4103
        private var exportData: ByteArray? = null
    }
}
