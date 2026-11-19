import { Component, EventEmitter, Input, OnChanges, OnDestroy, Output, SimpleChanges } from '@angular/core';
import { Subscription } from 'rxjs';

import { ColumnClassification, ColumnRole, ExcelProfileColumn } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';

export interface ProfileState {
  variable: string;
  columns: ExcelProfileColumn[];
}

const ROLE_LABELS: Record<ColumnRole, string> = {
  dimension: 'Dimensión (agrupar por esto)',
  metrica: 'Métrica (sumar/promediar)',
  fecha: 'Fecha',
  identificador: 'Identificador (no agrupar)',
  descartar: 'Descartar',
};

const ROLE_SHORT: Record<ColumnRole, { one: string; many: string }> = {
  dimension: { one: 'dimensión', many: 'dimensiones' },
  metrica: { one: 'métrica', many: 'métricas' },
  fecha: { one: 'fecha', many: 'fechas' },
  identificador: { one: 'identificador', many: 'identificadores' },
  descartar: { one: 'descartada', many: 'descartadas' },
};

const TYPE_LABELS: Record<string, string> = {
  categorica: 'texto',
  numerica: 'número',
  fecha: 'fecha',
  descartable: 'vacía',
};

/**
 * "Capa semántica": al subir el Excel se propone un rol por columna (Gemini,
 * con reglas fijas de respaldo - ver semantic_classifier.py) y el usuario
 * corrige con un clic. Confirmar dispara el catálogo automático
 * (analysis_catalog.py). Valida antes de enviar que haya al menos una
 * dimensión y una métrica - sin ellas el catálogo no puede generar nada - y
 * marca cuando la clasificación cambió después del último tablero generado.
 */
@Component({
  selector: 'app-column-classification',
  standalone: false,
  templateUrl: './column-classification.component.html',
  styleUrl: './column-classification.component.scss',
})
export class ColumnClassificationComponent implements OnChanges, OnDestroy {
  @Input() profile: ProfileState | null = null;
  // True while the dashboard for the last confirmation is being generated.
  @Input() busy = false;
  @Output() confirmed = new EventEmitter<ColumnClassification[]>();

  readonly roleLabels = ROLE_LABELS;
  readonly roleOptions: ColumnRole[] = ['dimension', 'metrica', 'fecha', 'identificador', 'descartar'];

  loading = false;
  usedAssistant = false;
  classifications: ColumnClassification[] = [];
  errorMessage: string | null = null;
  private suggested: ColumnClassification[] = [];
  private confirmedSnapshot: string | null = null;
  private sub?: Subscription;

  constructor(private notebook: NotebookService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['profile'] && this.profile) {
      this.fetchSuggestion();
    }
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  fetchSuggestion(): void {
    // A newer file replaces any suggestion still in flight for the old one.
    this.sub?.unsubscribe();
    this.loading = true;
    this.errorMessage = null;
    this.classifications = [];
    this.confirmedSnapshot = null;
    this.sub = this.notebook.classifyColumns().subscribe({
      next: (res) => {
        this.loading = false;
        this.classifications = res.data.classifications.map((c) => ({ ...c }));
        this.suggested = res.data.classifications.map((c) => ({ ...c }));
        this.usedAssistant = res.data.usedAssistant;
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No se pudo sugerir la clasificación de columnas.';
      },
    });
  }

  typeOf(name: string): string | null {
    const type = this.profile?.columns.find((c) => c.name === name)?.type;
    return type ? (TYPE_LABELS[type] ?? type) : null;
  }

  count(role: ColumnRole): number {
    return this.classifications.filter((c) => c.role === role).length;
  }

  get roleSummary(): { role: ColumnRole; text: string }[] {
    return this.roleOptions
      .map((role) => ({ role, n: this.count(role) }))
      .filter((r) => r.n > 0)
      .map(({ role, n }) => ({ role, text: `${n} ${n === 1 ? ROLE_SHORT[role].one : ROLE_SHORT[role].many}` }));
  }

  get missing(): string | null {
    const dims = this.count('dimension');
    const mets = this.count('metrica');
    if (!dims && !mets) {
      return 'Marca al menos una columna como Dimensión y otra como Métrica.';
    }
    if (!dims) {
      return 'Falta una Dimensión: la columna por la que quieres agrupar (cliente, ciudad, producto…).';
    }
    if (!mets) {
      return 'Falta una Métrica: la columna numérica que quieres sumar (valor, cantidad…).';
    }
    return null;
  }

  get dirty(): boolean {
    return this.confirmedSnapshot !== null && this.confirmedSnapshot !== this.snapshot();
  }

  get modifiedFromSuggestion(): boolean {
    return this.classifications.some((c) => this.suggested.find((s) => s.name === c.name)?.role !== c.role);
  }

  isChanged(name: string): boolean {
    const now = this.classifications.find((c) => c.name === name)?.role;
    return this.suggested.find((s) => s.name === name)?.role !== now;
  }

  setRole(name: string, role: ColumnRole): void {
    const entry = this.classifications.find((c) => c.name === name);
    if (entry) {
      entry.role = role;
    }
  }

  resetToSuggestion(): void {
    this.classifications = this.suggested.map((c) => ({ ...c }));
  }

  confirm(): void {
    if (this.missing || this.busy) {
      return;
    }
    this.confirmedSnapshot = this.snapshot();
    this.confirmed.emit(this.classifications.map((c) => ({ ...c })));
  }

  private snapshot(): string {
    return JSON.stringify(this.classifications.map((c) => [c.name, c.role]));
  }
}
