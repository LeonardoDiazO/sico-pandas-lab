import { HTTP_INTERCEPTORS, HttpClient, provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';

import { SessionInterceptor } from './session.interceptor';
import { SessionService } from './session.service';

describe('SessionInterceptor', () => {
  let http: HttpClient;
  let ctrl: HttpTestingController;
  let session: SessionService;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: HTTP_INTERCEPTORS, useClass: SessionInterceptor, multi: true },
      ],
    });
    http = TestBed.inject(HttpClient);
    ctrl = TestBed.inject(HttpTestingController);
    session = TestBed.inject(SessionService);
  });

  afterEach(() => {
    ctrl.verify();
    localStorage.clear();
  });

  it('stores the token the server issues and sends it back afterwards', () => {
    http.get('/api/a').subscribe();
    const first = ctrl.expectOne('/api/a');
    expect(first.request.headers.has('X-Session-Id')).toBeFalse();
    first.flush({}, { headers: { 'X-Session-Id': 'tok.signed' } });
    expect(session.token).toBe('tok.signed');

    http.get('/api/b').subscribe();
    expect(ctrl.expectOne('/api/b').request.headers.get('X-Session-Id')).toBe('tok.signed');
  });

  it('parallel first requests wait for the first token instead of each opening a session', () => {
    http.get('/api/one').subscribe();
    http.get('/api/two').subscribe();
    // Only the first one is out while there is no token yet.
    const one = ctrl.expectOne('/api/one');
    ctrl.expectNone('/api/two');
    one.flush({}, { headers: { 'X-Session-Id': 'tok.1' } });
    expect(ctrl.expectOne('/api/two').request.headers.get('X-Session-Id')).toBe('tok.1');
  });

  it('sends the team key when one is stored', () => {
    session.setToken('t');
    session.setAccessKey('clave');
    http.get('/api/c').subscribe();
    expect(ctrl.expectOne('/api/c').request.headers.get('X-Access-Key')).toBe('clave');
  });

  it('flags access denied on a 401', () => {
    session.setToken('t');
    let denied = false;
    session.accessDenied.subscribe((d) => (denied = d));
    http.get('/api/d').subscribe({ error: () => undefined });
    ctrl.expectOne('/api/d').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(denied).toBeTrue();
  });

  it('keeps working in memory when localStorage is blocked', () => {
    spyOn(Storage.prototype, 'setItem').and.throwError('blocked');
    spyOn(Storage.prototype, 'getItem').and.throwError('blocked');
    session.setToken('solo-memoria');
    expect(session.token).toBe('solo-memoria');
  });

  it('when the first request fails without a token, the waiting ones still go out one at a time', () => {
    http.get('/api/first').subscribe({ error: () => undefined });
    http.get('/api/w1').subscribe();
    http.get('/api/w2').subscribe();
    ctrl.expectOne('/api/first').flush({}, { status: 503, statusText: 'Unavailable' });
    // Only ONE of the waiters becomes the next bootstrap request.
    const next = ctrl.match((r) => r.url === '/api/w1' || r.url === '/api/w2');
    expect(next.length).toBe(1);
    next[0].flush({}, { headers: { 'X-Session-Id': 'tok.after' } });
    const last = ctrl.match((r) => r.url === '/api/w1' || r.url === '/api/w2');
    expect(last.length).toBe(1);
    expect(last[0].request.headers.get('X-Session-Id')).toBe('tok.after');
    last[0].flush({});
  });
});
