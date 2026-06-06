import { useState } from 'react'
import { Headphones, Loader2, Quote } from 'lucide-react'
import { api, type AudioTranscript } from '../api/client'

/**
 * Grounded two-host "audio study briefing" (NotebookLM-style, but cited).
 * Fetches the transcript (always available) and, when Azure Speech is configured,
 * plays the synthesized MP3. The transcript + citations prove it's grounded.
 */
export default function AudioBriefing({ learnerId, certId }: { learnerId: string; certId: string }) {
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<AudioTranscript | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function generate() {
    setLoading(true)
    setError(null)
    try {
      setData(await api.audioTranscript(learnerId, certId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate briefing')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ border: '1px solid #2a3a52', borderRadius: 10, padding: 16, background: '#0f1830' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <Headphones size={16} color="#0f9bd7" />
        <strong>Audio Study Briefing</strong>
        <span style={{ fontSize: 11, color: '#8aa0c0' }}>grounded · cited · two-host</span>
      </div>

      {!data && (
        <button onClick={generate} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '8px 14px',
            borderRadius: 8, border: 'none', background: '#0f6cbd', color: 'white', cursor: 'pointer' }}>
          {loading ? <Loader2 size={14} className="spin" /> : <Headphones size={14} />}
          {loading ? 'Generating…' : 'Generate audio briefing'}
        </button>
      )}

      {error && <p style={{ color: '#ff8a8a', fontSize: 13 }}>{error}</p>}

      {data && (
        <div>
          <h4 style={{ margin: '4px 0 8px' }}>{data.script.title}</h4>

          {data.audio_available ? (
            <audio controls preload="none" style={{ width: '100%', marginBottom: 10 }}
              src={api.audioUrl(learnerId, certId)} />
          ) : (
            <p style={{ fontSize: 12, color: '#8aa0c0', marginBottom: 10 }}>
              🔇 Audio synthesis is off (set <code>SPEECH_KEY</code> / <code>SPEECH_REGION</code>).
              Transcript below is fully grounded and ready.
            </p>
          )}

          <div style={{ maxHeight: 260, overflowY: 'auto', display: 'grid', gap: 8 }}>
            {data.script.turns.map((t, i) => (
              <div key={i} style={{ display: 'flex', gap: 8 }}>
                <span style={{ flexShrink: 0, fontSize: 11, fontWeight: 600,
                  color: t.speaker === 'host_a' ? '#0f9bd7' : '#7bd88f' }}>
                  {t.speaker === 'host_a' ? 'Coach' : 'Learner'}
                </span>
                <span style={{ fontSize: 13, color: '#d6e2f5' }}>{t.text}</span>
              </div>
            ))}
          </div>

          {data.script.citations?.length > 0 && (
            <div style={{ marginTop: 10, fontSize: 11, color: '#8aa0c0' }}>
              <Quote size={11} style={{ verticalAlign: 'middle' }} /> Sources:{' '}
              {data.script.citations.join(' · ')}
            </div>
          )}
          <p style={{ marginTop: 8, fontSize: 11, color: '#6b7f9e' }}>{data.script.ai_disclosure}</p>
        </div>
      )}
    </div>
  )
}
