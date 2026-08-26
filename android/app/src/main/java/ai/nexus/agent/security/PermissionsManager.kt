package ai.nexus.agent.security

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.PowerManager
import androidx.core.content.ContextCompat
import ai.nexus.agent.service.NexusAccessibilityService
import ai.nexus.agent.service.NexusNotificationListenerService

/**
 * Tracks and reports official Android runtime permissions.
 */
class PermissionsManager(private val context: Context) {

    fun hasPermission(permission: String): Boolean {
        return ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED
    }

    fun getPermissionReport(deviceId: String): Map<String, Any> {
        val powerManager = context.getSystemService(Context.POWER_SERVICE) as? PowerManager
        val isBatteryOptIgnored = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            powerManager?.isIgnoringBatteryOptimizations(context.packageName) ?: false
        } else {
            true
        }

        val hasStorage = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasPermission(Manifest.permission.READ_MEDIA_IMAGES) || hasPermission(Manifest.permission.READ_MEDIA_AUDIO)
        } else {
            hasPermission(Manifest.permission.READ_EXTERNAL_STORAGE)
        }

        val hasNotifsPost = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            hasPermission(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            true
        }

        return mapOf(
            "device_id" to deviceId,
            "accessibility_enabled" to NexusAccessibilityService.isServiceRunning,
            "notification_listener_enabled" to NexusNotificationListenerService.isListening,
            "microphone_granted" to hasPermission(Manifest.permission.RECORD_AUDIO),
            "camera_granted" to hasPermission(Manifest.permission.CAMERA),
            "storage_granted" to hasStorage,
            "sms_granted" to hasPermission(Manifest.permission.SEND_SMS),
            "phone_granted" to hasPermission(Manifest.permission.CALL_PHONE),
            "notifications_post_granted" to hasNotifsPost,
            "battery_optimization_ignored" to isBatteryOptIgnored
        )
    }
}
