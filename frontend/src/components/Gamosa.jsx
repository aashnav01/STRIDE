/*
 * Gamosa motifs — the app's decorative vocabulary.
 *
 * The gamosa is Assam's cultural cloth: white ground, woven borders, given
 * as a mark of respect. Its motifs are woven by rural Assamese women — the
 * community ASHA workers come from — so this is her visual language rather
 * than a tech-conference gradient.
 *
 * Motifs drawn from the common border repeats:
 *   pari      the plain stripes that edge every gamosa
 *   kumbha    the temple-triangle row found across Indian handloom borders
 *   kingkhap  the hooked, nested diamond
 *   phul      the four- and eight-petal flowers
 *   miri      the zigzag/chevron rows
 *
 * Rendered in indigo/violet rather than gamosa red, so decoration never
 * competes with the red that means "elevated risk".
 */

const INDIGO = '#4F46E5'
const VIOLET = '#7C3AED'
const BLUE = '#2563EB'
/* One green thread. Assam's ASHA uniform is a white drape with a green
   border — so the border of this cloth carries her colour too. */
const ASHA_GREEN = '#15803D'

/* --- the mark: a hooked kingkhap ---
   The same nested diamond woven into the border below, so the mark and
   the cloth speak one language. Built as three layers on separate
   translateZ planes inside a shared preserve-3d context, giving it real
   depth rather than a drawn bevel. --- */
export const Kingkhap = ({ size = 26 }) => (
  <span className="kingkhap" style={{ width: size, height: size }} aria-hidden="true">
    <svg className="kk-layer kk-1" viewBox="0 0 32 32" fill="none">
      <path
        d="M16 1 L18.6 3.6 M16 1 L13.4 3.6 M31 16 L28.4 13.4 M31 16 L28.4 18.6
           M16 31 L18.6 28.4 M16 31 L13.4 28.4 M1 16 L3.6 13.4 M1 16 L3.6 18.6"
        stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" opacity="0.85"
      />
      <path d="M16 2 L30 16 L16 30 L2 16 Z" stroke="currentColor" strokeWidth="1.7" />
    </svg>
    <svg className="kk-layer kk-2" viewBox="0 0 32 32" fill="none">
      <path d="M16 7 L25 16 L16 25 L7 16 Z" stroke="currentColor" strokeWidth="1.35" />
      <g fill="currentColor" opacity="0.8">
        <circle cx="16" cy="5.6" r="0.95" /><circle cx="26.4" cy="16" r="0.95" />
        <circle cx="16" cy="26.4" r="0.95" /><circle cx="5.6" cy="16" r="0.95" />
      </g>
    </svg>
    <svg className="kk-layer kk-3" viewBox="0 0 32 32" fill="none">
      <path d="M16 11.5 L20.5 16 L16 20.5 L11.5 16 Z" stroke="currentColor" strokeWidth="1.15" />
      <circle cx="16" cy="16" r="1.9" fill="currentColor" />
    </svg>
  </span>
)

/* one repeat of a full gamosa border, 220 wide */
const TILE_W = 220
const TILE_H = 116

