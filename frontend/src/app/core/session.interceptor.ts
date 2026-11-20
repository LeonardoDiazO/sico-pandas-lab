import {
  HttpErrorResponse,
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
  HttpResponse,
} from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable, defer, finalize, first, switchMap, tap, throwError, catchError } from 'rxjs';

import { SessionService } from './session.service';

const SESSION_HEADER = 'X-Session-Id';
const ACCESS_HEADER = 'X-Access-Key';

/**
 * Attaches the server-issued session token and the team access key to every
 * backend call, and stores a token the server sends back.
 *
 * Without a token yet, only ONE request goes out; the others wait until it
 * settles and then reuse the token it brought - otherwise the parallel
 * requests a screen fires on load would each get a different server session.
 */
@Injectable()
export class SessionInterceptor implements HttpInterceptor {
  constructor(private session: SessionService) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    return defer(() => {
      if (!this.session.token && this.session.tokenRequestInFlight) {
        return this.session.tokenSettled$.pipe(
          first(),
          switchMap(() => this.intercept(req, next)),
        );
      }
      return this.send(req, next);
    });
  }

  private send(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    const bootstrap = !this.session.token;
    if (bootstrap) {
      this.session.tokenRequestInFlight = true;
    }
    const headers: Record<string, string> = {};
    const token = this.session.token;
    if (token) {
      headers[SESSION_HEADER] = token;
    }
    const key = this.session.accessKey;
    if (key) {
      headers[ACCESS_HEADER] = key;
    }
    let settled = false;
    const settle = () => {
      if (bootstrap && !settled) {
        settled = true;
        this.session.tokenRequestInFlight = false;
        this.session.tokenSettled$.next();
      }
    };
    return next.handle(req.clone({ setHeaders: headers })).pipe(
      tap((event) => {
        if (event instanceof HttpResponse) {
          this.remember(event.headers.get(SESSION_HEADER));
          settle();
        }
      }),
      catchError((err: unknown) => {
        if (err instanceof HttpErrorResponse) {
          this.remember(err.headers?.get(SESSION_HEADER) ?? null);
          if (err.status === 401) {
            this.session.accessDenied$.next(true);
          }
        }
        settle();
        return throwError(() => err);
      }),
      finalize(settle),
    );
  }

  private remember(issued: string | null): void {
    if (issued) {
      this.session.setToken(issued);
    }
  }
}
