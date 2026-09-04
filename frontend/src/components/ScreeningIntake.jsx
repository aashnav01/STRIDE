import { useState } from 'react'
import { User, ClipboardList, Check, ChevronRight } from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import {
  SYMPTOM_QUESTIONS, SYMPTOM_OPTIONS, SYMPTOM_MAX, symptomBand,
} from '../constants/symptomQuestions'

/*
 * Two-step field intake for the health worker: who is being screened, then
 * how their knees feel. Runs before the walking video so the gait score
 * lands next to a symptom picture rather than on its own.
 */
const ScreeningIntake = ({ value, onChange }) => {
  const { t } = useLanguage()
  const [step, setStep] = useState(0)

  const patient = value.patient
  const answers = value.symptoms

  const setPatient = (k, v) => onChange({ ...value, patient: { ...patient, [k]: v } })
  const setAnswer = (id, v) => onChange({ ...value, symptoms: { ...answers, [id]: v } })

  const answered = SYMPTOM_QUESTIONS.filter(q => answers[q.id] != null).length
  const total = SYMPTOM_QUESTIONS.reduce((s, q) => s + (answers[q.id] ?? 0), 0)
  const complete = answered === SYMPTOM_QUESTIONS.length
  const canProceed = patient.name?.trim() && patient.age

  return (
    <section className="intake">
      <ol className="intake-steps" aria-label={t('intakeTitle')}>
        {[t('intakeStepPatient'), t('intakeStepSymptoms')].map((label, i) => (
          <li key={label} className={i === step ? 'on' : i < step ? 'done' : ''}>
            <span className="intake-step-dot">
              {i < step ? <Check size={13} /> : i + 1}
            </span>
            {label}
          </li>
        ))}
      </ol>

      {step === 0 ? (
        <div className="intake-panel">
          <h3><User size={17} /> {t('intakeStepPatient')}</h3>
          <div className="intake-grid">
            <label className="field field-wide">
              <span>{t('fieldName')}</span>
              <input
                type="text" value={patient.name || ''}
                onChange={e => setPatient('name', e.target.value)}
                placeholder={t('fieldNamePlaceholder')}
              />
            </label>
            <label className="field">
              <span>{t('fieldAge')}</span>
              <input
                type="number" min="1" max="120" inputMode="numeric"
                value={patient.age || ''}
                onChange={e => setPatient('age', e.target.value)}
              />
            </label>
            <label className="field">
              <span>{t('fieldSex')}</span>
              <select value={patient.sex || ''} onChange={e => setPatient('sex', e.target.value)}>
                <option value="">—</option>
                <option value="female">{t('sexFemale')}</option>
                <option value="male">{t('sexMale')}</option>
                <option value="other">{t('sexOther')}</option>
              </select>
            </label>
            <label className="field field-wide">
              <span>{t('fieldVillage')}</span>
              <input
                type="text" value={patient.village || ''}
                onChange={e => setPatient('village', e.target.value)}
                placeholder={t('fieldVillagePlaceholder')}
              />
            </label>
            <label className="field field-wide">
              <span>{t('fieldOccupation')}</span>
              <input
                type="text" value={patient.occupation || ''}
                onChange={e => setPatient('occupation', e.target.value)}
                placeholder={t('fieldOccupationPlaceholder')}
              />
            </label>
          </div>
          <button
            className="intake-next" disabled={!canProceed}
            onClick={() => setStep(1)}
          >
            {t('intakeNext')} <ChevronRight size={16} />
          </button>
        </div>
      ) : (
        <div className="intake-panel">
          <h3><ClipboardList size={17} /> {t('intakeStepSymptoms')}</h3>
          <p className="intake-hint">{t('symptomHint')}</p>

          {SYMPTOM_QUESTIONS.map(q => (
            <div className="symptom" key={q.id}>
              <span className="symptom-q">{t(q.key)}</span>
              <div className="symptom-scale" role="group" aria-label={t(q.key)}>
                {SYMPTOM_OPTIONS.map(o => (
                  <button
                    key={o.value}
                    className={`symptom-opt s${o.value}${answers[q.id] === o.value ? ' on' : ''}`}
                    onClick={() => setAnswer(q.id, o.value)}
                    aria-pressed={answers[q.id] === o.value}
                  >
                    {t(o.key)}
                  </button>
                ))}
              </div>
            </div>
          ))}

          <div className="symptom-total">
            <div>
              <span className="symptom-total-label">{t('symptomScore')}</span>
              <strong className={`symptom-total-value band-${symptomBand(total)}`}>
                {total}<span> / {SYMPTOM_MAX}</span>
              </strong>
            </div>
            <span className="symptom-progress">
              {complete ? t('symptomComplete') : `${answered} / ${SYMPTOM_QUESTIONS.length}`}
            </span>
          </div>

          <button className="intake-back" onClick={() => setStep(0)}>{t('intakeBack')}</button>
        </div>
      )}
    </section>
  )
}

export default ScreeningIntake
