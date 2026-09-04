/*
 * Northeast India referral facilities, keyed by risk band.
 * Phone numbers are intentionally left as "verify locally" — exact CHC/district
 * hospital switchboard numbers change and were not independently verified.
 * Names, cities, states and categories are real, well-known public institutions.
 */

export const NER_FACILITIES = [
  { name: 'AIIMS Guwahati', city: 'Guwahati', state: 'Assam', category: 'Tertiary / Orthopedics', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Gauhati Medical College & Hospital', city: 'Guwahati', state: 'Assam', category: 'District / Tertiary', phone: 'Verify locally', tier: 'elevated' },
  { name: 'RIMS Imphal (Regional Institute of Medical Sciences)', city: 'Imphal', state: 'Manipur', category: 'Tertiary / Orthopedics', phone: 'Verify locally', tier: 'elevated' },
  { name: 'NEIGRIHMS Shillong', city: 'Shillong', state: 'Meghalaya', category: 'Tertiary / Orthopedics', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Agartala Government Medical College (GBP Hospital)', city: 'Agartala', state: 'Tripura', category: 'District / Tertiary', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Naga Hospital Authority Kohima', city: 'Kohima', state: 'Nagaland', category: 'District Hospital', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Zoram Medical College Hospital', city: 'Falkawn / Aizawl', state: 'Mizoram', category: 'District / Tertiary', phone: 'Verify locally', tier: 'elevated' },
  { name: 'TRIHMS (Tomo Riba Institute of Health & Medical Sciences)', city: 'Naharlagun', state: 'Arunachal Pradesh', category: 'District / Tertiary', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Central Referral Hospital, SMIMS', city: 'Gangtok', state: 'Sikkim', category: 'District / Tertiary', phone: 'Verify locally', tier: 'elevated' },
  { name: 'Nearest Community Health Centre (CHC)', city: 'Your block / tehsil', state: '—', category: 'Primary orthopedic screening', phone: 'Ask at local PHC', tier: 'borderline' },
  { name: 'Nearest AYUSH Wellness Centre', city: 'Your block / tehsil', state: '—', category: 'Conservative / lifestyle management', phone: 'Ask at local PHC', tier: 'borderline' },
]

/* messageKey looks up the translated template in i18n/translations.js —
   referralMessageElevated / referralMessageBorderline / referralMessageLow. */
export function getReferral(band) {
  if (band === 'low') {
    return { band, messageKey: 'referralMessageLow', facilities: [] }
  }
  const tier = band === 'elevated' ? 'elevated' : 'borderline'
  return {
    band,
    messageKey: band === 'elevated' ? 'referralMessageElevated' : 'referralMessageBorderline',
    facilities: NER_FACILITIES.filter(f => f.tier === tier),
  }
}
