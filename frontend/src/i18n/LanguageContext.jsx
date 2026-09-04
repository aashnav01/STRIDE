import { useState, useCallback, useEffect } from 'react'
import { LanguageContext } from './context'
import { translations } from './translations'

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState('en')

  // CSS keys the Indic typeface off this attribute
  useEffect(() => {
    document.documentElement.setAttribute('data-lang', lang)
    document.documentElement.setAttribute(
      'lang', lang === 'as' ? 'as' : lang === 'mni' ? 'mni' : 'en'
    )
  }, [lang])

  const t = useCallback((key) => {
    return translations[lang]?.[key] ?? translations.en[key] ?? key
  }, [lang])

  return (
    <LanguageContext.Provider value={{ lang, setLang, t }}>
      {children}
    </LanguageContext.Provider>
  )
}
