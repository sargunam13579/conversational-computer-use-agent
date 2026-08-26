package ai.nexus.agent.capabilities

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.os.BatteryManager
import android.os.Build
import android.os.Vibrator
import android.os.VibrationEffect
import android.provider.AlarmClock
import android.provider.Settings
import android.view.KeyEvent
import java.io.File

/**
 * Executes supported native Android device actions through official Android SDK APIs.
 */
class DeviceCapabilitiesManager(private val context: Context) {

    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager

    /**
     * Launch an application by name or package.
     */
    fun launchApp(appNameOrPackage: String): Boolean {
        val pm = context.packageManager
        // 1. Try direct package intent
        var intent = pm.getLaunchIntentForPackage(appNameOrPackage)

        // 2. Search installed packages by label
        if (intent == null) {
            val installed = pm.getInstalledApplications(0)
            val matched = installed.firstOrNull {
                pm.getApplicationLabel(it).toString().equals(appNameOrPackage, ignoreCase = true) ||
                it.packageName.contains(appNameOrPackage, ignoreCase = true)
            }
            if (matched != null) {
                intent = pm.getLaunchIntentForPackage(matched.packageName)
            }
        }

        return if (intent != null) {
            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            context.startActivity(intent)
            true
        } else {
            false
        }
    }

    /**
     * Set stream volume level (0-100 scale normalized to system volume steps).
     */
    fun setVolume(levelPercent: Int, stream: String = "media"): Boolean {
        val streamType = when (stream.lowercase()) {
            "ring" -> AudioManager.STREAM_RING
            "alarm" -> AudioManager.STREAM_ALARM
            "notification" -> AudioManager.STREAM_NOTIFICATION
            else -> AudioManager.STREAM_MUSIC
        }
        val maxVol = audioManager.getStreamMaxVolume(streamType)
        val targetVol = (levelPercent.coerceIn(0, 100) * maxVol) / 100
        audioManager.setStreamVolume(streamType, targetVol, AudioManager.FLAG_SHOW_UI)
        return true
    }

    /**
     * Control media playback using media key events.
     */
    fun controlMedia(action: String): Boolean {
        val keyCode = when (action.lowercase()) {
            "play" -> KeyEvent.KEYCODE_MEDIA_PLAY
            "pause" -> KeyEvent.KEYCODE_MEDIA_PAUSE
            "next" -> KeyEvent.KEYCODE_MEDIA_NEXT
            "previous", "prev" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS
            else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE
        }
        val down = KeyEvent(KeyEvent.ACTION_DOWN, keyCode)
        val up = KeyEvent(KeyEvent.ACTION_UP, keyCode)
        audioManager.dispatchMediaKeyEvent(down)
        audioManager.dispatchMediaKeyEvent(up)
        return true
    }

    /**
     * Set alarm or countdown timer using official AlarmClock Intent.
     */
    fun setAlarmOrTimer(type: String, hour: Int?, minutes: Int?, seconds: Int?, message: String?): Boolean {
        val intent = when (type.lowercase()) {
            "timer" -> {
                Intent(AlarmClock.ACTION_SET_TIMER).apply {
                    putExtra(AlarmClock.EXTRA_LENGTH, seconds ?: 60)
                    putExtra(AlarmClock.EXTRA_MESSAGE, message ?: "NEXUS Timer")
                    putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                }
            }
            else -> {
                Intent(AlarmClock.ACTION_SET_ALARM).apply {
                    putExtra(AlarmClock.EXTRA_HOUR, hour ?: 8)
                    putExtra(AlarmClock.EXTRA_MINUTES, minutes ?: 0)
                    putExtra(AlarmClock.EXTRA_MESSAGE, message ?: "NEXUS Alarm")
                    putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                }
            }
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        return try {
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Open system settings pages via official Intents.
     */
    fun openSettings(section: String): Boolean {
        val action = when (section.lowercase()) {
            "wifi" -> Settings.ACTION_WIFI_SETTINGS
            "bluetooth" -> Settings.ACTION_BLUETOOTH_SETTINGS
            "battery" -> Intent.ACTION_POWER_USAGE_SUMMARY
            "accessibility" -> Settings.ACTION_ACCESSIBILITY_SETTINGS
            "display" -> Settings.ACTION_DISPLAY_SETTINGS
            "sound" -> Settings.ACTION_SOUND_SETTINGS
            else -> Settings.ACTION_SETTINGS
        }
        val intent = Intent(action).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        return try {
            context.startActivity(intent)
            true
        } catch (e: Exception) {
            false
        }
    }

    /**
     * Toggle device flashlight via CameraManager.
     */
    fun toggleFlashlight(enable: Boolean): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val cameraManager = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            return try {
                val cameraId = cameraManager.cameraIdList.firstOrNull() ?: return false
                cameraManager.setTorchMode(cameraId, enable)
                true
            } catch (e: Exception) {
                false
            }
        }
        return false
    }

    /**
     * Vibrate phone.
     */
    fun vibrate(durationMs: Long = 400): Boolean {
        val vibrator = context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator.vibrate(VibrationEffect.createOneShot(durationMs, VibrationEffect.DEFAULT_AMPLITUDE))
        } else {
            @Suppress("DEPRECATION")
            vibrator.vibrate(durationMs)
        }
        return true
    }

    /**
     * Get current battery status and percentage.
     */
    fun getBatteryInfo(): Map<String, Any> {
        val batteryManager = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        val level = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
        val isCharging = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val status = batteryManager.getIntProperty(BatteryManager.BATTERY_PROPERTY_STATUS)
            status == BatteryManager.BATTERY_STATUS_CHARGING || status == BatteryManager.BATTERY_STATUS_FULL
        } else {
            false
        }
        return mapOf("percent" to level, "is_charging" to isCharging)
    }
}
