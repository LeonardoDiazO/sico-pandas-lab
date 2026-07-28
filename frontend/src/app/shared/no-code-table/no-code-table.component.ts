import { HttpErrorResponse } from '@angular/common/http';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { CellResult, ExcelProfileColumn } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';
import { ExcelProfileState } from '../no-code-chart/no-code-chart.component';

// Same set Story 7.2 already established for chart grouping - a numeric
// column doesn't make sense to group BY, only to sum.
const GROUPABLE_TYPES: ExcelProfileColumn['type'][] = ['categorica', 'fecha'];

/**
 * Story 8.1: sort the raw rows of a bound DataFrame by a numeric column, no
 * Python involved - the simplest of Epic 8's "no-code table" flows. Reuses
 * app-cell-result to render the result table (same sanitized-HTML path the
 * free notebook already uses for any cell whose last expression is a
 * DataFrame), so this component only owns the column/direction selectors.
 */
@Component({
  selector: 'app-no-code-table',
  standalone: false,
  templateUrl: './no-code-table.component.html',
  styleUrl: './no-code-table.component.scss',
})
export class NoCodeTableComponent implements OnChanges {
  @Input() profile: ExcelProfileState | null = null;

  selectedValueColumn: string | null = null;
  // "Mayor a menor" first - matches the literal user request ("ordenar el
  // neto de toda la factura", read as biggest-first).
  ascending = false;
  sorting = false;
  sortResult: CellResult | null = null;

  // Story 8.2: group-by columns (checkboxes, same pattern as Story 7.2's
  // chart grouping) + a required value column to sum and take percentages
  // of - deliberately no "count rows" mode without a value column (out of
  // scope, the feedback was specifically about percentage of *value*).
  selectedGroupColumns: string[] = [];
  selectedSummaryValueColumn: string | null = null;
  summarizing = false;
  summaryResult: CellResult | null = null;

  constructor(private notebook: NotebookService) {}

  get numericColumns(): ExcelProfileColumn[] {
    return this.profile?.columns.filter((c) => c.type === 'numerica') ?? [];
  }

  get groupableColumns(): ExcelProfileColumn[] {
    return this.profile?.columns.filter((c) => GROUPABLE_TYPES.includes(c.type)) ?? [];
  }

  get canSort(): boolean {
    return !!this.profile && !!this.selectedValueColumn && !this.sorting;
  }

  get canSummarize(): boolean {
    return (
      !!this.profile &&
      this.selectedGroupColumns.length > 0 &&
      !!this.selectedSummaryValueColumn &&
      !this.summarizing
    );
  }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['profile']) {
      if (!this.numericColumns.some((c) => c.name === this.selectedValueColumn)) {
        this.selectedValueColumn = null;
      }
      if (!this.numericColumns.some((c) => c.name === this.selectedSummaryValueColumn)) {
        this.selectedSummaryValueColumn = null;
      }
      const groupable = new Set(this.groupableColumns.map((c) => c.name));
      this.selectedGroupColumns = this.selectedGroupColumns.filter((name) => groupable.has(name));
      this.sortResult = null;
      this.summaryResult = null;
    }
  }

  toggleGroupColumn(name: string): void {
    const index = this.selectedGroupColumns.indexOf(name);
    if (index === -1) {
      this.selectedGroupColumns = [...this.selectedGroupColumns, name];
    } else {
      this.selectedGroupColumns = this.selectedGroupColumns.filter((c) => c !== name);
    }
  }

  summarizeTable(): void {
    if (!this.profile || !this.canSummarize || !this.selectedSummaryValueColumn) {
      return;
    }
    this.summarizing = true;
    this.summaryResult = null;
    this.notebook
      .summaryTable(this.profile.variable, this.selectedGroupColumns, this.selectedSummaryValueColumn)
      .subscribe({
        next: (res) => {
          this.summarizing = false;
          this.summaryResult = res.data ?? null;
        },
        error: (err: HttpErrorResponse) => {
          this.summarizing = false;
          const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
          this.summaryResult = {
            stdout: null,
            result_html: null,
            result_text: null,
            image_base64: null,
            error: {
              type: 'RedError',
              message: backendMessage ?? 'No se pudo contactar el servidor.',
              traceback: '',
            },
          };
        },
      });
  }

  sortTable(): void {
    if (!this.profile || !this.selectedValueColumn || !this.canSort) {
      return;
    }
    this.sorting = true;
    this.sortResult = null;
    this.notebook.sortTable(this.profile.variable, this.selectedValueColumn, this.ascending).subscribe({
      next: (res) => {
        this.sorting = false;
        this.sortResult = res.data ?? null;
      },
      error: (err: HttpErrorResponse) => {
        // Same pattern as no-code-chart's generateChart() error handling -
        // surface the backend's specific message instead of a generic one.
        this.sorting = false;
        const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
        this.sortResult = {
          stdout: null,
          result_html: null,
          result_text: null,
          image_base64: null,
          error: {
            type: 'RedError',
            message: backendMessage ?? 'No se pudo contactar el servidor.',
            traceback: '',
          },
        };
      },
    });
  }
}
