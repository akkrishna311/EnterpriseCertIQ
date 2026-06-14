import { useEffect, useState } from 'react'
import { Headphones, Loader2, Quote, Sparkles } from 'lucide-react'
import { api, type AudioTranscript, type AudioConcepts } from '../api/client'

/**
 * Grounded two-host learning podcast.
 * Teaches the learner's WEAKEST concept by default, or any concept they pick.
 * Transcript always works; the MP3 plays when Azure Speech is configured.
 */
export default function AudioBriefing({ learnerId, certId }: { learnerId: string; certId: string }) {
  const [concepts, setConcepts] = useState<AudioConcepts | null>(null)
  const [focus, setFocus] = useState<string>('weakest') // 'weakest' | 'overview' | domain_id
  const [loading, setLoading] = useState(false)
  const [data, setData] = useState<AudioTranscript | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Load the concept menu (with the weakest one flagged) once on mount. The parent
  // remounts this component via `key` when the learner/cert changes, so state resets
  // cleanly here — no setState churn that could loop.
  useEffect(() => {
    let alive = true
    api.audioConcepts(learnerId, certId)
      .then((c) => { if (alive) setConcepts(c) })
      .catch(() => { /* concepts are optional; generate still works */ })
    return () => { alive = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function generate() {
    setLoading(true); setError(null)
    try {
      setData(await api.audioTranscript(learnerId, certId, focus))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to generate podcast')
    } finally {
      setLoading(false)
    }
  }

  // The focus string sent to the API: domain name for a picked concept, else the keyword.
  const focusParam =
    focus === 'weakest' || focus === 'overview'
      ? focus
      : concepts?.concepts.find((c) => c.domain_id === focus)?.name ?? focus

  return (
    <div style={{ border: '1px solid #2a3a52', borderRadius: 10, padding: 16, background: '#0f1830' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <Headphones size={16} color="#0f9bd7" />
        <strong>Learning Podcast</strong>
        <span style={{ fontSize: 11, color: '#8aa0c0' }}>grounded · cited · two-host</span>
      </div>

      {/* Concept picker */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap', marginBottom: 10 }}>
        <label style={{ fontSize: 12, color: '#8aa0c0' }}>Teach me:</label>
        <select value={focus} onChange={(e) => { setFocus(e.target.value); setData(null) }}
          style={{ background: '#0b1426', color: '#d6e2f5', border: '1px solid #2a3a52',
            borderRadius: 6, padding: '6px 8px', fontSize: 13, minWidth: 260 }}>
          <option value="weakest">🎯 My weakest area (recommended)</option>
          <option value="overview">📋 Full exam overview</option>
          {concepts?.concepts.map((c) => (
            <option key={c.domain_id} value={c.domain_id}>
              {c.name} · {c.weight_pct}%{c.is_weakest ? ' · weakest' : ''}
              {c.mastery_pct != null ? ` · mastery ${Math.round(c.mastery_pct)}%` : ''}
            </option>
          ))}
        </select>
        <button onClick={generate} disabled={loading}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '7px 13px',
            borderRadius: 8, border: 'none', background: '#0f6cbd', color: 'white', cursor: 'pointer' }}>
          {loading ? <Loader2 size={14} className="spin" /> : <Sparkles size={14} />}
          {loading ? 'Generating…' : 'Generate podcast'}
        </button>
      </div>

      {error && <p style={{ color: '#ff8a8a', fontSize: 13 }}>{error}</p>}

      {data && (
        <div>
          <h4 style={{ margin: '4px 0 6px' }}>{data.script.title}</h4>
          {data.script.is_weakest && (
            <p style={{ fontSize: 11, color: '#ffcf6b', margin: '0 0 8px' }}>
              ⭐ Targeting your weakest, highest-leverage area.
            </p>
          )}

          {data.audio_available ? (
            <audio controls preload="none" style={{ width: '100%', marginBottom: 10 }}
              src={api.audioUrl(learnerId, certId, focusParam)} />
          ) : (
            <p style={{ fontSize: 12, color: '#8aa0c0', marginBottom: 10 }}>
              🔇 Audio synthesis is off (set <code>SPEECH_KEY</code> / <code>SPEECH_REGION</code>).
              Transcript below is fully grounded and ready.
            </p>
          )}

          <div style={{ maxHeight: 300, overflowY: 'auto', display: 'grid', gap: 8 }}>
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
