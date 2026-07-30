import { HttpErrorResponse } from '@angular/common/http';
import { Component, Input, OnChanges, SimpleChanges } from '@angular/core';

import { ColumnFilter, ExcelProfileColumn, TableResult } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';
import { looksLikeMoney } from '../money-format';
import { ExcelProfileState } from '../no-code-chart/no-code-chart.component';

// Same set Story 7.2 already established for chart grouping - a numeric
// column doesn't make sense to group BY, only to sum.
const GROUPABLE_TYPES: ExcelProfileColumn['type'][] = ['categorica', 'fecha'];

// User feedback (real file: "detallado comfenalco"): a summary with only a
// handful of groups (e.g. 3 cost types, 96%/2.4%/1.4%) reads better as KPI
// cards than as a table row-by-row - but a table is still the right shape
// once there are enough groups that cards would just wrap into a wall of
// boxes. Chosen well below chart_builder.py's HIGH_CARDINALITY_THRESHOLD
// (15): that threshold is about pie/bar legibility, this is about "still
// scannable as cards at a glance," a stricter bar.
const MAX_GROUPS_FOR_CARDS = 8;

// The columns build_summary_code() always adds on top of the group-name
// column and the value column itself (table_builder.py) - used to find
// "whatever key is left" as the group's label, without hardcoding the
// grouping column's actual name (which the user picks freely).
const SUMMARY_METRIC_KEYS = ['% del total', '% acumulado', '80/20'];

export interface SummaryCard {
  label: string;
  value: number;
  pctTotal: number;
  pctAcum: number;
  marker: string;
}

// Story 8.4 (user feedback: "colocar los filtros para ordenar también en
// ordenar tabla" / "también en Resumen y porcentaje por columna") - one
// shared "Filtrar por columna" panel narrows the rows BEFORE either
// "Ordenar tabla" or "Resumen y porcentaje por columna" runs, Excel-style:
// per column, choose which values to include (all included by default).
export interface ActiveFilter {
  column: string;
  availableValues: string[];
  selectedValues: Set<string>;
  loading: boolean;
}

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
  // User feedback: the aggregate total per group wasn't enough - "faltaria
  // un resumen detallado, en el que por ejemplo salga LATIN LOGISTICS ...
  // las n veces". Off by default (keeps the original aggregate-only view
  // as the default experience); checking it asks the backend for the
  // subtotal-plus-individual-rows shape instead (build_summary_detail_code).
  showDetail = false;
  // Defaulted to cards whenever a new eligible summary arrives (set in
  // summarizeTable() below); the user can still flip back to the table.
  viewAsCards = false;

  // Story 8.4: shared by both "Ordenar tabla" and "Resumen y porcentaje por
  // columna" below - filtering once and exploring both views is the real
  // workflow (Excel's own filter dropdown works the same way, applying to
  // whatever view/formula reads the filtered range).
  activeFilters: ActiveFilter[] = [];
  filterColumnToAdd: string | null = null;
  filterLoadError: string | null = null;

  constructor(private notebook: NotebookService) {}

  get filterableColumns(): ExcelProfileColumn[] {
    const active = new Set(this.activeFilters.map((f) => f.column));
    return this.groupableColumns.filter((c) => !active.has(c.name));
  }

  get filtersPayload(): ColumnFilter[] {
    return this.activeFilters.map((f) => ({ column: f.column, values: Array.from(f.selectedValues) }));
  }

  addFilter(): void {
    if (!this.profile || !this.filterColumnToAdd) {
      return;
    }
    const column = this.filterColumnToAdd;
    const filter: ActiveFilter = { column, availableValues: [], selectedValues: new Set(), loading: true };
    this.activeFilters = [...this.activeFilters, filter];
    this.filterColumnToAdd = null;
    this.filterLoadError = null;
    this.notebook.columnValues(this.profile.variable, column).subscribe({
      next: (res) => {
        const values = (res.data?.result_records ?? []).map((row) => String(row[column]));
        filter.availableValues = values;
        filter.selectedValues = new Set(values); // Excel default: everything selected
        filter.loading = false;
      },
      error: (err: HttpErrorResponse) => {
        this.activeFilters = this.activeFilters.filter((f) => f !== filter);
        const backendMessage = typeof err.error?.message === 'string' ? err.error.message : null;
        this.filterLoadError = backendMessage ?? `No se pudieron cargar los valores de '${column}'.`;
      },
    });
  }

  removeFilter(column: string): void {
    this.activeFilters = this.activeFilters.filter((f) => f.column !== column);
  }

  toggleFilterValue(filter: ActiveFilter, value: string): void {
    const next = new Set(filter.selectedValues);
    if (next.has(value)) {
      next.delete(value);
    } else {
      next.add(value);
    }
    filter.selectedValues = next;
  }

  setAllFilterValues(filter: ActiveFilter, selected: boolean): void {
    filter.selectedValues = selected ? new Set(filter.availableValues) : new Set();
  }

  // Cards only make sense for the aggregate view (one row per group) - the
  // detail view's records are individual source rows plus subtotal rows, a
  // shape cards were never designed to represent.
  get cardsEligible(): boolean {
    const records = this.summaryResult?.result_records;
    return (
      !this.showDetail &&
      !this.summaryResult?.error &&
      !!records &&
      records.length > 0 &&
      records.length <= MAX_GROUPS_FOR_CARDS
    );
  }

  // The value column is the same for every card in a given summary - whether
  // it's money is a property of that column, not of each individual group.
  get summaryValueIsMoney(): boolean {
    return looksLikeMoney(this.selectedSummaryValueColumn);
  }

  get summaryCards(): SummaryCard[] {
    const records = this.summaryResult?.result_records;
    const valueKey = this.selectedSummaryValueColumn;
    if (!records || !valueKey) {
      return [];
    }
    return records.map((row) => {
      const labelKey = Object.keys(row).find(
        (key) => key !== valueKey && !SUMMARY_METRIC_KEYS.includes(key),
      );
      return {
        label: labelKey ? String(row[labelKey]) : '',
        value: Number(row[valueKey]),
        pctTotal: Number(row['% del total']),
        pctAcum: Number(row['% acumulado']),
        marker: row['80/20'] ? String(row['80/20']) : '',
      };
    });
  }

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
      // Filters are file-specific (column names/values) - a new profile
      // means starting the filter panel fresh, same as sort/summary results.
      this.activeFilters = [];
      this.filterColumnToAdd = null;
      this.filterLoadError = null;
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
      .summaryTable(
        this.profile.variable,
        this.selectedGroupColumns,
        this.selectedSummaryValueColumn,
        this.showDetail,
        this.filtersPayload,
      )
      .subscribe({
        next: (res) => {
          this.summarizing = false;
          this.summaryResult = res.data ?? null;
          this.viewAsCards = this.cardsEligible;
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
          this.viewAsCards = false;
        },
      });
  }

  sortTable(): void {
    if (!this.profile || !this.selectedValueColumn || !this.canSort) {
      return;
    }
    this.sorting = true;
    this.sortResult = null;
    this.notebook
      .sortTable(this.profile.variable, this.selectedValueColumn, this.ascending, this.filtersPayload)
      .subscribe({
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
