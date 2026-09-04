/*
 * Offline screening store (SIH26004: "offline data collection capability" and
 * "offline synchronization capability for remote areas").
 *
 * Raw IndexedDB — no dependency. Every screening is written locally first and
 * flagged `synced: 0`; the sync pass promotes them when a network appears. The
 * field worker never waits on connectivity to finish a screening.
 */

const DB_NAME = 'asha-sathi'
const DB_VERSION = 1
const STORE = 'screenings'

function open() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        const os = db.createObjectStore(STORE, { keyPath: 'id' })
        os.createIndex('synced', 'synced')
        os.createIndex('createdAt', 'createdAt')
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

function tx(store, mode, fn) {
  return open().then(db => new Promise((resolve, reject) => {
    const t = db.transaction(store, mode)
    const req = fn(t.objectStore(store))
    t.oncomplete = () => resolve(req && req.result)
    t.onerror = () => reject(t.error)
    t.onabort = () => reject(t.error)
  }))
}

export function newId() {
  return `scr_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}

export async function saveScreening(record) {
  const row = {
    id: record.id || newId(),
    createdAt: record.createdAt || new Date().toISOString(),
    synced: 0,
    ...record,
  }
  // never let a storage failure lose the screening in progress
  try {
    await tx(STORE, 'readwrite', os => os.put(row))
  } catch (e) {
    console.warn('local save failed', e)
  }
  return row
}

export async function listScreenings() {
  try {
    const rows = await tx(STORE, 'readonly', os => os.getAll())
    return (rows || []).sort((a, b) => (a.createdAt < b.createdAt ? 1 : -1))
  } catch {
    return []
  }
}

export async function pendingScreenings() {
  const all = await listScreenings()
  return all.filter(r => !r.synced)
}

export async function markSynced(id) {
  try {
    const all = await listScreenings()
    const row = all.find(r => r.id === id)
    if (row) await tx(STORE, 'readwrite', os => os.put({ ...row, synced: 1 }))
  } catch (e) {
    console.warn('markSynced failed', e)
  }
}

/* Push everything still pending. Silent no-op when the network is absent. */
export async function syncPending(apiUrl) {
  if (!navigator.onLine) return { sent: 0, pending: (await pendingScreenings()).length }
  const pending = await pendingScreenings()
  let sent = 0
  for (const row of pending) {
    try {
      const res = await fetch(`${apiUrl}/screenings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(row),
      })
      if (!res.ok) break
      await markSynced(row.id)
      sent++
    } catch {
      break                       // network died mid-flight; retry next pass
    }
  }
  return { sent, pending: (await pendingScreenings()).length }
}
