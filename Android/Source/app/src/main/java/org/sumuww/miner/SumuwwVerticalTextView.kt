package org.sumuww.miner

import android.content.Context
import android.graphics.Rect
import android.graphics.Bitmap
import android.graphics.Paint
import android.graphics.Canvas
import android.graphics.Typeface
import android.text.Layout
import android.text.StaticLayout
import android.text.TextDirectionHeuristics
import android.text.TextPaint
import android.view.Gravity
import android.view.View
import android.widget.TextView
import kotlin.math.ceil
import kotlin.math.max

/** Word-aware Mongolian columns. Latin names and numbers remain horizontal. */
internal class SumuwwVerticalTextView(context: Context) : TextView(context) {
    var verticalInlineDp = 72f
    var verticalTextSizeCapSp = 16f
    var verticalSection = false
    private data class Run(val layout: StaticLayout, val vertical: Boolean, val x: Float, val y: Float)
    private val rasterCache = java.util.IdentityHashMap<StaticLayout,Bitmap>()
    private fun raster(layout:StaticLayout):Bitmap = rasterCache.getOrPut(layout) {
        // Contextual glyph extents must be measured after shaping, not from
        // Paint.getTextBounds. Keep a full em guard for overhanging ink.
        val guard=ceil(layout.paint.textSize.toDouble()).toInt()+4
        val image=Bitmap.createBitmap(layout.width+guard*2,layout.height+guard*2,Bitmap.Config.ARGB_8888)
        val canvas=Canvas(image);canvas.translate(guard.toFloat(),guard.toFloat());layout.draw(canvas)
        val pixels=IntArray(image.width*image.height)
        image.getPixels(pixels,0,image.width,0,0,image.width,image.height)
        var left=image.width;var top=image.height;var right=-1;var bottom=-1
        for(y in 0 until image.height)for(x in 0 until image.width)if(pixels[y*image.width+x] ushr 24 != 0){
            left=minOf(left,x);top=minOf(top,y);right=maxOf(right,x);bottom=maxOf(bottom,y)
        }
        val result=if(right<0)Bitmap.createBitmap(1,1,Bitmap.Config.ARGB_8888)else{
            left=(left-2).coerceAtLeast(0);top=(top-2).coerceAtLeast(0)
            right=(right+2).coerceAtMost(image.width-1);bottom=(bottom+2).coerceAtMost(image.height-1)
            Bitmap.createBitmap(image,left,top,right-left+1,bottom-top+1)
        }
        if(result!==image)image.recycle()
        result
    }
    private fun inkWidth(layout:StaticLayout)=raster(layout).width
    private fun inkHeight(layout:StaticLayout)=raster(layout).height
    private val rasterPaint=Paint(Paint.ANTI_ALIAS_FLAG)
    private var runs = emptyList<Run>()
    private var blockWidth = 0f
    private var blockHeight = 0f
    val usesVerticalMongolian: Boolean
        get() = text?.any { it in '\u1800'..'\u18af' } == true

    internal val contentFitsMeasuredBounds:Boolean
        get() = !usesVerticalMongolian || (blockWidth <= measuredWidth-paddingLeft-paddingRight+1 && blockHeight <= measuredHeight-paddingTop-paddingBottom+1)

    private fun shape(value: String, maxWidth: Int): StaticLayout {
        val brush = TextPaint(paint).apply {
            typeface = if(value.any { it in '\u1800'..'\u18af' }) mongolianTypeface(context) else Typeface.create("sans-serif",Typeface.NORMAL)
            textSize = minOf(textSize, verticalTextSizeCapSp * resources.displayMetrics.scaledDensity)
            color = currentTextColor
        }
        val width = ceil(Layout.getDesiredWidth(value,brush).toDouble()).toInt().coerceIn(1,maxWidth)
        return StaticLayout.Builder.obtain(value,0,value.length,brush,width)
            .setTextDirection(TextDirectionHeuristics.LTR).setIncludePad(true)
            .setBreakStrategy(Layout.BREAK_STRATEGY_SIMPLE).setHyphenationFrequency(Layout.HYPHENATION_FREQUENCY_NONE).build()
    }

