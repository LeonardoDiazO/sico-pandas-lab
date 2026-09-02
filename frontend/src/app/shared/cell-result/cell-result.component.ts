import { Component, HostListener, Input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

import { CellResult } from '../../models/api.models';

type ExpandedView = 'table' | 'chart' | null;

@Component({
  selector: 'app-cell-result',
  standalone: false,
  templateUrl: './cell-result.component.html',
  styleUrl: './cell-result.component.scss',
})
export class CellResultComponent {
  @Input() result: CellResult | null = null;

  expanded: ExpandedView = null;

  constructor(private sanitizer: DomSanitizer) {}

  // The HTML is produced by our own backend (pandas.to_html) for an internal
  // tool, so trusting it is acceptable here.
  get safeHtml(): SafeHtml | null {
    if (!this.result?.result_html) {
      return null;
    }
    return this.sanitizer.bypassSecurityTrustHtml(this.result.result_html);
  }

  // Inline SVG (not an <img src="data:image/png;base64,...">) - user
  // feedback: "sería bueno tener un tooltip... para diferenciar[los]" -
  // native <title> hover tooltips (execution.py's _inject_svg_tooltips)
  // only fire when the SVG markup is inline in the DOM, not referenced via
  // <img>. Same trust rationale as safeHtml above - our own backend
  // (matplotlib) produced it.
  get safeChartSvg(): SafeHtml | null {
    if (!this.result?.chart_svg) {
      return null;
    }
    return this.sanitizer.bypassSecurityTrustHtml(this.result.chart_svg);
  }

  // User feedback: a chart/table squeezed into a small dashboard card is
  // hard to read - click either one to see it full-size in an overlay,
  // same content (safeHtml/safeChartSvg), just rendered without the card's
  // width/height constraints.
  expand(view: ExpandedView): void {
    this.expanded = view;
  }

  close(): void {
    this.expanded = null;
  }

  @HostListener('document:keydown.escape')
  onEscape(): void {
    this.close();
  }
}
