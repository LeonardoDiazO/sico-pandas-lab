import { Injectable } from '@angular/core';

export interface Snippet {
  id: string;
  name: string;
  note: string;
  code: string;
  createdAt: number;
}

/**
 * Named, intentionally-kept code the learner has decided is worth reusing --
 * "I built this analysis, it works, I don't want to rewrite it." Separate
 * from NotebookDraftService's unnamed autosave: this list only grows when the
 * user explicitly clicks "Guardar", never automatically.
 */
@Injectable({ providedIn: 'root' })
export class SnippetsService {
  private readonly key = 'sico-pandas-lab-snippets';

  list(): Snippet[] {
    try {
      const raw = localStorage.getItem(this.key);
      return raw ? JSON.parse(raw) : [];
    } catch {
      return [];
    }
  }

  save(name: string, note: string, code: string): Snippet[] {
    const snippet: Snippet = {
      id: this.generateId(),
      name,
      note,
      code,
      createdAt: Date.now(),
    };
    const updated = [...this.list(), snippet];
    this.persist(updated);
    return updated;
  }

  remove(id: string): Snippet[] {
    const updated = this.list().filter((s) => s.id !== id);
    this.persist(updated);
    return updated;
  }

  private persist(snippets: Snippet[]): void {
    localStorage.setItem(this.key, JSON.stringify(snippets));
  }

  private generateId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID();
    }
    return 'snip-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
}
