import { ActivatedRouteSnapshot, DetachedRouteHandle } from '@angular/router';

import { KeepAliveRouteReuseStrategy } from './keep-alive-route-reuse.strategy';

function snap(path: string, keepAlive: boolean): ActivatedRouteSnapshot {
  const self = {
    routeConfig: { path },
    component: class {},
    data: keepAlive ? { keepAlive: true } : {},
    url: path.split('/').map((p) => ({ path: p })),
  } as unknown as ActivatedRouteSnapshot;
  (self as unknown as { pathFromRoot: ActivatedRouteSnapshot[] }).pathFromRoot = [self];
  return self;
}

function handle() {
  return { componentRef: { destroy: jasmine.createSpy('destroy') } };
}

describe('KeepAliveRouteReuseStrategy', () => {
  it('keeps opted-in screens and gives them back on return', () => {
    const s = new KeepAliveRouteReuseStrategy();
    const h = handle() as unknown as DetachedRouteHandle;
    expect(s.shouldDetach(snap('notebook', true))).toBeTrue();
    s.store(snap('notebook', true), h);
    expect(s.shouldAttach(snap('notebook', true))).toBeTrue();
    expect(s.retrieve(snap('notebook', true))).toBe(h);
  });

  it('never keeps screens that did not opt in (the lesson list stays fresh)', () => {
    const s = new KeepAliveRouteReuseStrategy();
    expect(s.shouldDetach(snap('guiado', false))).toBeFalse();
    expect(s.retrieve(snap('guiado', false))).toBeNull();
  });

  it('destroys the least recently used screen beyond the limit', () => {
    const s = new KeepAliveRouteReuseStrategy();
    const refs = Array.from({ length: 7 }, () => handle());
    refs.forEach((h, i) => s.store(snap(`guiado/l${i}`, true), h as unknown as DetachedRouteHandle));
    expect(s.size).toBe(6);
    expect(refs[0].componentRef.destroy).toHaveBeenCalled();
    expect(refs[6].componentRef.destroy).not.toHaveBeenCalled();
  });
});
