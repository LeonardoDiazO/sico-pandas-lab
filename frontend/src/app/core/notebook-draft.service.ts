import { Injectable } from '@angular/core';

/**
 * Safety net for the free notebook: the code of every cell (not results --
 * those are cheap to recompute and stale results would be misleading) is
 * saved right before the tab/page actually goes away, so closing it by
 * accident doesn't lose work that was never executed.
 *
 * Deliberately separate from the "saved queries" library (SnippetsService):
 * this is an unnamed, single, ever-overwritten draft of "whatever I was
 * doing", not a curated list of things worth keeping on purpose.
 */
@Injectable({ providedIn: 'root' })
export class NotebookDraftService {
  private readonly key = 'sico-pandas-lab-notebook-draft';
  private readonly queueKey = 'sico-pandas-lab-notebook-queue';
  // In-memory fallback when localStorage is blocked: the hand-off happens
  // within one tab (in-app navigation), so memory is enough.
  private memoryQueue: string[] = [];

  load(): string[] | null {
    try {
      const raw = localStorage.getItem(this.key);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) && parsed.every((c) => typeof c === 'string') ? parsed : null;
    } catch {
      return null;
    }
  }

  save(codes: string[]): void {
    localStorage.setItem(this.key, JSON.stringify(codes));
  }

  clear(): void {
    localStorage.removeItem(this.key);
  }

  /** "Ver el código" (tablero sin código): code the Notebook should open as
   * new cells next time it loads. */
  enqueue(code: string): void {
    const queue = [...this.peekQueue(), code];
    this.memoryQueue = queue;
    try {
      localStorage.setItem(this.queueKey, JSON.stringify(queue));
    } catch {
      // memory fallback above
    }
  }

  /** Returns and empties the queued code. */
  takeQueue(): string[] {
    const queue = this.peekQueue();
    this.memoryQueue = [];
    try {
      localStorage.removeItem(this.queueKey);
    } catch {
      // nothing stored
    }
    return queue;
  }

  private peekQueue(): string[] {
    try {
      const raw = localStorage.getItem(this.queueKey);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.every((c) => typeof c === 'string')) {
          return parsed;
        }
      }
    } catch {
      // fall through to memory
    }
    return [...this.memoryQueue];
  }
}
