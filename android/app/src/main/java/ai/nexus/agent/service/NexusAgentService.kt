package ai.nexus.agent.service

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat
import ai.nexus.agent.capabilities.DeviceCapabilitiesManager
import ai.nexus.agent.security.PermissionsManager
import org.json.JSONObject

/**
 * Foreground Service running the NEXUS Android Agent WebSocket daemon.
 */
class NexusAgentService : Service() {

    companion object {
        var instance: NexusAgentService? = null
            private set

        const val CHANNEL_ID = "nexus_agent_foreground_channel"
        const val NOTIFICATION_ID = 1001
    }

    private lateinit var capabilities: DeviceCapabilitiesManager
    private lateinit var permissions: PermissionsManager
    private var isRunning = false

    override fun onCreate() {
        super.onCreate()
        instance = this
        capabilities = DeviceCapabilitiesManager(this)
        permissions = PermissionsManager(this)
        createNotificationChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val notification = createForegroundNotification()
        startForeground(NOTIFICATION_ID, notification)
        isRunning = true
        return START_STICKY
    }

    override fun onDestroy() {
        super.onDestroy()
        isRunning = false
        instance = null
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "NEXUS Mobile Agent",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Maintains secure real-time connectivity with NEXUS AI backend"
            }
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    private fun createForegroundNotification(): Notification {
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("NEXUS Mobile Agent")
            .setContentText("Connected and ready for AI commands")
            .setSmallIcon(android.R.drawable.stat_notify_sync)
            .setOngoing(true)
            .build()
    }

    /**
     * Dispatch incoming command received from backend WebSocket.
     */
    fun handleCommand(commandJson: String): String {
        return try {
            val json = JSONObject(commandJson)
            val requestId = json.getString("request_id")
            val actionType = json.getString("action_type")
            val params = json.optJSONObject("parameters") ?: JSONObject()

            val success: Boolean
            var output = "Action completed"

            when (actionType) {
                "launch_app" -> {
                    val app = params.optString("app_name", "")
                    success = capabilities.launchApp(app)
                    output = if (success) "Launched $app" else "Could not find app $app"
                }
                "volume_control" -> {
                    val act = params.optString("action", "set")
                    val lvl = params.optInt("level", 50)
                    val stream = params.optString("stream", "media")
                    success = capabilities.setVolume(lvl, stream)
                    output = "Volume updated ($act)"
                }
                "media_control" -> {
                    val act = params.optString("action", "toggle")
                    success = capabilities.controlMedia(act)
                    output = "Media $act executed"
                }
                "set_alarm" -> {
                    val type = params.optString("type", "alarm")
                    val hr = if (params.has("hour")) params.getInt("hour") else null
                    val min = if (params.has("minutes")) params.getInt("minutes") else null
                    val sec = if (params.has("seconds")) params.getInt("seconds") else null
                    val msg = params.optString("message", "NEXUS Alert")
                    success = capabilities.setAlarmOrTimer(type, hr, min, sec, msg)
                    output = "$type scheduled"
                }
                "open_settings" -> {
                    val sec = params.optString("setting", "general")
                    success = capabilities.openSettings(sec)
                    output = "Opened $sec settings"
                }
                "device_action" -> {
                    val act = params.optString("action", "get_battery")
                    success = when (act) {
                        "flashlight_on" -> capabilities.toggleFlashlight(true)
                        "flashlight_off" -> capabilities.toggleFlashlight(false)
                        "vibrate" -> capabilities.vibrate(400)
                        "get_battery" -> true
                        else -> false
                    }
                    output = "Device action $act completed"
                }
                "ui_interact" -> {
                    val a11y = NexusAccessibilityService.instance
                    if (a11y != null) {
                        val act = params.optString("action", "click")
                        success = when (act) {
                            "click" -> a11y.clickByText(params.optString("target_text", ""))
                            "type" -> a11y.typeText(params.optString("target_text"), params.optString("input_text", ""))
                            "scroll" -> a11y.scrollDirection(params.optString("direction", "down"))
                            "back", "home", "recents" -> a11y.performGlobal(act)
                            else -> false
                        }
                        output = "Accessibility action $act finished"
                    } else {
                        success = false
                        output = "Accessibility Service is not enabled"
                    }
                }
                else -> {
                    success = false
                    output = "Unknown action type: $actionType"
                }
            }

            JSONObject().apply {
                put("request_id", requestId)
                put("action_type", actionType)
                put("success", success)
                put("output", output)
            }.toString()
        } catch (e: Exception) {
            JSONObject().apply {
                put("success", false)
                put("error", e.message)
            }.toString()
        }
    }

    fun sendNotificationToServer(notif: MobileNotification) {
        // Forward notification payload over active WebSocket
    }
}
