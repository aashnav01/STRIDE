import { Check } from 'lucide-react'
import { useLanguage } from '../i18n/useLanguage'

const RecordingChecklist = () => {
  const { t } = useLanguage()
  const items = [t('checklistSideOn'), t('checklistWholeBody'), t('checklistDuration')]

  return (
    <div className="recording-checklist">
      <span className="recording-checklist-title">{t('checklistTitle')}</span>
      <ul>
        {items.map(item => (
          <li key={item}><Check size={14} />{item}</li>
        ))}
      </ul>
    </div>
  )
}

export default RecordingChecklist
