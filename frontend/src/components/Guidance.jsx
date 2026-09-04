import { Bone, Activity, Apple, HeartPulse, Info } from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'
import { GUIDANCE, guidanceLead } from '../constants/guidance'

const ICONS = { Bone, Activity, Apple, HeartPulse }

const Guidance = ({ band = 'low' }) => {
  const { t } = useLanguage()

  return (
    <div className="measurements guidance">
      <h3>{t('guideTitle')}</h3>
      <p className="guidance-lead">
        <Info size={15} /> {t(guidanceLead(band))}
      </p>
      <div className="guidance-grid">
        {GUIDANCE.map(g => {
          const Icon = ICONS[g.icon]
          return (
            <div className="guidance-card" key={g.id}>
              <h4><Icon size={16} /> {t(`guide_${g.id}`)}</h4>
              <ul>
                {g.items.map(k => <li key={k}>{t(k)}</li>)}
              </ul>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default Guidance
