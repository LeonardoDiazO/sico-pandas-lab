import { fakeAsync, TestBed, tick } from '@angular/core/testing';

import { ToastService } from './toast.service';

describe('ToastService', () => {
  let service: ToastService;

  beforeEach(() => {
    service = TestBed.inject(ToastService);
  });

  it('auto-dismisses a success but keeps an error until closed', fakeAsync(() => {
    service.success('Excel cargado');
    service.error('No se pudo subir');
    expect(service.toasts$.value.length).toBe(2);
    tick(5000);
    expect(service.toasts$.value.map((t) => t.text)).toEqual(['No se pudo subir']);
    service.dismiss(service.toasts$.value[0].id);
    expect(service.toasts$.value.length).toBe(0);
  }));

  it('the same message again refreshes instead of stacking', fakeAsync(() => {
    service.error('Sin conexión');
    service.error('Sin conexión');
    expect(service.toasts$.value.length).toBe(1);
  }));
});
