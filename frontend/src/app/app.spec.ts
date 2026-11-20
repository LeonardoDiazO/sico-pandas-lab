import { provideHttpClient, withInterceptorsFromDi, HTTP_INTERCEPTORS } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { FormsModule } from '@angular/forms';
import { RouterModule } from '@angular/router';

import { App } from './app';
import { SessionInterceptor } from './core/session.interceptor';
import { SessionService } from './core/session.service';
import { TourOverlayComponent } from './core/tour-overlay/tour-overlay.component';

describe('App', () => {
  let http: HttpTestingController;
  let session: SessionService;

  beforeEach(async () => {
    localStorage.clear();
    await TestBed.configureTestingModule({
      imports: [RouterModule.forRoot([]), FormsModule],
      declarations: [App, TourOverlayComponent],
      providers: [
        provideHttpClient(withInterceptorsFromDi()),
        provideHttpClientTesting(),
        { provide: HTTP_INTERCEPTORS, useClass: SessionInterceptor, multi: true },
      ],
    }).compileComponents();
    http = TestBed.inject(HttpTestingController);
    session = TestBed.inject(SessionService);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  function flushHealth(accessKeyRequired: boolean) {
    http
      .expectOne((r) => r.url.endsWith('/api/health'))
      .flush({ success: true, status: 200, message: 'ok', data: { service: 'x', accessKeyRequired, maxUploadMb: 15 } });
  }

  it('renders the brand', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(false);
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('.brand')?.textContent).toContain('sico-pandas-lab');
  });

  it('shows no key screen when the backend does not require a key', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(false);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.access-gate')).toBeNull();
  });

  it('asks for the team key when the backend requires one and none is stored', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(true);
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('.access-gate')).not.toBeNull();
  });

  it('a wrong key (401) is cleared, the gate stays and an error is shown', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(true);
    const app = fixture.componentInstance;
    app.accessKeyInput = 'mala';
    app.submitAccessKey();
    http
      .expectOne((r) => r.url.endsWith('/api/guided/lessons'))
      .flush({ success: false, status: 401, message: 'Ingresa la clave del equipo.', data: null }, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    expect(session.accessKey).toBeNull();
    expect(app.accessRequired).toBeTrue();
    expect(fixture.nativeElement.querySelector('.access-error')?.textContent).toContain('no es correcta');
  });

  it('a server error while verifying does NOT accept the key', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(true);
    const app = fixture.componentInstance;
    app.accessKeyInput = 'quizas';
    app.submitAccessKey();
    http
      .expectOne((r) => r.url.endsWith('/api/guided/lessons'))
      .flush({ success: false, status: 503, message: 'Servidor lleno', data: null }, { status: 503, statusText: 'Unavailable' });
    fixture.detectChanges();
    expect(session.accessKey).toBeNull();
    expect(app.accessRequired).toBeTrue();
    expect(app.accessError).toContain('No se pudo verificar');
  });

  it('a right key closes the gate and is kept for later calls', () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    flushHealth(true);
    const app = fixture.componentInstance;
    app.accessKeyInput = 'buena';
    app.submitAccessKey();
    const req = http.expectOne((r) => r.url.endsWith('/api/guided/lessons'));
    expect(req.request.headers.get('X-Access-Key')).toBe('buena');
    req.flush({ success: true, status: 200, message: 'ok', data: { lessons: [] } });
    fixture.detectChanges();
    expect(app.accessRequired).toBeFalse();
    expect(session.accessKey).toBe('buena');
    expect(fixture.nativeElement.querySelector('.access-gate')).toBeNull();
  });
});
