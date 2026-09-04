/*
 * Preventive guidance — SIH26004 (h): "awareness and preventive guidance
 * related to joint care, physical activity, nutrition, and lifestyle
 * management".
 *
 * General public-health advice consistent with standard OA self-management
 * (weight management, low-impact activity, quadriceps strengthening, joint
 * protection). It is education, not a prescription — the referral card and
 * the disclaimer carry the clinical hand-off.
 */

export const GUIDANCE = [
  {
    id: 'joint',
    icon: 'Bone',
    items: ['guideJoint1', 'guideJoint2', 'guideJoint3'],
  },
  {
    id: 'activity',
    icon: 'Activity',
    items: ['guideActivity1', 'guideActivity2', 'guideActivity3'],
  },
  {
    id: 'nutrition',
    icon: 'Apple',
    items: ['guideNutrition1', 'guideNutrition2', 'guideNutrition3'],
  },
  {
    id: 'lifestyle',
    icon: 'HeartPulse',
    items: ['guideLifestyle1', 'guideLifestyle2', 'guideLifestyle3'],
  },
]

/* Which note leads, given the screening band. */
export function guidanceLead(band) {
  if (band === 'elevated') return 'guideLeadElevated'
  if (band === 'borderline') return 'guideLeadBorderline'
  return 'guideLeadLow'
}
