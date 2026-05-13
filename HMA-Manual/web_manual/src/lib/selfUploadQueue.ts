import type { Side } from "./types";

export type QueuedSelfVideo = {
  id: string;
  movementKey: string;
  side: Side;
  file: File;
  fileName: string;
  createdAt: string;
};

const DB_NAME = "hma-manual-upload";
const STORE_NAME = "review-videos";
const DB_VERSION = 1;
const memoryQueue = new Map<string, QueuedSelfVideo>();

function hasIndexedDb() {
  return typeof indexedDB !== "undefined";
}

function openDb(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: "id" });
      }
    };
    request.onerror = () => reject(request.error ?? new Error("Unable to open upload queue."));
    request.onsuccess = () => resolve(request.result);
  });
}

function withStore<T>(mode: IDBTransactionMode, action: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  return openDb().then(
    (db) =>
      new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, mode);
        const request = action(transaction.objectStore(STORE_NAME));
        request.onerror = () => reject(request.error ?? new Error("Upload queue request failed."));
        request.onsuccess = () => resolve(request.result);
        transaction.oncomplete = () => db.close();
        transaction.onerror = () => {
          db.close();
          reject(transaction.error ?? new Error("Upload queue transaction failed."));
        };
      })
  );
}

export async function saveQueuedSelfVideo(video: QueuedSelfVideo) {
  if (!hasIndexedDb()) {
    memoryQueue.set(video.id, video);
    return;
  }
  await withStore("readwrite", (store) => store.put(video));
}

export async function deleteQueuedSelfVideo(id: string) {
  if (!hasIndexedDb()) {
    memoryQueue.delete(id);
    return;
  }
  await withStore("readwrite", (store) => store.delete(id));
}

export async function listQueuedSelfVideos() {
  if (!hasIndexedDb()) {
    return Array.from(memoryQueue.values());
  }
  return withStore<QueuedSelfVideo[]>("readonly", (store) => store.getAll());
}