    override fun onMeasure(widthMeasureSpec:Int,heightMeasureSpec:Int) {
        rasterCache.values.forEach{it.recycle()};rasterCache.clear()
        if(!usesVerticalMongolian) { runs=emptyList();super.onMeasure(widthMeasureSpec,heightMeasureSpec);return }
        val available = max(1,(if(View.MeasureSpec.getMode(widthMeasureSpec)==View.MeasureSpec.UNSPECIFIED)
            resources.displayMetrics.widthPixels else View.MeasureSpec.getSize(widthMeasureSpec))-paddingLeft-paddingRight)
        val pieces = Regex("[\\u1800-\\u18af\\u200c\\u200d\\u202f]+|[A-Za-z0-9][A-Za-z0-9:.,/_%+@=()\\-]*|[^ \\t\\n]|[ \\t]+|\\n").findAll(text).map { it.value }.toList()
        val shaped = pieces.map { value -> if(value.isBlank()) null else shape(value,if(value.any{it in '\u1800'..'\u18af'})32768 else available) }
        val gap = 4f*resources.displayMetrics.density
        val longest = shaped.mapIndexedNotNull { index, layout -> layout?.let { if(pieces[index].any{it in '\u1800'..'\u18af'})inkWidth(it).toFloat() else inkHeight(it).toFloat() } }.maxOrNull()?:1f
        var inline=max(verticalInlineDp*resources.displayMetrics.density,longest)
        fun arrange() {
            val columns=mutableListOf<MutableList<Pair<Int,Float>>>()
            var column=mutableListOf<Pair<Int,Float>>();var y=0f
            for(index in pieces.indices) {
                val value=pieces[index];val layout=shaped[index]
                if(value=="\n") { if(column.isNotEmpty())columns.add(column);column=mutableListOf();y=0f;continue }
                if(layout==null) { if(column.isNotEmpty())y+=gap;continue }
                val advance=if(value.any{it in '\u1800'..'\u18af'})inkWidth(layout).toFloat() else inkHeight(layout).toFloat()
                if(column.isNotEmpty()&&y+advance>inline) { columns.add(column);column=mutableListOf();y=0f }
                column.add(index to y);y+=advance+resources.displayMetrics.density
            }
            if(column.isNotEmpty())columns.add(column)
            var x=0f;var height=0f;val result=mutableListOf<Run>()
            for(col in columns) {
                val cross=col.maxOf { (index,_)->val layout=shaped[index]!!;if(pieces[index].any{it in '\u1800'..'\u18af'})inkHeight(layout).toFloat() else inkWidth(layout).toFloat() }
                for((index,offset) in col) {
                    val layout=shaped[index]!!;val vertical=pieces[index].any{it in '\u1800'..'\u18af'}
                    val actualCross=if(vertical)inkHeight(layout).toFloat() else inkWidth(layout).toFloat()
                    result.add(Run(layout,vertical,x+(cross-actualCross)/2,offset))
                    height=max(height,offset+if(vertical)inkWidth(layout) else inkHeight(layout))
                }
                x+=cross+gap
            }
            runs=result;blockWidth=max(1f,x-gap);blockHeight=max(1f,height)
        }
        arrange()
        while(blockWidth>available&&inline<32768) { inline*=1.5f;arrange() }
        setMeasuredDimension(resolveSize(max(suggestedMinimumWidth,ceil(blockWidth.toDouble()).toInt()+paddingLeft+paddingRight),widthMeasureSpec),
            resolveSize(max(suggestedMinimumHeight,ceil(blockHeight.toDouble()).toInt()+paddingTop+paddingBottom),heightMeasureSpec))
    }

    override fun onDraw(canvas:Canvas) {
        if(!usesVerticalMongolian) { super.onDraw(canvas);return }
        val x=paddingLeft+if(gravity and Gravity.HORIZONTAL_GRAVITY_MASK==Gravity.CENTER_HORIZONTAL)max(0f,width-paddingLeft-paddingRight-blockWidth)/2 else 0f
        val y=paddingTop+if(gravity and Gravity.VERTICAL_GRAVITY_MASK==Gravity.CENTER_VERTICAL)max(0f,height-paddingTop-paddingBottom-blockHeight)/2 else 0f
        for(run in runs) {
            canvas.save()
            if(run.vertical) { canvas.translate(x+run.x+inkHeight(run.layout),y+run.y);canvas.rotate(90f) }
            else canvas.translate(x+run.x,y+run.y)
            rasterPaint.colorFilter=android.graphics.PorterDuffColorFilter(currentTextColor,android.graphics.PorterDuff.Mode.SRC_IN)
            canvas.drawBitmap(raster(run.layout),0f,0f,rasterPaint);canvas.restore()
        }
    }
    companion object {
        @Volatile private var font:Typeface?=null
        private fun mongolianTypeface(context:Context):Typeface=font?:synchronized(this) {
            font?:Typeface.createFromAsset(context.assets,"fonts/NotoSansMongolian-Regular.ttf").also{font=it}
        }
    }
}
