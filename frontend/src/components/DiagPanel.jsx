import { useState } from 'react'
import { Terminal, Copy, Check } from 'lucide-react'

/*
 * On-screen diagnostics.
 *
 * Console logging is useless when the person debugging is not looking at
 * devtools, and it says nothing at all while a request is still pending.
 * This shows what is happening as it happens — the URL actually being
 * called, the file being sent, a live elapsed counter, and the verbatim
 * error if one arrives — and offers one button to copy the lot.
 */
const DiagPanel = ({ lines, open, onToggle }) => {
  const [copied, setCopied] = useState(false)
  if (!lines.length) return null

  const text = lines.map(l => `${l.t.padStart(7)}  ${l.msg}`).join('\n')

  const copy = () => {
    navigator.clipboard?.writeText(text).then(
      () => { setCopied(true); setTimeout(() => setCopied(false), 1800) },
      () => {}
    )
  }

  return (
    <div className={`diag${open ? ' open' : ''}`}>
      <div className="diag-head">
        <button className="diag-toggle" onClick={onToggle}>
          <Terminal size={13} />
          Diagnostics ({lines.length})
        </button>
        {open && (
          <button className="diag-copy" onClick={copy}>
            {copied ? <Check size={12} /> : <Copy size={12} />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        )}
      </div>
      {open && (
        <pre className="diag-body">
          {lines.map((l, i) => (
            <div key={i} className={l.level ? `diag-${l.level}` : undefined}>
              <span className="diag-t">{l.t}</span>{l.msg}
            </div>
          ))}
        </pre>
      )}
    </div>
  )
}

export default DiagPanel
