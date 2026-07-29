import { HttpErrorResponse } from '@angular/common/http';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { ExcelProfileColumn, TableResult } from '../../models/api.models';
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
  sortResult: TableResult | null = null;

  // Story 8.2: group-by columns (checkboxes, same pattern as Story 7.2's
  // chart grouping) + a required value column to sum and take percentages
  // of - deliberately no "count rows" mode without a value column (out of
  // scope, the feedback was specifically about percentage of *value*).
  selectedGroupColumns: string[] = [];
  selectedSummaryValueColumn: string | null = null;
  summarizing = false;
  summaryResult: TableResult | null = null;

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
      // Smart default (user feedback): auto-pick the first numeric column
      // for both the sort and summary value selectors on a fresh profile,
      // instead of leaving them empty - one less click, and avoids the
      // reported confusion where forgetting to pick a value column
      // silently changes what's being shown.
      if (!this.numericColumns.some((c) => c.name === this.selectedValueColumn)) {
        this.selectedValueColumn = this.numericColumns[0]?.name ?? null;
      }
      if (!this.numericColumns.some((c) => c.name === this.selectedSummaryValueColumn)) {
        this.selectedSummaryValueColumn = this.numericColumns[0]?.name ?? null;
      }
      const groupable = new Set(this.groupableColumns.map((c) => c.name));
      this.selectedGroupColumns = this.selectedGroupColumns.filter((name) => groupable.has(name));
      // Reverted: auto-picking groupableColumns[0] regardless of type/
      // meaning (e.g. a junk placeholder column that happens to sort first)
      // produced a confusing first summary nobody asked for - same reasoning
      // that reverted this default in no-code-chart.component.ts (real bug:
      // it broke línea there by picking a non-"fecha" column). Grouping
      // selection stays manual; only the value-column default below is kept.
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
            explanation: null,
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
          explanation: null,
        };
      },
    });
  }
}
