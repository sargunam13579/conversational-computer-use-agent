package ai.nexus.agent.service

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Bundle
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * NEXUS Accessibility Service.
 * Provides official UI navigation, node clicks, text input, and global navigation gestures.
 */
class NexusAccessibilityService : AccessibilityService() {

    companion object {
        var instance: NexusAccessibilityService? = null
            private set

        val isServiceRunning: Boolean
            get() = instance != null
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // Track active window or screen changes if permitted
    }

    override fun onInterrupt() {
        instance = null
    }

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }

    /**
     * Search accessibility node tree by text and trigger a click action.
     */
    fun clickByText(text: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val matchedNodes = root.findAccessibilityNodeInfosByText(text)
        for (node in matchedNodes) {
            if (node.isClickable) {
                return node.performAction(AccessibilityNodeInfo.ACTION_CLICK)
            }
            // Try parent if child is not clickable
            var parent = node.parent
            while (parent != null) {
                if (parent.isClickable) {
                    return parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)
                }
                parent = parent.parent
            }
        }
        return false
    }

    /**
     * Type text into currently focused editable field or node with matching text.
     */
    fun typeText(targetText: String?, inputText: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val targetNode: AccessibilityNodeInfo? = if (targetText != null) {
            root.findAccessibilityNodeInfosByText(targetText).firstOrNull { it.isEditable || it.isFocusable }
        } else {
            root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT)
        }

        if (targetNode != null) {
            val args = Bundle().apply {
                putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, inputText)
            }
            return targetNode.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
        }
        return false
    }

    /**
     * Perform global system navigation gestures.
     */
    fun performGlobal(actionType: String): Boolean {
        return when (actionType.lowercase()) {
            "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "recents" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "notifications" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            "quick_settings" -> performGlobalAction(GLOBAL_ACTION_QUICK_SETTINGS)
            else -> false
        }
    }

    /**
     * Perform touch scroll gesture across screen.
     */
    fun scrollDirection(direction: String): Boolean {
        val displayMetrics = resources.displayMetrics
        val width = displayMetrics.widthPixels.toFloat()
        val height = displayMetrics.heightPixels.toFloat()

        val path = Path()
        val startX = width / 2
        var startY = height * 0.7f
        var endY = height * 0.3f

        if (direction.lowercase() in listOf("up", "top")) {
            startY = height * 0.3f
            endY = height * 0.7f
        }

        path.moveTo(startX, startY)
        path.lineTo(startX, endY)

        val gesture = GestureDescription.Builder()
            .addStroke(GestureDescription.StrokeDescription(path, 0, 300))
            .build()

        return dispatchGesture(gesture, null, null)
    }
}
