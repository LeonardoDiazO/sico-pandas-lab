import { Injectable } from '@angular/core';

/**
 * Supplies a stable per-browser session id. With no auth in the MVP, this is
 * how the backend keeps each user's notebook worker separate.
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly key = 'sico-pandas-lab-session-id';

  get sessionId(): string {
    let id = localStorage.getItem(this.key);
    if (!id) {
      id = this.generateId();
      localStorage.setItem(this.key, id);
    }
    return id;
  }

  private generateId(): string {
    if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
      return crypto.randomUUID();
    }
    return 'sess-' + Math.random().toString(36).slice(2) + Date.now().toString(36);
  }
}
