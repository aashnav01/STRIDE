import { GamosaDefs } from './Gamosa'

/*
 * Page background — a piece of gamosa cloth, in 3D space.
 *
 * Rather than a flat wallpaper, the whole thing is a plane set on a CSS
 * perspective and tilted a few degrees, with the woven borders running all
 * four edges the way they do on real cloth, a central medallion, and soft
 * fold shading across it. The medallion's rings sit at different translateZ
 * depths, so tilting the plane gives them genuine parallax against each
 * other — depth that is actually three-dimensional, not painted on.
 *
 * All CSS transforms: GPU-composited, no WebGL, and nothing here costs a
 * frame on the low-end Android this is built for.
 */
const AppBackground = () => (
  <div className="app-bg" aria-hidden="true">
    {/* soft light behind the cloth */}
    <div className="aurora">
      <span className="aurora-blob b1" />
      <span className="aurora-blob b2" />
      <span className="aurora-blob b3" />
    </div>

    <div className="cloth-scene">
      <div className="cloth-plane">
        {/* the weave itself */}
        <svg className="cloth-weave">
          <GamosaDefs />
          <rect width="100%" height="100%" fill="url(#gamosaWeave)" />
        </svg>

        {/* drape: light falling across the folds */}
        <div className="cloth-folds" />

        {/* woven borders at the two ends, as on the cloth */}
        <div className="cloth-edge edge-top">
          <svg width="100%" height="116"><rect width="100%" height="116" fill="url(#gamosaBorder)" /></svg>
        </div>
        <div className="cloth-edge edge-bottom">
          <svg width="100%" height="116"><rect width="100%" height="116" fill="url(#gamosaBorder)" /></svg>
        </div>

        {/* central medallion — each ring on its own Z plane */}
        <div className="medallion">
          <svg className="med-ring med-1" viewBox="0 0 200 200">
            <path d="M100,4 L196,100 L100,196 L4,100 Z" fill="none" stroke="#4F46E5" strokeWidth="1.1" />
            <path d="M100,4 L106,10 M100,4 L94,10 M196,100 L190,94 M196,100 L190,106
                     M100,196 L106,190 M100,196 L94,190 M4,100 L10,94 M4,100 L10,106"
                  stroke="#4F46E5" strokeWidth="1.1" strokeLinecap="round" />
          </svg>
          <svg className="med-ring med-2" viewBox="0 0 200 200">
            <path d="M100,30 L170,100 L100,170 L30,100 Z" fill="none" stroke="#7C3AED" strokeWidth="1" />
            <circle cx="100" cy="100" r="52" fill="none" stroke="#7C3AED" strokeWidth="0.7" strokeDasharray="3 6" />
          </svg>
          <svg className="med-ring med-3" viewBox="0 0 200 200">
            <path d="M100,60 L140,100 L100,140 L60,100 Z" fill="none" stroke="#2563EB" strokeWidth="0.9" />
            <circle cx="100" cy="100" r="7" fill="none" stroke="#2563EB" strokeWidth="0.9" />
          </svg>
        </div>
      </div>
    </div>
  </div>
)

export default AppBackground
