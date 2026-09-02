import { Component, EventEmitter, Input, OnChanges, Output, SimpleChanges } from '@angular/core';

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

/**
 * "Capa semántica" - reemplaza tener que saber de antemano cuál columna es
 * la dimensión y cuál la métrica: al subir el Excel, se propone un rol por
 * columna (Gemini, con reglas fijas de respaldo si no hay asistente
 * disponible - ver semantic_classifier.py) y el usuario corrige con un
 * clic, no escribiendo nada. Confirmar dispara el catálogo automático de
 * análisis (analysis_catalog.py) sobre esos roles.
 */
@Component({
  selector: 'app-column-classification',
  standalone: false,
  templateUrl: './column-classification.component.html',
  styleUrl: './column-classification.component.scss',
})
export class ColumnClassificationComponent implements OnChanges {
  @Input() profile: ProfileState | null = null;
  @Output() confirmed = new EventEmitter<ColumnClassification[]>();

  readonly roleLabels = ROLE_LABELS;
  readonly roleOptions: ColumnRole[] = ['dimension', 'metrica', 'fecha', 'identificador', 'descartar'];

  loading = false;
  usedAssistant = false;
  classifications: ColumnClassification[] = [];
  errorMessage: string | null = null;

  constructor(private notebook: NotebookService) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['profile'] && this.profile) {
      this.fetchSuggestion();
    }
  }

  private fetchSuggestion(): void {
    this.loading = true;
    this.errorMessage = null;
    this.classifications = [];
    this.notebook.classifyColumns().subscribe({
      next: (res) => {
        this.loading = false;
        this.classifications = res.data.classifications;
        this.usedAssistant = res.data.usedAssistant;
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'No se pudo sugerir la clasificación de columnas. Intenta de nuevo.';
      },
    });
  }

  setRole(name: string, role: ColumnRole): void {
    const entry = this.classifications.find((c) => c.name === name);
    if (entry) {
      entry.role = role;
    }
  }

  confirm(): void {
    this.confirmed.emit(this.classifications);
  }
}
