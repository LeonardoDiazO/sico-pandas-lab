import { Injectable, signal } from '@angular/core';

export interface TourStep {
  /** CSS selector for the element to highlight. Steps whose target isn't
   * present in the current view are skipped automatically (e.g. the
   * challenge box only exists on some lessons). */
  target: string;
  title: string;
  text: string;
}

/**
 * Lightweight product tour: highlights one element at a time with a tooltip.
 * No dependency, no video -- just a sequence of steps driven by signals so
 * the overlay component can react to them. Each tour is remembered as "seen"
 * in localStorage so it only auto-starts once per browser; a manual "?"
 * button lets the user replay it any time.
 */
@Injectable({ providedIn: 'root' })
export class TourService {
  readonly steps = signal<TourStep[]>([]);
  readonly stepIndex = signal(0);
  readonly active = signal(false);

  private readonly seenKey = 'sico-pandas-lab-tours-seen';
  private currentTourId: string | null = null;

  hasSeen(tourId: string): boolean {
    return this.seenList().includes(tourId);
  }

  start(tourId: string, steps: TourStep[]): void {
    this.currentTourId = tourId;
    this.steps.set(steps);
    this.stepIndex.set(0);
    this.active.set(true);
  }

  startIfFirstVisit(tourId: string, steps: TourStep[]): void {
    if (!this.hasSeen(tourId)) {
      this.start(tourId, steps);
    }
  }

  next(): void {
    if (this.stepIndex() + 1 < this.steps().length) {
      this.stepIndex.set(this.stepIndex() + 1);
    } else {
      this.finish();
    }
  }

  prev(): void {
    if (this.stepIndex() > 0) {
      this.stepIndex.set(this.stepIndex() - 1);
    }
  }

  skip(): void {
    this.finish();
  }

  finish(): void {
    if (this.currentTourId) {
      this.markSeen(this.currentTourId);
    }
    this.active.set(false);
    this.steps.set([]);
    this.stepIndex.set(0);
    this.currentTourId = null;
  }

  private seenList(): string[] {
    try {
      return JSON.parse(localStorage.getItem(this.seenKey) || '[]');
    } catch {
      return [];
    }
  }

  private markSeen(tourId: string): void {
    const list = this.seenList();
    if (!list.includes(tourId)) {
      localStorage.setItem(this.seenKey, JSON.stringify([...list, tourId]));
    }
  }
}
