package pl.czarnewilkiprawdy.app

import android.app.Service
import android.content.Intent
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.os.IBinder
import kotlin.concurrent.thread

/**
 * Continuous microphone listen. Auto-stop is forbidden — only an explicit Stop intent.
 */
class MicService : Service() {
    @Volatile private var listening = false
    private var rec: AudioRecord? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> stopMic()
            else -> startMic()
        }
        return START_STICKY
    }

    private fun startMic() {
        if (listening) return
        listening = true
        val sr = 16000
        val min = AudioRecord.getMinBufferSize(sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        rec = AudioRecord(MediaRecorder.AudioSource.MIC, sr, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, min)
        rec?.startRecording()
        thread(name = "wolf-mic") {
            val buf = ShortArray(min)
            while (listening) {
                rec?.read(buf, 0, buf.size)
            }
        }
    }

    private fun stopMic() {
        listening = false
        rec?.stop()
        rec?.release()
        rec = null
        stopSelf()
    }

    companion object {
        const val ACTION_STOP = "pl.czarnewilkiprawdy.app.STOP_MIC"
    }
}
