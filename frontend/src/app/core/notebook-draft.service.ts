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
}
