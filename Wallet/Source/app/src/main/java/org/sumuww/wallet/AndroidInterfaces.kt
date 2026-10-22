package org.sumuww.wallet

import android.content.Context
import android.net.ConnectivityManager
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.NetworkInterface
import org.json.JSONArray
import org.json.JSONObject

/** Local interface addresses only. No external IP service or NAT assumptions. */
object AndroidInterfaces {
    @Volatile private var appContext: Context? = null
    fun configure(context: Context) { appContext = context.applicationContext }

    @JvmStatic fun networkIdentity(): String {
        val manager = appContext?.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
            ?: return ""
        val network = manager.activeNetwork ?: return ""
        val links = manager.getLinkProperties(network) ?: return ""
        val addresses = links.linkAddresses.map { it.toString() }.sorted().joinToString(",")
        return "${network.networkHandle}|${links.interfaceName}|$addresses"
    }

    @JvmStatic fun read(): String {
        val result = JSONArray()
        val seen = mutableSetOf<String>()
        val interfaces = NetworkInterface.getNetworkInterfaces() ?: return result.toString()
        val manager = appContext?.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        val activeInterface = manager?.activeNetwork?.let { manager.getLinkProperties(it)?.interfaceName }
        var count = 0
        var addressCount = 0
        while (interfaces.hasMoreElements()) {
            check(++count <= 64) { "Too many network interfaces" }
            val item = interfaces.nextElement()
            if (!item.isUp || item.isLoopback) continue
            // Default-route sockets use this network. An up cellular adapter
            // may remain present while Wi-Fi is active, without a usable
            // inbound path for this application. Do not publish it as ours.
            if (activeInterface != null && item.name != activeInterface) continue
            for (entry in item.interfaceAddresses) {
                check(++addressCount <= 128) { "Too many interface addresses" }
                val address = entry.address
                if (address !is Inet4Address && address !is Inet6Address) continue
                if (address.isLoopbackAddress || address.isLinkLocalAddress) continue
                val host = address.hostAddress?.substringBefore("%") ?: continue
                if (seen.add(host)) result.put(JSONObject().put("host", host).put("index", item.index.coerceAtLeast(0)))
            }
        }
        return result.toString()
    }
}
