import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';

/**
 * Holds the two credentials every backend call carries:
 *
 * - the session token, MINTED BY THE SERVER (auditoría 2026-11-18): the
 *   browser no longer invents its own id. The first response carries a signed
 *   token in the `X-Session-Id` response header; it is stored here and sent
 *   back on every request (see SessionInterceptor);
 * - the shared team key (`X-Access-Key`), when the backend requires one.
 *
 * Both are kept in localStorage when available, with an in-memory fallback:
 * if storage is blocked (private window, policy) the app still works for the
 * life of the tab instead of creating a new server session on every request.
 */
@Injectable({ providedIn: 'root' })
export class SessionService {
  private readonly tokenKey = 'sico-pandas-lab-session-token';
  private readonly accessKeyKey = 'sico-pandas-lab-access-key';
  private memory = new Map<string, string>();

  /** True while the first token-less request is in flight (see interceptor). */
  tokenRequestInFlight = false;
  /** Emits whenever a token request settles (with or without a token). */
  readonly tokenSettled$ = new Subject<void>();

  /** Raised when the backend answers 401: the team key is missing or wrong. */
  readonly accessDenied$ = new BehaviorSubject<boolean>(false);

  /** Upload size limit announced by /api/health (null until known). */
  maxUploadMb: number | null = null;

  get token(): string | null {
    return this.read(this.tokenKey);
  }

  setToken(token: string): void {
    this.write(this.tokenKey, token);
  }

  clearToken(): void {
    this.remove(this.tokenKey);
  }

  get accessKey(): string | null {
    return this.read(this.accessKeyKey);
  }

  setAccessKey(key: string): void {
    this.write(this.accessKeyKey, key);
  }

  clearAccessKey(): void {
    this.remove(this.accessKeyKey);
  }

  get accessDenied(): Observable<boolean> {
    return this.accessDenied$.asObservable();
  }

  private read(key: string): string | null {
    try {
      const value = localStorage.getItem(key);
      if (value !== null) {
        return value;
      }
    } catch {
      // Storage blocked - fall back to memory below.
    }
    return this.memory.get(key) ?? null;
  }

  private write(key: string, value: string): void {
    this.memory.set(key, value);
    try {
      localStorage.setItem(key, value);
    } catch {
      // Memory copy is enough for this tab.
    }
  }

  private remove(key: string): void {
    this.memory.delete(key);
    try {
      localStorage.removeItem(key);
    } catch {
      // Nothing persisted to remove.
    }
  }
}
