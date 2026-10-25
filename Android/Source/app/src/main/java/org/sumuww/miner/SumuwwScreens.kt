package org.sumuww.miner

import android.Manifest
import android.app.Activity
import android.content.pm.PackageManager
import android.os.Build
import android.view.Gravity
import android.view.View
import android.view.ViewTreeObserver
import android.view.WindowInsets
import android.widget.FrameLayout
import android.widget.ImageView
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import android.util.TypedValue
import org.json.JSONObject

/** UI adapter for the existing SMW controller. No wallet, network or mining rules live here. */
internal class SumuwwScreens(
    private val activity: Activity,
    private val translate: (String) -> String,
    private val dispatch: (String, String, String) -> Unit
) {
    data class Model(
        val page: Int, val status: JSONObject?, val history: JSONObject?,
        val historyOffset: Int, val historyFilter: String, val cpu: Int, val elapsed: String,
        val targetDraft: String, val sendAddress: String, val sendAmount: String,
        val error: String?, val tour: Boolean, val dark: Boolean,
        val palette: SumuwwTheme.Palette, val themeMode: String, val languageName: String,
        val manualFee: Boolean = false, val feeDraft: String = "1", val historySearch: String = "", val statusUnavailable: Boolean = false, val blocks: JSONObject? = null, val blockSearch: String = "", val feeMode: Int = 1
    )

    val appRoot = FrameLayout(activity)
    val content = FrameLayout(activity)
    val topHeader = LinearLayout(activity)
    val bottomNav = LinearLayout(activity)
    val tabs = Array(4) { LinearLayout(activity) }
    val tabIcons = Array(4) { ImageView(activity) }
    val tabLabels = Array(4) { TextView(activity) }
    private val shell = LinearLayout(activity).apply { orientation = LinearLayout.VERTICAL }
    private var lastPage = -1
    private lateinit var state: Model
    private lateinit var ui: SumuwwUiComponents
    private val miningUpdates = mutableListOf<() -> Unit>()

    init {
        shell.setOnApplyWindowInsetsListener { view, insets ->
            if (Build.VERSION.SDK_INT >= 30) {
                val bars = insets.getInsets(WindowInsets.Type.systemBars() or WindowInsets.Type.displayCutout() or WindowInsets.Type.ime())
                view.setPadding(bars.left, bars.top, bars.right, bars.bottom)
            } else view.setPadding(insets.systemWindowInsetLeft, insets.systemWindowInsetTop, insets.systemWindowInsetRight, insets.systemWindowInsetBottom)
            insets
        }
        topHeader.orientation = LinearLayout.VERTICAL
        shell.addView(topHeader, LinearLayout.LayoutParams(-1, -2))
        shell.addView(content, LinearLayout.LayoutParams(-1, 0, 1f))
        bottomNav.orientation = LinearLayout.HORIZONTAL
        shell.addView(bottomNav, LinearLayout.LayoutParams(-1, -2))
        appRoot.addView(shell, FrameLayout.LayoutParams(-1, -1))
    }

    fun updateFormStatus(status:JSONObject,cpu:Int){
        if(::state.isInitialized&&state.page in listOf(5,12)){
            state=state.copy(status=status,cpu=cpu,statusUnavailable=false)
            miningUpdates.forEach{it()}
        }
    }
    fun render(next: Model) {
        val samePage = lastPage == next.page
        // A status poll must not replace the views being touched or scrolled.
        val updateMining = samePage && next.page == 1 && miningUpdates.isNotEmpty() &&
            state.palette == next.palette && state.dark == next.dark &&
            state.languageName == next.languageName && state.tour == next.tour &&
            state.error == next.error && state.targetDraft == next.targetDraft &&
            state.status?.optJSONObject("mobile_batch")?.optString("protection_reason")==next.status?.optJSONObject("mobile_batch")?.optString("protection_reason") &&
            state.status?.optJSONObject("security")?.optBoolean("locked")==next.status?.optJSONObject("security")?.optBoolean("locked")
        if (updateMining) {
            state = next
            miningUpdates.forEach { it() }
            return
        }
        val existingScroll = content.getChildAt(0) as? ScrollView
        val oldY = if (samePage) existingScroll?.scrollY ?: 0 else 0
        miningUpdates.clear()
        lastPage = next.page; state = next
        ui = SumuwwUiComponents(activity, next.palette, next.dark)
        shell.layoutDirection = if (UiLanguage.code(activity) in setOf("ar", "ur")) View.LAYOUT_DIRECTION_RTL else View.LAYOUT_DIRECTION_LTR
        shell.background = SumuwwScreenBackground(next.palette, next.dark)
        topHeader.removeAllViews()
        val title = when (next.page) {
            0 -> tr("SUMUWW"); 1 -> tr("채굴"); 2 -> tr("지갑"); 3 -> tr("거래내역"); 4 -> tr("더보기")
            5 -> tr("보내기"); 6 -> tr("받기"); 7 -> tr("도움말"); 8 -> tr("테마")
            9 -> tr("설정"); 10 -> tr("계정"); 11 -> tr("보안 설정"); 12 -> tr("채굴 설정")
            13 -> tr("알림 설정"); 14 -> tr("앱 정보"); 15 -> tr("전체 블록"); else -> tr("SUMUWW")
        }
        val back = if (next.page in listOf(0, 1, 2, 4)) null else ({ action("back") })
        topHeader.addView(ui.SumuwwTopBar(title, back,
            if (next.page == 0) R.drawable.ic_bell else if (next.page in listOf(1, 2, 4)) R.drawable.ic_settings else null,
            if (next.page == 0) tr("알림 설정") else tr("설정")) { action("page", if (next.page == 0) "13" else "9") })
        renderNavigation()
        val scroll = existingScroll ?: ScrollView(activity).apply { isFillViewport = true; isVerticalScrollBarEnabled = false; clipToPadding = false }
        // Vertical text measures its own natural height; viewport filling must not compress the final control.
        scroll.isFillViewport = !ui.verticalMongolian
        val page = ui.column().apply { setPadding(ui.dp(if(ui.verticalMongolian)14 else 20), ui.dp(12), ui.dp(if(ui.verticalMongolian)14 else 20), ui.dp(24)) }
        next.error?.let { page.addView(ui.label(it, 13f, ui.negative).apply { setPadding(ui.dp(12), ui.dp(12), ui.dp(12), ui.dp(12)); background = ui.rounded(ui.soft, 12) }, ui.params(bottom = 16)) }
        when (next.page) {
            0 -> home(page); 1 -> mining(page); 2 -> wallet(page); 3 -> history(page); 4 -> more(page)
            5 -> send(page); 6 -> receive(page); 7 -> help(page); 8 -> themes(page); 9 -> settings(page)
            10 -> account(page); 11 -> security(page); 12 -> miningSettings(page); 13 -> notifications(page); 14 -> information(page); 15 -> allBlocks(page)
        }
        if(ui.verticalMongolian){
            // A vertical heading sits beside its content, as in Mongolian reading
            // columns. Stacking it above a full-width card wastes an entire band.
            var i=0
            while(i+1<page.childCount){
                val heading=page.getChildAt(i)
                if(heading is SumuwwVerticalTextView && heading.verticalSection){
                    val body=page.getChildAt(i+1)
                    page.removeView(body);page.removeView(heading)
                    val lane=ui.row().apply{gravity=Gravity.TOP}
                    lane.addView(heading,ui.params(width=ui.dp(60)))
                    lane.addView(body,LinearLayout.LayoutParams(0,-2,1f).apply{leftMargin=ui.dp(8)})
                    page.addView(lane,i,ui.params(top=8,bottom=8))
                }
                i++
            }
        }
        scroll.removeAllViews()
        scroll.addView(page)
        if (existingScroll == null) content.addView(scroll)
        // Restore before drawing, not in a posted callback after a frame at the top.
        scroll.viewTreeObserver.addOnPreDrawListener(object : ViewTreeObserver.OnPreDrawListener {
            override fun onPreDraw(): Boolean {
                scroll.viewTreeObserver.removeOnPreDrawListener(this)
                scroll.scrollTo(0, oldY)
                return true
            }
        })
    }

    private fun renderNavigation() {
        bottomNav.removeAllViews(); bottomNav.setBackgroundColor(ui.surface)
        bottomNav.visibility = if (state.page in listOf(0, 1, 2, 4) || state.tour) View.VISIBLE else View.GONE
        val routes = intArrayOf(0, 1, 2, 4)
        val labels = arrayOf("홈", "채굴", "지갑", "더보기")
        val resources = intArrayOf(R.drawable.nav_home, R.drawable.nav_mining, R.drawable.nav_wallet, R.drawable.nav_more)
        for (i in 0..3) {
            val chosen = state.page == routes[i]
            val color = if (chosen) ui.accent else ui.muted
            tabs[i] = (if(ui.verticalMongolian)ui.row() else ui.column()).apply { gravity = Gravity.CENTER; minimumHeight = ui.dp(64); setPadding(0, ui.dp(8), 0, ui.dp(8)); contentDescription = tr(labels[i]); setOnClickListener { action("page", routes[i].toString()) } }
            tabIcons[i] = ui.icon(resources[i], color)
            tabLabels[i] = ui.label(tr(labels[i]), 11f, color, chosen).apply { gravity = Gravity.CENTER;verticalInlineDp=40f;verticalTextSizeCapSp=10f }
            tabs[i].addView(tabIcons[i], ui.params(ui.dp(22), ui.dp(22)))
            tabs[i].addView(tabLabels[i], if(ui.verticalMongolian)ui.params(width=-2).apply{leftMargin=ui.dp(6)} else ui.params(top = 4))
            bottomNav.addView(tabs[i], LinearLayout.LayoutParams(0, -2, 1f))
        }
    }

    private fun home(p: LinearLayout) {
        val balance = ui.SumuwwBalanceCard(tr("내 자산"), "${amount("total_smw")} SMW", "${tr("사용 가능")} ${amount("available_smw")} SMW")
        balance.addView(View(activity), ui.params(height=ui.dp(if(ui.verticalMongolian)8 else 18)))
        actions(balance, listOf(
            Triple(R.drawable.action_send, "보내기", "5"), Triple(R.drawable.action_receive, "받기", "6"),
            Triple(R.drawable.nav_mining, "채굴", "1"), Triple(R.drawable.nav_more, "더보기", "4")
        ))
        p.addView(balance, ui.params(bottom = 8))
        p.addView(ui.section(tr("채굴 상태")))
        val mining = ui.row().apply { setPadding(ui.dp(16), ui.dp(16), ui.dp(16), ui.dp(16)); background = ui.surfaceFinish() }
        mining.addView(ui.icon(R.drawable.nav_mining), ui.params(ui.dp(28), ui.dp(28)))
        val words = ui.column().apply { setPadding(ui.dp(12), 0, 0, 0) }
        words.addView(ui.label(miningLabel(), 18f, ui.ink, true))
        words.addView(ui.label("${completed()} / ${target()} ${tr("블록")}", 12f, ui.muted), ui.params(top = 5))
        mining.addView(words, LinearLayout.LayoutParams(0, -2, 1f))
        mining.addView(ui.label(state.elapsed, 13f, ui.accent, true))
        mining.setOnClickListener { action("page", "1") }
        p.addView(mining)
        p.addView(ui.section(tr("최근 활동")))
        val transactions = state.status?.optJSONArray("transactions")
        if (transactions == null || transactions.length() == 0) {
            p.addView(ui.label(tr("거래 내역이 없습니다"), 14f, ui.muted), ui.params(bottom = 12))
        } else {
            for (i in 0 until minOf(3, transactions.length())) transaction(p, transactions.optJSONObject(i) ?: continue)
        }
        val history = ui.SumuwwSettingRow(R.drawable.nav_history, tr("전체 거래내역")) { action("history") }.apply { tag = "sumuww-history-entry" }
        p.addView(history)
        p.addView(ui.section(tr("네트워크 상태")))
        metric(p, tr("블록 높이"), node()?.optInt("height")?.toString() ?: "—")
        metric(p, tr("연결 피어"), node()?.optInt("peers")?.toString() ?: "—")
        metric(p, tr("동기화"), syncState())
    }

    private fun mining(p: LinearLayout) {
        state.status?.optJSONObject("mobile_batch")?.optString("protection_reason")?.takeIf{it.isNotBlank()&&it!="null"}?.let{p.addView(ui.label(tr(it),14f,ui.negative),ui.params(bottom=12))}
        if(state.status?.optJSONObject("security")?.optBoolean("locked")==true)p.addView(ui.label(tr("자동 보안 잠금"),14f,ui.muted),ui.params(bottom=12))
        fun description() = when {
            running() -> tr("휴대폰에서 SMW 블록을 탐색 중")
            address().isBlank() -> tr("지갑을 열고 동기화된 노드에 연결해 시작하세요")
            else -> "${tr("네트워크 상태")}: ${syncState()}"
        }
        val explanation=miningText(ui.label(description(),13f,ui.muted).apply{if(ui.verticalMongolian){verticalInlineDp=80f;verticalTextSizeCapSp=11f}}){description()}
        if(!ui.verticalMongolian)p.addView(explanation,ui.params(bottom=24))
        val detailedArtwork=LocaleBrand.isLocalized(activity)
        val circleSize = if(ui.verticalMongolian) (activity.resources.configuration.screenWidthDp-200).coerceIn(108,132) else if(detailedArtwork)
            (activity.resources.configuration.screenWidthDp-40).coerceIn(260,320).coerceAtMost(activity.resources.configuration.screenWidthDp-40)
            else (activity.resources.configuration.screenWidthDp - 80 + ((activity.resources.configuration.fontScale - 1f) * 80).toInt())
            .coerceIn(220, 280).coerceAtMost(activity.resources.configuration.screenWidthDp - 40)
        val ring = FrameLayout(activity)
        val progress = ui.SumuwwMiningProgress(if (target() > 0) completed().toFloat() / target() else 0f)
        miningUpdates.add { progress.progress = if (target() > 0) completed().toFloat() / target() else 0f }
        ring.addView(progress, FrameLayout.LayoutParams(-1, -1))
        val center = ui.column().apply { gravity = Gravity.CENTER }
        var arabicBalanceCaption:TextView?=null
        if(ui.verticalMongolian) {
            // A compact rectangular brand panel leaves vertical captions room beside it.
            center.addView(ui.logo(),ui.params(ui.dp(52),ui.dp(36)))
            center.addView(ui.label("SMW",13f,ui.ink,true).apply{gravity=Gravity.CENTER},ui.params(top=4))
        } else {
        val detailedLogo=LocaleBrand.isLocalized(activity)
        center.addView(ui.logo(), ui.params(ui.dp(if(detailedLogo)176 else 72), ui.dp(if(detailedLogo)96 else 52)))
        center.addView(miningText(ui.label("", 15f, ui.muted).apply { gravity = Gravity.CENTER }) { miningLabel() }, ui.params(top = if(detailedLogo)6 else 12))
        center.addView(miningText(ui.label(amount("total_smw"), 34f, ui.ink, true).apply {
            gravity = Gravity.CENTER; maxLines = 1
            typeface=android.graphics.Typeface.create("sans-serif",android.graphics.Typeface.BOLD)
            includeFontPadding=false
            setAutoSizeTextTypeUniformWithConfiguration(18, 34, 1, TypedValue.COMPLEX_UNIT_SP)
        }) { amount("total_smw") }, ui.params(top = 8))
        center.addView(ui.label("SMW", 14f, ui.ink, true).apply { gravity = Gravity.CENTER }, ui.params(top = 4))
        val balanceCaption=miningText(ui.label("", 11f, ui.muted).apply { gravity = Gravity.CENTER }) {
            if (state.status?.optJSONObject("mining")?.optBoolean("network_synchronized") == true)
                tr("총 보유량") else tr("로컬 체인 잔액")
        }
        if(ui.arabic)arabicBalanceCaption=balanceCaption else center.addView(balanceCaption,ui.params(top=4))
        }
        ring.addView(center, FrameLayout.LayoutParams(-1, -1).apply { leftMargin = ui.dp(if(ui.verticalMongolian)12 else 36); rightMargin = leftMargin })
        if(!ui.verticalMongolian)p.addView(ring,ui.params(ui.dp(circleSize),ui.dp(circleSize),bottom=20).apply{gravity=Gravity.CENTER})
        arabicBalanceCaption?.let{p.addView(it,ui.params(bottom=16))}
        if(ui.verticalMongolian){
            val captions=ui.row().apply{gravity=Gravity.TOP}
            captions.addView(miningText(ui.label("",12f,ui.ink,true).apply{verticalInlineDp=48f}){miningLabel()},LinearLayout.LayoutParams(0,-2,1f))
            captions.addView(miningText(ui.label("",11f,ui.muted).apply{verticalInlineDp=48f}){
                if(state.status?.optJSONObject("mining")?.optBoolean("network_synchronized")==true)tr("총 보유량") else tr("로컬 체인 잔액")
            },LinearLayout.LayoutParams(0,-2,1f))
            val words=ui.column()
            words.addView(explanation,ui.params(bottom=8));words.addView(captions)
            val hero=ui.row().apply{gravity=Gravity.TOP}
            hero.addView(ring,ui.params(ui.dp(circleSize),ui.dp(104)))
            hero.addView(words,LinearLayout.LayoutParams(0,-2,1f).apply{leftMargin=ui.dp(12)})
            p.addView(hero,ui.params(bottom=8))
            // Balances can have seventeen digits. The full-width row keeps them
            // readable beside the compact rectangular progress panel.
            p.addView(miningText(ui.label("",28f,ui.ink,true).apply{
                gravity=Gravity.CENTER;maxLines=1
                setAutoSizeTextTypeUniformWithConfiguration(12,28,1,TypedValue.COMPLEX_UNIT_SP)
            }){"${amount("total_smw")} SMW"},ui.params(bottom=12))
        }
        p.addView(miningText(ui.SumuwwPrimaryButton("") { if (running()) action("stopMining") else action("startMining", state.targetDraft) }) { if (running()) tr("채굴 중지") else tr("채굴 시작") })
        fun duration(seconds:Double):String { val s=seconds.toLong().coerceAtLeast(0);return String.format(java.util.Locale.ROOT,"%02d:%02d:%02d",s/3600,(s/60)%60,s%60) }
        fun telemetry()=state.status?.optJSONObject("mobile_mining")
        val values: List<Pair<String, () -> String>> = listOf(tr("총 경과 시간") to { state.elapsed }, tr("진행 블록") to { "${completed()} / ${target()}" }, tr("실제 계산 시간") to { duration(telemetry()?.optDouble("hashing_seconds",0.0)?:0.0) }, tr("네트워크 대기 시간") to { duration(state.status?.optJSONObject("mobile_batch")?.optDouble("network_wait_seconds",0.0)?:0.0) }, tr("실제 계산 속도") to { String.format(java.util.Locale.ROOT,"%,.0f H/s",telemetry()?.optDouble("hashes_per_second",0.0)?:0.0) }, tr("네트워크 상태") to { syncState() }, tr("현재 블록 보상") to { subsidy() })
        values.chunked(2).forEach { pair ->
            val row = ui.row()
            pair.forEach { (caption, value) ->
                val tile = ui.column().apply { setPadding(ui.dp(12), ui.dp(16), ui.dp(12), ui.dp(16)); background = ui.surfaceFinish(16) }
                tile.addView(ui.label(caption, 12f, ui.muted)); tile.addView(miningText(ui.label("", 18f, ui.ink, true), value), ui.params(top = 8))
                row.addView(tile, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = ui.dp(4); rightMargin = ui.dp(4) })
            }
            p.addView(row, ui.params(top = 12))
        }
        p.addView(ui.SumuwwSettingRow(R.drawable.ic_settings, tr("채굴 설정"), "${state.targetDraft} ${tr("블록")}") { action("page", "12") }, ui.params(top = 12))
    }

    private fun miningText(view: TextView, value: () -> String): TextView {
        val update = {
            val text = value()
            if (view.text.toString() != text) view.text = text
            if (view.isClickable) view.contentDescription = text
        }
        update()
        miningUpdates.add(update)
        return view
    }

    private fun wallet(p: LinearLayout) {
        val address = address()
        p.addView(ui.SumuwwBalanceCard(tr("총 보유 자산"), "${amount("total_smw")} SMW", "${tr("사용 가능")} ${amount("available_smw")} SMW", if (address.isBlank()) tr("지갑을 먼저 열어 주세요") else shortAddress(address), true, if(address.isBlank())null else ({action("copyAddress")})), ui.params(bottom = 20))
        actions(p, listOf(Triple(R.drawable.action_send, "보내기", "5"), Triple(R.drawable.action_receive, "받기", "6"), Triple(R.drawable.nav_history, "거래내역", "history")))
        p.addView(ui.section(tr("자산")))
        p.addView(ui.SumuwwAssetRow(tr("SUMUWW"), amount("total_smw"), tr("SMW 보유량")))
        metric(p, tr("사용 가능"), "${amount("available_smw")} SMW")
        metric(p, tr("미성숙 보상"), "${amount("immature_smw")} SMW")
        metric(p, tr("대기 중"), "${amount("pending_smw")} SMW")
        p.addView(ui.SumuwwSettingRow(R.drawable.nav_wallet, tr("지갑 관리")) { action("page", "10") }, ui.params(top = 16))
    }

    private fun send(p: LinearLayout) {
        val recipient = ui.SumuwwField(tr("받는 주소"), tr("받는 SMW 주소"), state.sendAddress, false, "sendAddress")
        p.addView(recipient.first)
        val quantity = ui.SumuwwField(tr("보낼 수량"), "0 SMW", state.sendAmount, true, "sendAmount")
        p.addView(quantity.first)
        p.addView(miningText(ui.label("",13f,ui.muted)){"${tr("사용 가능한 잔액")}  ${amount("available_smw")} SMW"}, ui.params(top = 12, bottom = 24))
        val fee = ui.SumuwwField(tr("수수료율 (yugeon/vB)"), "1 yugeon/vB", state.feeDraft, true, "sendFee")
        val preset=android.widget.Spinner(activity).apply {
            tag="feeMode"
            adapter=android.widget.ArrayAdapter(activity,android.R.layout.simple_spinner_dropdown_item,listOf(tr("느림"),tr("보통"),tr("빠름")))
            setSelection(state.feeMode.coerceIn(0,2));isEnabled=!state.manualFee
        }
        p.addView(preset,ui.params(bottom=8))
        val manual = android.widget.CheckBox(activity).apply {
            SumuwwVerticalCaptions.watch(this)
            tag="manualFee";text=tr("수수료 직접 설정");setTextColor(ui.ink);isChecked=state.manualFee
        }
        fee.first.visibility=if(manual.isChecked)View.VISIBLE else View.GONE
        manual.setOnCheckedChangeListener { _,checked -> fee.first.visibility=if(checked)View.VISIBLE else View.GONE;preset.isEnabled=!checked }
        p.addView(manual,ui.params(bottom=8));p.addView(fee.first)
        val preview = miningText(ui.label("",13f,ui.muted)) {
            val fees=state.status?.optJSONObject("fees")
            val mode=listOf("slow","normal","fast")[preset.selectedItemPosition.coerceIn(0,2)]
            if(manual.isChecked||fees==null) tr("자동 계산 · 최종 수수료는 전송 전에 확인합니다")
            else tr("현지 대기 수수료").replace("{0}",fees.optLong("pending_vsize").toString())
                .replace("{1}",fees.optJSONObject("rates")?.optString(mode,"—")?:"—")
                .replace("{2}",fees.optJSONObject("target_blocks")?.optInt(mode).toString())
        }
        preset.onItemSelectedListener=object:android.widget.AdapterView.OnItemSelectedListener{
            override fun onItemSelected(parent:android.widget.AdapterView<*>?,view:View?,position:Int,id:Long){miningUpdates.forEach{it()}}
            override fun onNothingSelected(parent:android.widget.AdapterView<*>?){}
        }
        manual.setOnCheckedChangeListener { _,checked -> fee.first.visibility=if(checked)View.VISIBLE else View.GONE;preset.isEnabled=!checked;miningUpdates.forEach{it()} }
        p.addView(preview,ui.params(top=8,bottom=20))
        p.addView(View(activity), if(ui.verticalMongolian) ui.params(height=ui.dp(8)) else LinearLayout.LayoutParams(-1, 0, 1f))
        p.addView(ui.SumuwwPrimaryButton(tr("다음")) { action("send", recipient.second.text.toString().trim(), quantity.second.text.toString().trim()) })
    }

    private fun receive(p: LinearLayout) {
        val address = address()
        p.addView(ui.SumuwwAddressCard(tr("내 SMW 주소"), if (address.isBlank()) tr("지갑을 먼저 열어 주세요") else address, tr("이 주소로 받은 SMW는 블록에서 확인된 뒤 잔액에 표시됩니다.")), ui.params(top = 24, bottom = 24))
        if (address.isNotBlank()) actions(p, listOf(Triple(R.drawable.ic_copy, "주소 복사", "copyAddress"), Triple(R.drawable.ic_share, "공유하기", "shareAddress")))
        else p.addView(ui.SumuwwPrimaryButton(tr("지갑 열기 / 생성 / 복구")) { action("walletManager") })
    }

    private fun history(p: LinearLayout) {
        val search=ui.SumuwwField(tr("거래 ID 검색"), "TXID", state.historySearch, false, "historySearch")
        p.addView(search.first,ui.params(bottom=8))
        p.addView(ui.SumuwwPrimaryButton(tr("검색")){action("historySearch",search.second.text.toString())},ui.params(bottom=16))
        val filters = ui.row().apply { setPadding(ui.dp(4), ui.dp(4), ui.dp(4), ui.dp(4)); background = ui.rounded(ui.soft, 22) }
        listOf("all" to "전체", "receive" to "받기", "send" to "보내기", "mining" to "채굴").forEach { (key, title) ->
            val chosen = key == state.historyFilter
            filters.addView(ui.label(tr(title), 12f, if (chosen) ui.onButton else ui.muted, chosen).apply { gravity = Gravity.CENTER; minimumHeight = ui.dp(44); background = if (chosen) ui.finish(SumuwwFinishDrawable.Kind.BUTTON,22) else null; setOnClickListener { action("historyFilter", key) } }, LinearLayout.LayoutParams(0, -2, 1f))
        }
        p.addView(filters, ui.params(bottom = 16))
        val items = state.history?.optJSONArray("transactions")
        if (items == null) { p.addView(ui.label(tr("불러오는 중"), 14f, ui.muted)); return }
        var shown = 0
        for (i in 0 until items.length()) {
            val tx = items.optJSONObject(i) ?: continue
            val kind = kind(tx)
            if (state.historyFilter != "all" && state.historyFilter != kind) continue
            shown++; transaction(p, tx)
        }
        if (shown == 0) p.addView(ui.label(tr("해당 내역이 없습니다"), 14f, ui.muted), ui.params(top = 24, bottom = 24))
        val total = state.history?.optInt("total", 0) ?: 0
        p.addView(ui.label("${if (total == 0) 0 else state.historyOffset + 1}–${minOf(state.historyOffset + 50, total)} / $total", 12f, ui.muted), ui.params(top = 20, bottom = 12))
        if (state.historyOffset > 0) p.addView(ui.SumuwwPrimaryButton(tr("이전")) { action("historyPrevious") }, ui.params(bottom = 8))
        if (state.historyOffset + 50 < total) p.addView(ui.SumuwwPrimaryButton(tr("다음")) { action("historyNext") }, ui.params(bottom = 8))
        p.addView(ui.SumuwwSettingRow(R.drawable.ic_info, tr("새로고침")) { action("historyRefresh") })
    }

    private fun allBlocks(p: LinearLayout) {
        p.addView(ui.label(tr("제네시스부터 현재까지 검증된 모든 노드의 블록을 확인합니다."),13f,ui.muted),ui.params(bottom=12))
        val search=ui.SumuwwField(tr("블록 높이"),"0",state.blockSearch,true,"blockSearch")
        p.addView(search.first,ui.params(bottom=8))
        p.addView(ui.SumuwwPrimaryButton(tr("검색")){action("blockSearch",search.second.text.toString())}.apply{tag="blocks-search"},ui.params(bottom=12))
        p.addView(ui.SumuwwSettingRow(R.drawable.ic_info,tr("새로고침")){action("blocksRefresh")}.apply{tag="blocks-refresh"})
        val result=state.blocks
        val blocks=result?.optJSONArray("blocks")
        if(blocks==null){p.addView(ui.label(tr("불러오는 중"),14f,ui.muted));return}
        val offset=result.optInt("offset");val total=result.optInt("total")
        if(result.optInt("height")<9600)p.addView(ui.label(tr("9,600번 블록 전에 업데이트하세요."),13f,ui.muted),ui.params(bottom=8))
        val jobs=result.optJSONArray("pending_proof_jobs")
        p.addView(ui.SumuwwSettingRow(R.drawable.ic_info,tr("Connection proofs")+": "+result.optInt("stored_proofs")){
            val lines=StringBuilder()
            val counts=result.optJSONObject("lottery_jobs")
            if(counts!=null)lines.append(tr("Selected pending")).append(": ").append(counts.optInt("selected_pending")).append("\n\n")
            for(i in 0 until (jobs?.length()?:0)){
                val job=jobs!!.getJSONObject(i)
                val phase=when(job.optString("phase")){
                    "participants","activity"->"활동 중인 노드 확인 중"
                    "beacon"->"추첨 대기"
                    "candidate_quorum"->"후보 승인 대기"
                    "witnesses"->"증인 서명 대기"
                    "target_receipt"->"블록 생성자 응답 대기"
                    else->"Pending"
                }
                lines.append(tr("블록 높이")).append(": ").append(job.optInt("height")).append(" · ").append(tr(phase)).append("\n")
                lines.append(tr("증인 응답")).append(": ").append(job.optInt("received")).append("/3\n")
                val retry=job.optLong("next_retry")
                if(retry>0)lines.append(tr("다음 재시도")).append(": ").append(java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss",java.util.Locale.getDefault()).format(java.util.Date(retry*1000))).append("\n")
                lines.append("\n")
            }
            SumuwwVerticalCaptions.builder(activity).setTitle(tr("Connection proofs")).setMessage(lines.toString()).setPositiveButton(tr("닫기"),null).show()
        })
        val controls=ui.column()
        if(offset>0)controls.addView(ui.SumuwwPrimaryButton(tr("이전")){action("blocksPrevious")}.apply{tag="blocks-previous"},ui.params(bottom=8))
        if(offset+50<total)controls.addView(ui.SumuwwPrimaryButton(tr("다음")){action("blocksNext")}.apply{tag="blocks-next"},ui.params(bottom=8))
        p.addView(controls,ui.params(top=12,bottom=12))
        if(blocks.length()>0)p.addView(ui.label("${tr("블록 높이")}: ${blocks.getJSONObject(blocks.length()-1).optInt("height")}–${blocks.getJSONObject(0).optInt("height")} / ${result.optInt("height")}",13f,ui.muted),ui.params(bottom=12))
        val list=ui.column().apply{tag="sumuww-all-blocks-list"}
        p.addView(list)
        for(i in 0 until blocks.length()){
            val block=blocks.getJSONObject(i)
            val card=ui.column().apply{tag="network-block-${block.optString("hash")}";setPadding(ui.dp(12),ui.dp(12),ui.dp(12),ui.dp(12));background=ui.surfaceFinish(12)}
            val origin=tr(when(block.optString("origin")){"local"->"이 노드";"other"->"다른 노드";else->"생성자 정보 없음"})
            card.addView(ui.label("${tr("블록 높이")} ${block.optInt("height")} · $origin",14f,ui.ink,true))
            val date=java.text.SimpleDateFormat("yyyy-MM-dd HH:mm:ss",java.util.Locale.getDefault()).format(java.util.Date(block.optLong("timestamp")*1000L))
            card.addView(ui.label("${tr("블록 시간 (현지)")}: $date",12f,ui.muted),ui.params(top=6))
            val producer=block.optString("producer_id").takeIf{it.isNotBlank()&&it!="null"}
            if(producer!=null)card.addView(ui.label("${tr("생성 노드")}: $producer",11f,ui.muted),ui.params(top=6))
            card.addView(ui.label("${tr("블록 해시")}: ${block.optString("hash")}",11f,ui.muted).apply{setTextIsSelectable(true)},ui.params(top=6))
            list.addView(card,ui.params(bottom=8))
        }
    }

    private fun more(p: LinearLayout) {
        setting(p, R.drawable.ic_info, "전체 블록", "page", "15").tag="sumuww-all-blocks"
        setting(p, R.drawable.nav_wallet, "지갑 관리", "page", "10")
        setting(p, R.drawable.ic_security, "보안 설정", "page", "11")
        setting(p, R.drawable.nav_mining, "채굴 설정", "page", "12")
        setting(p, R.drawable.ic_bell, "알림 설정", "page", "13")
        setting(p, R.drawable.ic_theme, "테마", "page", "8")
        setting(p, R.drawable.ic_language, "언어", "language", value = state.languageName)
        setting(p, R.drawable.ic_info, "도움말", "help").tag = "sumuww-help-entry"
        setting(p, R.drawable.ic_info, "처음 사용 안내", "tour").tag = "sumuww-tour-entry"

        setting(p, R.drawable.ic_info, "앱 정보", "page", "14")
    }

    private fun settings(p: LinearLayout) {
        setting(p, R.drawable.ic_security, "권한 및 동의", "consentSettings").tag="sumuww-consent-settings"
        setting(p, R.drawable.nav_wallet, "계정", "page", "10")
        setting(p, R.drawable.ic_security, "보안 설정", "page", "11")
        setting(p, R.drawable.nav_mining, "채굴 설정", "page", "12")
        setting(p, R.drawable.ic_bell, "알림 설정", "page", "13")
        setting(p, R.drawable.ic_language, "언어", "language", value = state.languageName)
        setting(p, R.drawable.ic_theme, "테마", "page", "8")

        setting(p, R.drawable.ic_info, "앱 정보", "page", "14")
    }

    private fun account(p: LinearLayout) {
        p.addView(ui.SumuwwAddressCard(tr("내 SMW 주소"), address().ifBlank { tr("지갑을 먼저 열어 주세요") }, tr("지갑 비밀번호와 복구 단어를 안전하게 보관하세요")), ui.params(bottom = 20))
        setting(p, R.drawable.nav_wallet, "지갑 열기 / 생성 / 복구", "walletManager")
        setting(p, R.drawable.ic_copy, "암호화 백업 내보내기", "exportBackup")
        setting(p, R.drawable.ic_copy, "암호화 백업 가져오기", "importBackup")
    }

    private fun security(p: LinearLayout) {
        setting(p,R.drawable.ic_security,"IP 보호","privacy",value=state.status?.optJSONObject("connection")?.optJSONObject("privacy")?.optString("mode") ?: "direct")
        val i2p=state.status?.optJSONObject("connection")?.optJSONObject("privacy")?.optString("i2p_address")?:""
        if(i2p.isNotBlank()&&i2p!="null")setting(p,R.drawable.ic_copy,"I2P","copyI2p",value=i2p)
        val prefs=activity.getSharedPreferences("sumuww-ui",0)
        setting(p,R.drawable.ic_security,"자동 보안 잠금","autoLock",value="${prefs.getInt("auto-lock-seconds",300)/60} min").tag="sumuww-auto-lock"
        p.addView(ui.label(tr("채굴 중에는 송금을 잠그고, 채굴 종료 후 지갑 키를 잠급니다."),14f,ui.muted),ui.params(bottom=16))
        setting(p, R.drawable.ic_security, "복구 단어 보기", "recoveryWords")
        setting(p, R.drawable.ic_copy, "암호화 백업 내보내기", "exportBackup")
        p.addView(ui.label(tr("오프라인에 안전하게 보관하세요. 누구든 이 단어를 알면 SMW를 사용할 수 있습니다."), 14f, ui.muted), ui.params(top = 24))
    }

    private fun miningSettings(p: LinearLayout) {
        val prefs=activity.getSharedPreferences("sumuww-ui",0)
        val exempt=activity.getSystemService(android.os.PowerManager::class.java).isIgnoringBatteryOptimizations(activity.packageName)
        setting(p,R.drawable.ic_settings,"백그라운드 실행 설정","backgroundSettings",value=tr(if(exempt)"배터리 최적화 제외됨" else "배터리 최적화 적용됨"))
        p.addView(ui.label(tr("앱은 백그라운드 CPU를 별도로 제한하지 않습니다. Android의 배터리·발열 제한은 적용될 수 있습니다."),14f,ui.muted),ui.params(bottom=16))
        setting(p,R.drawable.ic_security,"충전 중에만 채굴","chargingOnly",value=tr(if(prefs.getBoolean("charging-only",false))"켜짐" else "꺼짐")).tag="sumuww-charging-only"
        setting(p,R.drawable.ic_security,"최저 배터리","batteryLimit",value="${prefs.getInt("battery-limit",15)}%").tag="sumuww-battery-limit"
        p.addView(ui.label(tr("배터리 45°C 이상 또는 시스템 과열 상태에서는 채굴을 중지합니다. 식힌 뒤 직접 다시 시작하세요."),14f,ui.muted),ui.params(bottom=16))
        val count = ui.SumuwwField(tr(if(running())"다음 채굴 목표" else "이번 채굴 목표"), "1–10000", state.targetDraft, true, "miningTarget")
        count.second.inputType=android.text.InputType.TYPE_CLASS_NUMBER
        count.second.imeOptions=android.view.inputmethod.EditorInfo.IME_ACTION_DONE
        count.second.setOnEditorActionListener{_,id,_->if(id==android.view.inputmethod.EditorInfo.IME_ACTION_DONE){action("miningTarget",count.second.text.toString());true}else false}
        p.addView(count.first)
        p.addView(ui.SumuwwPrimaryButton(tr("적용")) { action("miningTarget", count.second.text.toString()) }.apply{tag="miningApply"}, ui.params(top = 20, bottom = 20))
        liveMetric(p,tr("CPU 사용률")){"${state.cpu}%"}
        liveMetric(p,tr("동기화 피어")){node()?.optInt("synchronized_peers")?.toString() ?: "—"}
        liveMetric(p,tr("다음 난이도 bits")){node()?.optString("next_bits", "—") ?: "—"}
        setting(p, R.drawable.ic_settings, "피어 추가", "peer")
        setting(p, R.drawable.ic_info, "상세 통계", "stats")
    }

    private fun notifications(p: LinearLayout) {
        val prefs=activity.getSharedPreferences("sumuww-ui",0)
        for((label,key,act) in listOf(Triple("입금 알림","alert-incoming","alertIncoming"),Triple("송금 확인 알림","alert-outgoing","alertOutgoing"),Triple("채굴 완료 알림","alert-mining","alertMining"))){setting(p,R.drawable.ic_bell,label,act,value=tr(if(prefs.getBoolean(key,true))"켜짐" else "꺼짐"))}
        val granted = Build.VERSION.SDK_INT < 33 || activity.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED
        metric(p, tr("앱 알림"), tr(if (granted) "허용됨" else "허용되지 않음"))
        p.addView(ui.label(tr("백그라운드 노드 및 채굴 상태는 Android 알림에 표시됩니다"), 14f, ui.muted), ui.params(top = 16, bottom = 24))
        p.addView(ui.SumuwwPrimaryButton(tr("Android 알림 설정 열기")) { action("notificationSettings") })
    }

    private fun information(p: LinearLayout) {
        val diagnostics=state.status?.optJSONObject("mobile_diagnostics")
        metric(p,tr("최근 연결 확인"),diagnostics?.optString("last_connected","—")?:"—")
        metric(p,tr("최근 상태 조회 오류"),diagnostics?.optString("last_error","—")?:"—")
        metric(p,tr("최근 피어 연결 오류"),node()?.optString("last_peer_error")?.takeIf{it.isNotBlank()&&it!="null"}?:"—")
        setting(p,R.drawable.ic_info,"상세 통계","stats")
        metric(p,tr("연결된 노드"),node()?.optInt("peers",0)?.toString()?:"—")
        metric(p,tr("동기화 피어"),node()?.optInt("synchronized_peers",0)?.toString()?:"—")
        state.status?.optJSONObject("mobile_batch")?.optString("protection_reason")?.takeIf{it.isNotBlank()&&it!="null"}?.let{p.addView(ui.label(tr(it),14f,ui.negative),ui.params(bottom=12))}
        p.addView(ui.logo(), ui.params(ui.dp(if(LocaleBrand.isLocalized(activity))184 else 104), ui.dp(if(LocaleBrand.isLocalized(activity))104 else 72), top = 20, bottom = 24).apply { gravity = Gravity.CENTER })
        p.addView(ui.label(tr("SUMUWW"), 32f, ui.ink, true).apply { gravity = Gravity.CENTER }, ui.params(bottom = 8))
        p.addView(ui.label("Open Connections\nGreater Tomorrow.", 14f, ui.muted).apply { gravity = Gravity.CENTER }, ui.params(bottom = 32))
        metric(p, tr("앱 버전"), activity.packageManager.getPackageInfo(activity.packageName, 0).versionName ?: "—")
        setting(p, R.drawable.ic_info, "업데이트 확인", "checkUpdates").tag = "sumuww-update-check"
        metric(p, tr("네트워크"), tr("SUMUWW"))
        metric(p, tr("블록 높이"), node()?.optInt("height")?.toString() ?: "—")
        setting(p, R.drawable.ic_info, "도움말", "help")
    }

    private fun themes(p: LinearLayout) {
        setting(p, R.drawable.ic_theme, "라이트·다크", "mode", value = tr(when (state.themeMode) { "light" -> "라이트 모드"; "dark" -> "다크 모드"; else -> "시스템 설정" }))
        val seasons = setOf("spring", "summer", "autumn", "winter")
        val saved = SumuwwThemeCalendar.savedPalette(activity.getSharedPreferences("sumuww-ui", Activity.MODE_PRIVATE).getString("palette", "default"))
        val groups = listOf("기본 테마" to SumuwwTheme.manualPalettes.filter { it.id == "default" },
            "색상 테마" to SumuwwTheme.manualPalettes.filter { it.id != "default" && it.id !in seasons },
            "계절 테마" to SumuwwTheme.manualPalettes.filter { it.id in seasons })
        groups.forEach { (caption, palettes) ->
            p.addView(ui.section(tr(caption)))
            palettes.chunked(2).forEach { pair ->
                val row = ui.row()
                pair.forEach { theme -> row.addView(ui.SumuwwThemePreview(theme, theme.id == saved.id, tr(theme.label)) { action("selectPalette", theme.id) }, LinearLayout.LayoutParams(0, -2, 1f).apply { leftMargin = ui.dp(4); rightMargin = ui.dp(4) }) }
                if (pair.size == 1) row.addView(View(activity), LinearLayout.LayoutParams(0, 0, 1f))
                p.addView(row, ui.params(bottom = 12))
            }
        }
        p.addView(ui.section(tr("크리스마스 자동 적용")))
        p.addView(ui.label(tr("매년 12월 18일 00:00부터 12월 26일 00:00까지 · 휴대폰 현지 시간 기준"), 13f, ui.muted))
        if (state.palette.id == "christmas") {
            p.addView(ui.label(tr("크리스마스 기간에 선택한 테마는 종료 후 적용됩니다"), 13f, ui.muted), ui.params(top = 12))
            metric(p, tr("종료 후 테마"), tr(saved.label))
        }
    }

    private fun help(p: LinearLayout) {
        p.addView(ui.SumuwwSettingRow(R.drawable.ic_info, DocumentationActivity.title(activity), "0.6.91") { action("documents") }.apply { tag = "sumuww-documents-entry" })
        val page = SumuwwHelp.page(activity, UiLanguage.code(activity))
        p.addView(ui.label(page.subtitle, 14f, ui.muted), ui.params(bottom = 16))
        page.topics.forEach { topic ->
            p.addView(ui.section(topic.title).apply { tag = "sumuww-help-${topic.id}" })
            p.addView(ui.label(topic.body, 14f, ui.muted), ui.params(bottom = 8))
        }
    }

    private fun actions(p: LinearLayout, items: List<Triple<Int, String, String>>) {
        val line = ui.row().apply{if(ui.verticalMongolian)gravity=Gravity.TOP}
        items.forEach { (resource, label, route) ->
            val button = ui.SumuwwActionButton(resource, tr(label)) { if (route.toIntOrNull() != null) action("page", route) else action(route) }
            if (label == "거래내역") button.tag = "sumuww-history-entry"
            line.addView(button, LinearLayout.LayoutParams(0, -2, 1f))
        }
        p.addView(line, ui.params(bottom = 8))
    }

    private fun setting(p: LinearLayout, icon: Int, caption: String, operation: String, arg: String = "", value: String = ""): LinearLayout {
        val row = ui.SumuwwSettingRow(icon, tr(caption), value) { action(operation, arg) }
        p.addView(row); p.addView(ui.divider()); return row
    }
    private fun liveMetric(p:LinearLayout,caption:String,value:()->String){
        val row=ui.row().apply{setPadding(0,ui.dp(14),0,ui.dp(14))}
        row.addView(ui.label(caption,14f,ui.muted),LinearLayout.LayoutParams(0,-2,1f))
        row.addView(miningText(ui.label("",15f,ui.ink,true),value),LinearLayout.LayoutParams(0,-2,1f).apply{gravity=Gravity.END})
        p.addView(row);p.addView(ui.divider())
    }
    private fun metric(p: LinearLayout, caption: String, value: String) {
        val row = ui.row().apply { setPadding(0, ui.dp(14), 0, ui.dp(14)) }
        row.addView(ui.label(caption, 14f, ui.muted), LinearLayout.LayoutParams(0, -2, 1f))
        row.addView(ui.label(value, 15f, ui.ink, true), LinearLayout.LayoutParams(0, -2, 1f).apply { gravity = Gravity.END })
        p.addView(row); p.addView(ui.divider())
    }
    private fun transaction(p: LinearLayout, tx: JSONObject) {
        val kind = kind(tx); val raw = tx.optLong("net_amount")
        val name = tr(when (kind) { "send" -> "보내기"; "receive" -> "받기"; else -> "채굴 보상" })
        val detail = when (tx.optString("status")) { "replaced" -> tr(if (tx.optString("replacement_reason") == "ancestor_replaced") "Removed after parent replacement" else "Replaced · not applied"); "pending" -> tr("대기 중"); else -> "${tx.optInt("confirmations")} ${tr("확인") }" }
        p.addView(ui.SumuwwTransactionRow(name, "${if (raw > 0) "+" else ""}${formatUnits(raw)} SMW", detail, kind) { action("transaction", tx.toString()) })
        tx.optJSONObject("mining_reward")?.let { reward ->
            for ((caption, field) in listOf("New issuance (block)" to "subsidy_reward_smw", "Transaction fees (block)" to "fee_reward_smw", "Total block reward" to "claimed_reward_smw")) {
                val value = if (reward.isNull(field)) "—" else reward.optString(field) + " SMW"
                metric(p, tr(caption), value)
            }
            if (reward.optString("allocation") == "underclaimed") p.addView(ui.label(tr("Reward not fully claimed"), 13f, ui.muted))
        }
        p.addView(ui.divider())
    }
    private fun kind(tx: JSONObject) = if (tx.optBoolean("coinbase")) "mining" else if (tx.optLong("net_amount") < 0) "send" else "receive"
    private fun formatUnits(value: Long): String = java.math.BigDecimal.valueOf(value, 8).stripTrailingZeros().toPlainString()
    private fun amount(key: String): String {
        val raw = state.status?.optJSONObject("wallet")?.optString(key, "—") ?: "—"
        return try { java.text.DecimalFormat("#,##0.########", java.text.DecimalFormatSymbols(java.util.Locale.US)).format(java.math.BigDecimal(raw)) } catch (_: NumberFormatException) { raw }
    }
    private fun address() = state.status?.optJSONObject("wallet")?.optString("address", "") ?: ""
    private fun shortAddress(address: String) = if (address.length > 25) address.take(12) + "…" + address.takeLast(8) else address
    private fun node() = if(state.statusUnavailable)null else state.status?.optJSONObject("node")
    private fun running() = state.status?.optJSONObject("mobile_batch")?.optBoolean("running", false) == true
    private fun miningLabel(): String {
        val mining = state.status?.optJSONObject("mining")
        return when {
            state.statusUnavailable -> tr("상태 확인 불가")
            !running() -> tr("채굴 대기")
            mining?.optString("state") == "waiting" -> tr("동기화 대기")
            mining?.optString("mode") == "offline" -> tr("오프라인 채굴")
            else -> tr("채굴 중")
        }
    }
    private fun completed() = state.status?.optJSONObject("mobile_batch")?.optInt("completed", 0) ?: 0
    private fun target() = state.status?.optJSONObject("mobile_batch")?.optInt("target", 0) ?: 0
    private fun subsidy() = state.status?.optString("current_subsidy_smw", "—") ?: "—"
    private fun syncState() = if(state.statusUnavailable)tr("상태 확인 불가") else if (node()?.optBoolean("mining_ready", false) == true) tr("준비됨") else tr("대기")
    private fun tr(value: String) = translate(value)
    private fun action(operation: String, first: String = "", second: String = "") = dispatch(operation, first, second)
}

