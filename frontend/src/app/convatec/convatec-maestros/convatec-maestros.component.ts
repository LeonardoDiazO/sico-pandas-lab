import { Component, OnInit } from '@angular/core';

import { ConvatecComisionExternaFila, ConvatecMaestrosResumen } from '../../models/api.models';
import { ConvatecService } from '../services/convatec.service';

@Component({
  selector: 'app-convatec-maestros',
  standalone: false,
  templateUrl: './convatec-maestros.component.html',
  styleUrl: './convatec-maestros.component.scss',
})
export class ConvatecMaestrosComponent implements OnInit {
  resumen: ConvatecMaestrosResumen | null = null;
  cargando = false;
  error: string | null = null;

  comisionExterna: ConvatecComisionExternaFila[] | null = null;
  cargandoComisionExterna = false;
  comisionExternaError: string | null = null;

  constructor(private convatec: ConvatecService) {}

  ngOnInit(): void {
    this.cargar();
  }

  cargar(): void {
    this.cargando = true;
    this.error = null;
    this.convatec.maestrosResumen().subscribe({
      next: (res) => {
        this.resumen = res.data;
        this.cargando = false;
      },
      error: (err) => {
        this.error = this.errorMessage(err);
        this.cargando = false;
      },
    });
  }

  onComisionExternaSelected(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files && input.files.length > 0 ? input.files[0] : null;
    if (!file) return;
    this.cargandoComisionExterna = true;
    this.comisionExternaError = null;
    this.convatec.comisionExternaReferencia(file).subscribe({
      next: (res) => {
        this.comisionExterna = res.data.filas;
        this.cargandoComisionExterna = false;
      },
      error: (err) => {
        this.comisionExternaError = this.errorMessage(err);
        this.cargandoComisionExterna = false;
      },
    });
  }

  private errorMessage(err: unknown): string {
    const httpError = err as { error?: { message?: string } };
    return httpError?.error?.message || 'No se pudo contactar el servidor.';
  }
}
