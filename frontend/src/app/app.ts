import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnDestroy, OnInit, signal } from '@angular/core';
import { Subscription } from 'rxjs';

import { SessionService } from './core/session.service';
import { UserProfileService } from './core/user-profile.service';
import { GuidedService } from './guided/services/guided.service';
import { NotebookService } from './notebook/services/notebook.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  standalone: false,
  styleUrl: './app.scss'
})
export class App implements OnInit, OnDestroy {
  protected readonly title = signal('frontend');

  userName: string | null = null;
  nameInput = '';

  // Team access key gate (decisión #1): shown when the backend requires a
  // key and none is stored, or when any call comes back 401.
  accessRequired = false;
  accessKeyInput = '';
  accessChecking = false;
  accessError: string | null = null;
  private sub?: Subscription;

  constructor(
    private profile: UserProfileService,
    private session: SessionService,
    private notebook: NotebookService,
    private guided: GuidedService,
  ) {
    this.userName = this.profile.name;
  }

  ngOnInit(): void {
    this.sub = this.session.accessDenied.subscribe((denied) => {
      if (denied) {
        this.session.clearAccessKey();
        this.accessRequired = true;
      }
    });
    this.notebook.health().subscribe({
      next: (res) => {
        this.session.maxUploadMb = res.data?.maxUploadMb ?? null;
        if (res.data?.accessKeyRequired && !this.session.accessKey) {
          this.accessRequired = true;
        }
      },
      error: () => {
        // Health unreachable: nothing to gate yet; the screens report their own errors.
      },
    });
  }

  ngOnDestroy(): void {
    this.sub?.unsubscribe();
  }

  submitAccessKey(): void {
    const key = this.accessKeyInput.trim();
    if (!key || this.accessChecking) {
      return;
    }
    this.accessChecking = true;
    this.accessError = null;
    this.session.setAccessKey(key);
    // A protected endpoint (health is public) tells a right key from a wrong one.
    this.guided.listLessons().subscribe({
      next: () => {
        this.accessChecking = false;
        this.accessRequired = false;
        this.accessKeyInput = '';
        this.session.accessDenied$.next(false);
      },
      error: (err: HttpErrorResponse) => {
        this.accessChecking = false;
        this.session.clearAccessKey();
        this.accessError =
          err.status === 401
            ? 'Esa clave no es correcta. Pídela a quien administra la herramienta.'
            : 'No se pudo verificar la clave (el servidor no respondió). Intenta de nuevo.';
      },
    });
  }

  saveName(): void {
    if (!this.nameInput.trim()) {
      return;
    }
    this.profile.setName(this.nameInput);
    this.userName = this.profile.name;
  }

  editName(): void {
    this.nameInput = this.userName ?? '';
    this.userName = null;
  }
}
