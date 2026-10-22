package org.sumuww.miner

import java.time.LocalDate
import java.time.Month
import java.time.ZonedDateTime

/** Local display policy only. The saved manual palette is never overwritten by the holiday. */
object SumuwwThemeCalendar {
    fun isChristmas(now: ZonedDateTime): Boolean =
        now.month == Month.DECEMBER && now.dayOfMonth in 18..25

    fun savedPalette(id: String?): SumuwwTheme.Palette =
        SumuwwTheme.manualPalettes.firstOrNull { it.id == id }
            ?: if (id == "cherry") SumuwwTheme.selected("pink") else SumuwwTheme.selected("default")

    fun resolve(id: String?, now: ZonedDateTime = ZonedDateTime.now()): SumuwwTheme.Palette =
        if (isChristmas(now)) SumuwwTheme.selected("christmas") else savedPalette(id)

    fun nextTransition(now: ZonedDateTime): ZonedDateTime {
        val start = LocalDate.of(now.year, Month.DECEMBER, 18).atStartOfDay(now.zone)
        val end = LocalDate.of(now.year, Month.DECEMBER, 26).atStartOfDay(now.zone)
        return when {
            now.isBefore(start) -> start
            now.isBefore(end) -> end
            else -> LocalDate.of(now.year + 1, Month.DECEMBER, 18).atStartOfDay(now.zone)
        }
    }
}
