import { Injectable, NgZone } from '@angular/core';
import { BehaviorSubject } from 'rxjs';

export interface Toast {
  id: number;
  text: string;
  ok: boolean;
}

// Successes confirm and get out of the way; errors stay until the person
// closes them, so a failure is never missed.
const SUCCESS_MS = 5000;
const MAX_VISIBLE = 4;

/**
 * App-wide notifications (floating toasts) - replaces the inline banners each
 * screen used to render at the top of its content, which were easy to miss
 * once the page was scrolled.
 */
@Injectable({ providedIn: 'root' })
export class ToastService {
  private nextId = 1;
  private readonly timers = new Map<number, ReturnType<typeof setTimeout>>();
  readonly toasts$ = new BehaviorSubject<Toast[]>([]);

  constructor(private zone: NgZone) {}

  show(text: string, ok: boolean): void {
    if (!text) {
      return;
    }
    const current = this.toasts$.value;
    // The same message again (e.g. a retried upload) refreshes, not stacks.
    const existing = current.find((t) => t.text === text && t.ok === ok);
    if (existing) {
      this.dismiss(existing.id);
    }
    const toast: Toast = { id: this.nextId++, text, ok };
    this.toasts$.next([...this.toasts$.value, toast].slice(-MAX_VISIBLE));
    if (ok) {
      this.timers.set(
        toast.id,
        setTimeout(() => this.zone.run(() => this.dismiss(toast.id)), SUCCESS_MS),
      );
    }
  }

  success(text: string): void {
    this.show(text, true);
  }

  error(text: string): void {
    this.show(text, false);
  }

  dismiss(id: number): void {
    const timer = this.timers.get(id);
    if (timer) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
    this.toasts$.next(this.toasts$.value.filter((t) => t.id !== id));
  }
}
