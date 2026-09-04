/*
 * Pain & mobility screening — SIH26004 requires "pain and mobility screening
 * inputs" alongside gait analysis.
 *
 * Items are derived from the WOMAC osteoarthritis index (pain, stiffness and
 * physical-function subscales), shortened to five for field use. Each scores
 * 0-4, so the instrument runs 0-20. WOMAC is a validated, freely used
 * self-report measure for knee OA — this is a shortened screening adaptation,
 * not the scored WOMAC instrument, and must not be reported as one.
 */

export const SYMPTOM_QUESTIONS = [
  { id: 'painWalking', key: 'symPainWalking' },
  { id: 'painStairs', key: 'symPainStairs' },
  { id: 'stiffness', key: 'symStiffness' },
  { id: 'rising', key: 'symRising' },
  { id: 'painNight', key: 'symPainNight' },
]

/* 0-4 per item, ascending severity */
export const SYMPTOM_OPTIONS = [
  { value: 0, key: 'symNone' },
  { value: 1, key: 'symMild' },
  { value: 2, key: 'symModerate' },
  { value: 3, key: 'symSevere' },
  { value: 4, key: 'symExtreme' },
]

export const SYMPTOM_MAX = SYMPTOM_QUESTIONS.length * 4

export function symptomBand(total) {
  const pct = total / SYMPTOM_MAX
  if (pct < 0.25) return 'low'
  if (pct < 0.5) return 'borderline'
  return 'elevated'
}
