import { Component } from '@angular/core';

import { ConvatecProcesarResult } from '../../models/api.models';
import { ConvatecService, VentasTipo } from '../services/convatec.service';

interface UploadState {
  fileName: string | null;
  rows: number | null;
  error: string | null;
}

const emptyUpload = (): UploadState => ({ fileName: null, rows: null, error: null });

@Component({
  selector: 'app-convatec-home',
  standalone: false,
  templateUrl: './convatec-home.component.html',
  styleUrl: './convatec-home.component.scss',
})
export class ConvatecHomeComponent {
  maestros: UploadState = emptyUpload();
  productos: UploadState = emptyUpload();
  servicios: UploadState = emptyUpload();
  enviosNacionales: UploadState = emptyUpload();

  mes = new Date().getMonth() + 1;
  procesando = false;
  procesarError: string | null = null;
  resultado: ConvatecProcesarResult | null = null;

  valorReferencia: number | null = null;
  calculandoComision = false;
  comisionCalculada = false;
  comisionError: string | null = null;

  descargando = false;

  constructor(private convatec: ConvatecService) {}

  get puedeProcesar(): boolean {
    return this.maestros.rows !== null && (this.productos.rows !== null || this.servicios.rows !== null || this.enviosNacionales.rows !== null);
  }

  onMaestrosSelected(event: Event): void {
    const file = this.fileFrom(event);
    if (!file) return;
    this.convatec.uploadMasterTables(file).subscribe({
      next: (res) => {
        const totalRows = res.data.productoRows + res.data.representantesRows + res.data.conveniosRows;
        this.maestros = { fileName: file.name, rows: totalRows, error: null };
      },
      error: (err) => {
        this.maestros = { fileName: file.name, rows: null, error: this.errorMessage(err) };
      },
    });
  }

  onVentasSelected(tipo: VentasTipo, event: Event): void {
    const file = this.fileFrom(event);
    if (!file) return;
    this.convatec.uploadVentas(tipo, file).subscribe({
      next: (res) => this.setState(tipo, { fileName: file.name, rows: res.data.rows, error: null }),
      error: (err) => this.setState(tipo, { fileName: file.name, rows: null, error: this.errorMessage(err) }),
    });
  }

  reiniciarSesion(): void {
    this.convatec.reiniciarSesion().subscribe(() => {
      this.maestros = emptyUpload();
      this.productos = emptyUpload();
      this.servicios = emptyUpload();
      this.enviosNacionales = emptyUpload();
      this.resultado = null;
      this.comisionCalculada = false;
      this.valorReferencia = null;
    });
  }

  procesarCiclo(): void {
    this.procesando = true;
    this.procesarError = null;
    this.resultado = null;
    this.comisionCalculada = false;
    this.convatec.procesarCiclo(this.mes).subscribe({
      next: (res) => {
        this.resultado = res.data;
        this.procesando = false;
      },
      error: (err) => {
        this.procesarError = this.errorMessage(err);
        this.procesando = false;
      },
    });
  }

  calcularComisionIlustrativa(): void {
    if (this.valorReferencia === null) return;
    this.calculandoComision = true;
    this.comisionError = null;
    this.convatec.calcularComisionIlustrativa(this.valorReferencia).subscribe({
      next: () => {
        this.comisionCalculada = true;
        this.calculandoComision = false;
      },
      error: (err) => {
        this.comisionError = this.errorMessage(err);
        this.calculandoComision = false;
      },
    });
  }

  descargarResultado(): void {
    this.descargando = true;
    this.convatec.descargarResultado().subscribe({
      next: (blob) => {
        this.triggerDownload(blob, 'convatec_asignacion.xlsx');
        this.descargando = false;
      },
      error: () => {
        this.descargando = false;
      },
    });
  }

  private setState(tipo: VentasTipo, state: UploadState): void {
    if (tipo === 'productos') this.productos = state;
    else if (tipo === 'servicios') this.servicios = state;
    else this.enviosNacionales = state;
  }

  private fileFrom(event: Event): File | null {
    const input = event.target as HTMLInputElement;
    return input.files && input.files.length > 0 ? input.files[0] : null;
  }

  private errorMessage(err: unknown): string {
    const httpError = err as { error?: { message?: string } };
    return httpError?.error?.message || 'No se pudo contactar el servidor.';
  }

  private triggerDownload(blob: Blob, filename: string): void {
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    window.URL.revokeObjectURL(url);
  }
}
