/*
 * App-shell service worker. The screening flow must keep working in a village
 * with no signal, so the shell is cached on install and served cache-first.
 * API calls are never cached — stale clinical data is worse than none.
 */
const CACHE = 'asha-sathi-v1'
const SHELL = ['/', '/index.html', '/manifest.webmanifest']

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())
  )
})

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  )
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  // model/API traffic: network only, never served stale
  if (/\/(extract-pose|generate-report|screenings|health)$/.test(url.pathname)) return
  if (url.origin !== self.location.origin) return

  e.respondWith(
    caches.match(req).then(hit => {
      if (hit) {
        // refresh in the background so the next load is current
        fetch(req).then(res => {
          if (res && res.ok) caches.open(CACHE).then(c => c.put(req, res.clone()))
        }).catch(() => {})
        return hit
      }
      return fetch(req)
        .then(res => {
          if (res && res.ok && res.type === 'basic') {
            const copy = res.clone()
            caches.open(CACHE).then(c => c.put(req, copy))
          }
          return res
        })
        .catch(() => caches.match('/index.html'))
    })
  )
})
