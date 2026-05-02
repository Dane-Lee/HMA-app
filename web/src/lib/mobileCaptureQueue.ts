import type { Side } from "./types";

export type QueuedCapture = {
  id: string;
  assessmentId: string;
  movementKey: string;
  side: Side;
  file: File;
  fileName: string;
  createdAt: string;
};

const DB_NAME = "hma-mobile-capture";
const STORE_NAME = "captures";
const DB_VERSION = 1;
const memoryQueue = new Map<string, QueuedCapture>();

function hasIndexedDb() {
  return typeof indexedDB !== "undefined";
}

function openQueueDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onerror = () => reject(request.error ?? new Error("Unable to open capture queue."));
    request.onsuccess = () => resolve(request.result);
  });
}

function withStore<T>(
  mode: IDBTransactionMode,
  action: (store: IDBObjectStore) => IDBRequest<T>
): Promise<T> {
  return openQueueDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, mode);
        const store = transaction.objectStore(STORE_NAME);
        const request = action(store);
        request.onerror = () => reject(request.error ?? new Error("Capture queue request failed."));
        request.onsuccess = () => resolve(request.result);
        transaction.oncomplete = () => db.close();
        transaction.onerror = () => {
          db.close();
          reject(transaction.error ?? new Error("Capture queue transaction failed."));
        };
      })
  );
}

export async function saveQueuedCapture(capture: QueuedCapture) {
  if (!hasIndexedDb()) {
    memoryQueue.set(capture.id, capture);
    return;
  }
  await withStore("readwrite", (store) => store.put(capture));
}

export async function deleteQueuedCapture(id: string) {
  if (!hasIndexedDb()) {
    memoryQueue.delete(id);
    return;
  }
  await withStore("readwrite", (store) => store.delete(id));
}

export async function deleteQueuedCapturesForAssessment(assessmentId: string) {
  const captures = await listQueuedCaptures(assessmentId);
  await Promise.all(captures.map((capture) => deleteQueuedCapture(capture.id)));
}

export async function listQueuedCaptures(assessmentId: string) {
  if (!hasIndexedDb()) {
    return Array.from(memoryQueue.values()).filter((capture) => capture.assessmentId === assessmentId);
  }
  const captures = await withStore<QueuedCapture[]>("readonly", (store) => store.getAll());
  return captures.filter((capture) => capture.assessmentId === assessmentId);
}
