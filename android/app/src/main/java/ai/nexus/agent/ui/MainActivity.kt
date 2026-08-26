package ai.nexus.agent.ui

import android.content.Intent
import android.os.Build
import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AppCompatActivity
import ai.nexus.agent.security.PermissionsManager
import ai.nexus.agent.service.NexusAgentService

/**
 * Main Activity handling pairing setup, permission checklists, and status indicators.
 */
class MainActivity : AppCompatActivity() {

    private lateinit var permissionsManager: PermissionsManager
    private lateinit var statusText: TextView
    private lateinit var pairCodeInput: EditText
    private lateinit var pairButton: Button
    private lateinit var startServiceButton: Button

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        permissionsManager = PermissionsManager(this)
        
        // Dynamic layout or binding setup
        setupUI()
    }

    private fun setupUI() {
        // Simple programmatic or view layout for pairing and permissions verification
        statusText = TextView(this).apply {
            text = "NEXUS Agent Ready. Enter pairing code to connect with your PC."
            textSize = 16f
            setPadding(32, 32, 32, 16)
        }
        
        refreshStatus()
    }

    override fun onResume() {
        super.onResume()
        refreshStatus()
    }

    private fun refreshStatus() {
        val perms = permissionsManager.getPermissionReport("local_device")
        val a11yOn = perms["accessibility_enabled"] as Boolean
        val notifOn = perms["notification_listener_enabled"] as Boolean

        val sb = StringBuilder()
        sb.append("NEXUS Mobile Agent Status\n\n")
        sb.append("• Accessibility Service: ").append(if (a11yOn) "Active ✅" else "Disabled ⚠️").append("\n")
        sb.append("• Notification Listener: ").append(if (notifOn) "Active ✅" else "Disabled ⚠️").append("\n")
        sb.append("• Microphone Permission: ").append(if (perms["microphone_granted"] as Boolean) "Granted ✅" else "Denied ❌").append("\n")
        sb.append("• Camera Permission: ").append(if (perms["camera_granted"] as Boolean) "Granted ✅" else "Denied ❌").append("\n")
        
        statusText.text = sb.toString()
    }

    fun startAgentService() {
        val intent = Intent(this, NexusAgentService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        Toast.makeText(this, "NEXUS Agent Service Started", Toast.LENGTH_SHORT).show()
    }
}
