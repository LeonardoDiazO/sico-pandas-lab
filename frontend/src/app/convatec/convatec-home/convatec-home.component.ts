import { Component, OnInit } from '@angular/core';

import { ConvatecPreviewResult, ConvatecProcesarResult, ConvatecValidacionCifras } from '../../models/api.models';
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
export class ConvatecHomeComponent implements OnInit {
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

  preview: ConvatecPreviewResult | null = null;
  cargandoPreview = false;
  previewError: string | null = null;

  reconocimiento: UploadState = emptyUpload();
  validandoCifras = false;
  validacionCifras: ConvatecValidacionCifras | null = null;
  validacionError: string | null = null;

  constructor(private convatec: ConvatecService) {}

  ngOnInit(): void {
    // Maestros are global/persisted -- a fresh page load may already have
    // them from a previous upload (even a previous session/restart).
    this.convatec.estadoMasterTables().subscribe({
      next: (res) => {
        if (res.data) {
          const totalRows = res.data.productoRows + res.data.representantesRows + res.data.conveniosRows;
          this.maestros = { fileName: 'Ya cargadas', rows: totalRows, error: null };
        }
      },
      error: () => {
        // Silent: the upload dropzone still works normally if this check fails.
      },
    });
  }

  get puedeProcesar(): boolean {
    return this.maestros.rows !== null && (this.productos.rows !== null || this.servicios.rows !== null || this.enviosNacionales.rows !== null);
  }

  /** Drives the stepper header — 1-indexed, used to mark done/active/pending. */
  get pasoActual(): number {
    if (this.descargando) return 6;
    if (this.resultado) return this.comisionCalculada ? 5 : 4;
    if (this.maestros.rows !== null) return this.puedeProcesar ? 3 : 2;
    return 1;
  }

  get porcentajeResuelto(): number {
    if (!this.resultado || this.resultado.totalLineas === 0) return 0;
    const resueltas = this.resultado.totalLineas - this.resultado.lineasMarcadas;
    return Math.round((resueltas / this.resultado.totalLineas) * 100);
  }

  motivoClase(motivo: string): string {
    const key = motivo.toLowerCase();
    if (key.includes('duplicado')) return 'badge-duplicado';
    if (key.includes('convenio')) return 'badge-convenio';
    if (key.includes('ciudad')) return 'badge-ciudad';
    if (key.includes('homolog')) return 'badge-producto';
    return 'badge-generico';
  }

  iniciales(nombre: unknown): string {
    if (typeof nombre !== 'string' || !nombre.trim()) return '?';
    const partes = nombre.trim().split(/\s+/);
    return (partes[0][0] + (partes[1]?.[0] ?? '')).toUpperCase();
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

  onReconocimientoSelected(event: Event): void {
    const file = this.fileFrom(event);
    if (!file) return;
    this.convatec.uploadReconocimientoIngreso(file).subscribe({
      next: () => {
        this.reconocimiento = { fileName: file.name, rows: null, error: null };
        this.validacionCifras = null;
        this.validacionError = null;
      },
      error: (err) => {
        this.reconocimiento = { fileName: file.name, rows: null, error: this.errorMessage(err) };
      },
    });
  }

  validarCifras(): void {
    this.validandoCifras = true;
    this.validacionError = null;
    this.convatec.validarCifras().subscribe({
      next: (res) => {
        this.validacionCifras = res.data;
        this.validandoCifras = false;
      },
      error: (err) => {
        this.validacionError = this.errorMessage(err);
        this.validandoCifras = false;
      },
    });
  }

  reiniciarSesion(): void {
    this.convatec.reiniciarSesion().subscribe(() => {
      // Maestros are global/persisted -- "reiniciar" clears this session's
      // ventas/resultado only, never the territory rules (see backend
      // ConvatecSessionStore.reset docstring). ngOnInit already re-checks
      // this on load, so no need to re-check here again.
      this.productos = emptyUpload();
      this.servicios = emptyUpload();
      this.enviosNacionales = emptyUpload();
      this.reconocimiento = emptyUpload();
      this.resultado = null;
      this.comisionCalculada = false;
      this.valorReferencia = null;
      this.preview = null;
      this.validacionCifras = null;
    });
  }

  procesarCiclo(): void {
    this.procesando = true;
    this.procesarError = null;
    this.resultado = null;
    this.comisionCalculada = false;
    this.preview = null;
    this.convatec.procesarCiclo(this.mes).subscribe({
      next: (res) => {
        this.resultado = res.data;
        this.procesando = false;
        this.cargarPreview();
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
        this.cargarPreview();
      },
      error: (err) => {
        this.comisionError = this.errorMessage(err);
        this.calculandoComision = false;
      },
    });
  }

  private cargarPreview(): void {
    this.cargandoPreview = true;
    this.previewError = null;
    this.convatec.previewResultado(50).subscribe({
      next: (res) => {
        this.preview = res.data;
        this.cargandoPreview = false;
      },
      error: (err) => {
        this.previewError = this.errorMessage(err);
        this.cargandoPreview = false;
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
