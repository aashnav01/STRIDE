import { Phone } from 'lucide-react'
import { getReferral } from '../constants/nerFacilities'
import { useLanguage } from '../i18n/useLanguage'

const ReferralCard = ({ band }) => {
  const { t } = useLanguage()
  const referral = getReferral(band)

  return (
    <div className="measurements referral-card">
      <h3>{t('referralTitle')}</h3>
      <p className="referral-message">{t(referral.messageKey)}</p>
      {referral.facilities.length > 0 && (
        <div className="measurement-grid">
          {referral.facilities.map((f, i) => (
            <div className="measurement referral-facility" key={i}>
              <div className="measurement-header">
                <span className="measurement-label">{f.name}</span>
                <span className="measurement-value">{f.category}</span>
              </div>
              <div className="measurement-reading">
                {f.city}{f.state !== '—' ? `, ${f.state}` : ''}
                <br />
                <Phone size={12} style={{ verticalAlign: '-1px', marginRight: 4 }} />
                {f.phone}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default ReferralCard
