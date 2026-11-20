import { Component } from '@angular/core';

import { ToastService } from '../toast.service';

/** Renders ToastService notifications as floating cards (top-right). */
@Component({
  selector: 'app-toast-host',
  standalone: false,
  template: `
    <div class="toast-stack" aria-live="polite">
      @for (toast of toasts.toasts$ | async; track toast.id) {
        <div class="toast" [class.ok]="toast.ok" [class.bad]="!toast.ok" [attr.role]="toast.ok ? 'status' : 'alert'">
          <span class="toast-icon" aria-hidden="true">
            @if (toast.ok) {
              <svg viewBox="0 0 24 24"><path d="m5 12.5 4.5 4.5L19 7.5" /></svg>
            } @else {
              <svg viewBox="0 0 24 24"><path d="M12 8v5" /><path d="M12 16.5v.01" /><circle cx="12" cy="12" r="9" /></svg>
            }
          </span>
          <p class="toast-text">{{ toast.text }}</p>
          <button type="button" class="toast-close" (click)="toasts.dismiss(toast.id)" aria-label="Cerrar notificación">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12" /></svg>
          </button>
        </div>
      }
    </div>
  `,
  styleUrl: './toast-host.component.scss',
})
export class ToastHostComponent {
  constructor(public toasts: ToastService) {}
}
