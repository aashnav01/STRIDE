import { useLanguage } from '../i18n/useLanguage'

const WhyNER = () => {
  const { t } = useLanguage()

  return (
    <section className="why-ner" id="why-ner">
      <h2>{t('whyNERTitle')}</h2>
      <p>{t('whyNERIntro')}</p>
      <div className="why-ner-stats">
        <div className="why-ner-stat">
          <strong>29.4%</strong>
          <span>knee OA prevalence found in a tea-garden community study, Jorhat, Assam</span>
        </div>
        <div className="why-ner-stat">
          <strong>28.7%</strong>
          <span>overall knee OA prevalence estimated across India (population meta-analysis)</span>
        </div>
        <div className="why-ner-stat">
          <strong>Few</strong>
          <span>community-based OA studies exist for the North-Eastern states — access to imaging and specialist care lags rural areas most</span>
        </div>
      </div>
      <p className="why-ner-sources">
        Sources:{' '}
        <a href="https://ijor.org/archive/volume/9/issue/1/article/7334" target="_blank" rel="noopener noreferrer">
          Jorhat tea-garden OA study
        </a>{', '}
        <a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC11633723/" target="_blank" rel="noopener noreferrer">
          rural India OA burden review
        </a>
      </p>
    </section>
  )
}

export default WhyNER
