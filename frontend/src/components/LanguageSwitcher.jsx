import { Languages } from 'lucide-react'
import { LANGUAGES } from '../i18n/translations'
import { useLanguage } from '../i18n/useLanguage'

const LanguageSwitcher = () => {
  const { lang, setLang } = useLanguage()

  return (
    <div className="language-switcher">
      <Languages size={16} />
      <select value={lang} onChange={e => setLang(e.target.value)} aria-label="Select language">
        {LANGUAGES.map(l => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>
    </div>
  )
}

export default LanguageSwitcher
