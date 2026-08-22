package pl.czarnewilkiprawdy.app

import android.accessibilityservice.AccessibilityService
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

/**
 * Native Android Accessibility Service — requirement 8.
 * Walks the view tree and performs user-initiated clicks. No vendor API.
 */
class WolfAccessibilityService : AccessibilityService() {
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        val root = rootInActiveWindow ?: return
        // Example traversal used by the publication planner when the operator confirms send.
        collect(root)
        root.recycle()
    }

    override fun onInterrupt() {}

    private fun collect(node: AccessibilityNodeInfo) {
        for (i in 0 until node.childCount) {
            val c = node.getChild(i) ?: continue
            collect(c)
            c.recycle()
        }
    }

    fun clickByText(label: String): Boolean {
        val root = rootInActiveWindow ?: return false
        val hits = root.findAccessibilityNodeInfosByText(label)
        val ok = hits.firstOrNull()?.performAction(AccessibilityNodeInfo.ACTION_CLICK) ?: false
        hits.forEach { it.recycle() }
        root.recycle()
        return ok
    }
}
