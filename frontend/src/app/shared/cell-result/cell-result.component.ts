import { Component, Input } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

import { CellResult } from '../../models/api.models';

@Component({
  selector: 'app-cell-result',
  standalone: false,
  templateUrl: './cell-result.component.html',
  styleUrl: './cell-result.component.scss',
})
export class CellResultComponent {
  @Input() result: CellResult | null = null;

  constructor(private sanitizer: DomSanitizer) {}

  // The HTML is produced by our own backend (pandas.to_html) for an internal
  // tool, so trusting it is acceptable here.
  get safeHtml(): SafeHtml | null {
    if (!this.result?.result_html) {
      return null;
    }
    return this.sanitizer.bypassSecurityTrustHtml(this.result.result_html);
  }
}
