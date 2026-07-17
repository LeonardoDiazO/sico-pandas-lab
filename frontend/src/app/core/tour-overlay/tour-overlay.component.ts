import { Component, effect, OnDestroy } from '@angular/core';

import { TourService, TourStep } from '../tour.service';

const TOOLTIP_WIDTH = 300;
const TOOLTIP_HEIGHT_ESTIMATE = 170;
const HIGHLIGHT_PADDING = 6;
const GAP = 14;

@Component({
  selector: 'app-tour-overlay',
  standalone: false,
  templateUrl: './tour-overlay.component.html',
  styleUrl: './tour-overlay.component.scss',
})
export class TourOverlayComponent implements OnDestroy {
  rect: DOMRect | null = null;

  private resizeHandler = () => this.recompute();

  constructor(public tour: TourService) {
    window.addEventListener('resize', this.resizeHandler);
    effect(() => {
      const active = this.tour.active();
      // Reading stepIndex()/steps() here makes the effect re-run on every
      // step change, which is exactly when we need to re-locate the target.
      this.tour.stepIndex();
      this.tour.steps();
      if (active) {
        this.focusCurrentStep();
      } else {
        this.rect = null;
      }
    });
  }

  ngOnDestroy(): void {
    window.removeEventListener('resize', this.resizeHandler);
  }

  get currentStep(): TourStep | null {
    return this.tour.steps()[this.tour.stepIndex()] ?? null;
  }

  get isLast(): boolean {
    return this.tour.stepIndex() === this.tour.steps().length - 1;
  }

  get highlightLeft(): number {
    return (this.rect?.left ?? 0) - HIGHLIGHT_PADDING;
  }

  get highlightTop(): number {
    return (this.rect?.top ?? 0) - HIGHLIGHT_PADDING;
  }

  get highlightWidth(): number {
    return (this.rect?.width ?? 0) + HIGHLIGHT_PADDING * 2;
  }

  get highlightHeight(): number {
    return (this.rect?.height ?? 0) + HIGHLIGHT_PADDING * 2;
  }

  get tooltipLeft(): number {
    const raw = this.rect?.left ?? 12;
    return Math.max(12, Math.min(raw, window.innerWidth - TOOLTIP_WIDTH - 12));
  }

  get tooltipTop(): number {
    if (!this.rect) {
      return 12;
    }
    const below = this.rect.bottom + GAP;
    if (below + TOOLTIP_HEIGHT_ESTIMATE > window.innerHeight) {
      return Math.max(12, this.rect.top - TOOLTIP_HEIGHT_ESTIMATE - GAP);
    }
    return below;
  }

  next(): void {
    this.tour.next();
  }

  prev(): void {
    this.tour.prev();
  }

  skip(): void {
    this.tour.skip();
  }

  private focusCurrentStep(): void {
    const step = this.currentStep;
    if (!step) {
      this.rect = null;
      return;
    }
    const el = document.querySelector(step.target);
    const rect = el?.getBoundingClientRect() ?? null;
    if (!el || !rect || (rect.width === 0 && rect.height === 0)) {
      // Target isn't in this view, or is an empty/collapsed element (e.g. a
      // challenge box on a lesson that has none, or the loaded-variables
      // chip list before anything is loaded) -- skip forward without getting
      // stuck. Deferred so we don't write a signal from inside the effect
      // that's reading it.
      setTimeout(() => this.tour.next());
      return;
    }
    el.scrollIntoView({ block: 'center', behavior: 'smooth' });
    setTimeout(() => this.recompute(), 260);
  }

  private recompute(): void {
    const step = this.currentStep;
    const el = step ? document.querySelector(step.target) : null;
    this.rect = el ? el.getBoundingClientRect() : null;
  }
}
