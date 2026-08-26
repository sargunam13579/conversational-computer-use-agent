package ai.nexus.agent.service

import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class MobileNotification(
    val id: String,
    val packageName: String,
    val appName: String,
    val title: String,
    val text: String,
    val timestamp: String,
    val isOngoing: Boolean
)

/**
 * Official Android NotificationListenerService for capturing incoming notifications.
 */
class NexusNotificationListenerService : NotificationListenerService() {

    companion object {
        var instance: NexusNotificationListenerService? = null
            private set

        val isListening: Boolean
            get() = instance != null

        private val recentNotifications = mutableListOf<MobileNotification>()

        fun getBufferedNotifications(): List<MobileNotification> {
            return synchronized(recentNotifications) {
                recentNotifications.toList()
            }
        }
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        instance = this
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        instance = null
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        sbn ?: return
        val extras = sbn.notification.extras ?: return

        val title = extras.getCharSequence("android.title")?.toString() ?: ""
        val text = extras.getCharSequence("android.text")?.toString() ?: ""
        val pkg = sbn.packageName ?: ""
        
        if (title.isBlank() && text.isBlank()) return

        val appName = try {
            val appInfo = packageManager.getApplicationInfo(pkg, 0)
            packageManager.getApplicationLabel(appInfo).toString()
        } catch (e: Exception) {
            pkg
        }

        val sdf = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US)
        val notif = MobileNotification(
            id = "${sbn.id}_${sbn.postTime}",
            packageName = pkg,
            appName = appName,
            title = title,
            text = text,
            timestamp = sdf.format(Date(sbn.postTime)),
            isOngoing = sbn.isOngoing
        )

        synchronized(recentNotifications) {
            recentNotifications.add(notif)
            if (recentNotifications.size > 50) {
                recentNotifications.removeAt(0)
            }
        }

        // Notify running background agent service
        NexusAgentService.instance?.sendNotificationToServer(notif)
    }

    override fun onNotificationRemoved(sbn: StatusBarNotification?) {
        // Handled if removal synchronization is needed
    }
}