export const GamosaDefs = () => (
  <defs>
    {/* the cloth: warp and weft */}
    <pattern id="gamosaWeave" width="7" height="7" patternUnits="userSpaceOnUse">
      <path d="M0,0 H7 M0,3.5 H7" stroke="#1E3A8A" strokeWidth="0.55" opacity="0.5" />
      <path d="M0,0 V7 M3.5,0 V7" stroke={INDIGO} strokeWidth="0.4" opacity="0.34" />
    </pattern>

    <pattern id="gamosaBorder" width={TILE_W} height={TILE_H} patternUnits="userSpaceOnUse">
      {/* --- pari: graded stripes --- */}
      <path d={`M0,3 H${TILE_W}`} stroke={INDIGO} strokeWidth="1.2" opacity="0.75" />
      <path d={`M0,8.5 H${TILE_W}`} stroke={INDIGO} strokeWidth="3" />
      <path d={`M0,13.5 H${TILE_W}`} stroke={VIOLET} strokeWidth="1" opacity="0.6" />

      {/* --- dotted row --- */}
      <g fill={VIOLET} opacity="0.7">
        {Array.from({ length: 22 }, (_, i) => (
          <circle key={i} cx={5 + i * 10} cy="19.5" r="1.3" />
        ))}
      </g>

      {/* --- kumbha: temple triangles --- */}
      <path
        d={Array.from({ length: 11 }, (_, i) => {
          const x = i * 20
          return `M${x},34 L${x + 10},24 L${x + 20},34`
        }).join(' ')}
        fill="none" stroke={BLUE} strokeWidth="1.5" opacity="0.8"
      />

      {/* --- main motif row --- */}
      {/* hooked kingkhap, centred */}
      <g stroke={INDIGO} fill="none">
        <path d="M110,44 L136,70 L110,96 L84,70 Z" strokeWidth="2.4" />
        <path d="M110,52 L128,70 L110,88 L92,70 Z" strokeWidth="1.8" stroke={VIOLET} />
        <path d="M110,60 L120,70 L110,80 L100,70 Z" strokeWidth="1.4" stroke={VIOLET} opacity="0.8" />
        <path
          d="M110,44 L113,47 M110,44 L107,47 M136,70 L133,67 M136,70 L133,73
             M110,96 L113,93 M110,96 L107,93 M84,70 L87,67 M84,70 L87,73"
          strokeWidth="1.5" strokeLinecap="round"
        />
      </g>
      <circle cx="110" cy="70" r="2.6" fill={VIOLET} />

      {/* eight-petal phul at the tile edges, so they tile into whole flowers */}
      {[0, TILE_W].map(cx => (
        <g key={cx} stroke={VIOLET} strokeWidth="1.7" fill="none" opacity="0.9">
          <path d={`M${cx},56 L${cx},84 M${cx - 14},70 L${cx + 14},70`} />
          <path d={`M${cx - 10},60 L${cx + 10},80 M${cx + 10},60 L${cx - 10},80`} opacity="0.65" />
          <circle cx={cx} cy="70" r="3.4" />
        </g>
      ))}

      {/* two leaves and a bud — the Assam tea motif, for the tea-garden
          workers this screening exists for */}
      {[55, 165].map(cx => (
        <g key={cx} fill="none" strokeLinecap="round">
          <path d={`M${cx},82 V64`} stroke={ASHA_GREEN} strokeWidth="1.5" opacity="0.85" />
          <path
            d={`M${cx},66 C${cx - 9},64 ${cx - 12},72 ${cx - 4},76 C${cx - 1},73 ${cx - 1},69 ${cx},66 Z`}
            stroke={ASHA_GREEN} strokeWidth="1.4" opacity="0.8"
          />
          <path
            d={`M${cx},66 C${cx + 9},64 ${cx + 12},72 ${cx + 4},76 C${cx + 1},73 ${cx + 1},69 ${cx},66 Z`}
            stroke={ASHA_GREEN} strokeWidth="1.4" opacity="0.8"
          />
          {/* the bud */}
          <path
            d={`M${cx},63.5 C${cx - 3},60 ${cx - 2},55 ${cx},53 C${cx + 2},55 ${cx + 3},60 ${cx},63.5 Z`}
            stroke={ASHA_GREEN} strokeWidth="1.4" fill={ASHA_GREEN} fillOpacity="0.18"
          />
        </g>
      ))}

      {/* --- miri zigzag --- */}
      <path
        d={Array.from({ length: 15 }, (_, i) => {
          const x = i * 15
          return `M${x},106 L${x + 7.5},99 L${x + 15},106`
        }).join(' ')}
        fill="none" stroke={BLUE} strokeWidth="1.5" opacity="0.75"
      />

      {/* --- closing stripes --- */}
      <path d={`M0,111 H${TILE_W}`} stroke={INDIGO} strokeWidth="2.4" />
      <path d={`M0,114 H${TILE_W}`} stroke={ASHA_GREEN} strokeWidth="1.1" opacity="0.7" />
      <path d={`M0,116 H${TILE_W}`} stroke={INDIGO} strokeWidth="0.9" opacity="0.6" />
    </pattern>

  </defs>
)
