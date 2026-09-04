/*
 * App-shell service worker.
 *
 * The screening flow must keep working in a village with no signal, so the
 * shell is cached. But the caching STRATEGY matters:
 *
 *   navigations / HTML  -> network-first, cache as fallback
 *   hashed build assets -> cache-first (the filename contains a content
 *                          hash, so a changed file is a different URL and
 *                          can never be served stale)
 *   API traffic         -> never touched; stale clinical data is worse
 *                          than none
 *
 * A previous version was cache-first for everything including index.html.
 * That pins a returning device to whichever build it saw first — a redeploy
 * would never reach it. For an app that must be correctable in the field,
 * that is a serious bug, not a performance tweak.
 */
const CACHE = 'stride-v2'
const SHELL = ['/', '/index.html', '/manifest.webmanifest']

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then(c => c.addAll(SHELL))
      .then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

/* let the page force an update without the user clearing site data */
self.addEventListener('message', (e) => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting()
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return
  // API traffic is never cached
  if (/\/(extract-pose|generate-report|screenings|health)/.test(url.pathname)) return

  const isDocument =
    req.mode === 'navigate' ||
    req.destination === 'document' ||
    url.pathname === '/' ||
    url.pathname.endsWith('.html')

  if (isDocument) {
    // network-first: a redeploy is picked up on the next load, and the
    // cached shell only appears when the network genuinely is not there
    e.respondWith(
      fetch(req)
        .then(res => {
          if (res && res.ok) {
            const copy = res.clone()
            caches.open(CACHE).then(c => c.put('/index.html', copy))
          }
          return res
        })
        .catch(() => caches.match('/index.html').then(r => r || caches.match('/')))
    )
    return
  }

  // static assets: filenames are content-hashed, so cache-first is safe
  e.respondWith(
    caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res && res.ok && res.type === 'basic') {
        const copy = res.clone()
        caches.open(CACHE).then(c => c.put(req, copy))
      }
      return res
    }))
  )
})
