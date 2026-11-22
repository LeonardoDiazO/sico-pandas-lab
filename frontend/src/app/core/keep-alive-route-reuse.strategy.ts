import { Injectable } from '@angular/core';
import { ActivatedRouteSnapshot, DetachedRouteHandle, RouteReuseStrategy } from '@angular/router';

// Enough for the three main screens plus a few open lessons; the oldest is
// destroyed beyond this, so memory stays bounded.
const MAX_KEPT = 6;

/**
 * Keeps the main screens alive while switching tabs (user feedback: going
 * from Notebook to Sin código and back wiped the dashboard, the wizard step,
 * the cells and their results). Routes opt in with `data: { keepAlive: true }`;
 * everything else (e.g. the lesson list, so its progress is always fresh)
 * behaves as before. Shared data consistency is handled by DatasetService.
 */
@Injectable()
export class KeepAliveRouteReuseStrategy implements RouteReuseStrategy {
  private readonly handles = new Map<string, DetachedRouteHandle>();

  private keepAlive(route: ActivatedRouteSnapshot): boolean {
    return !!route.routeConfig && !!route.component && route.data?.['keepAlive'] === true;
  }

  // Full URL of the route (e.g. "guiado/01-fundamentos"): each lesson keeps its own state.
  private key(route: ActivatedRouteSnapshot): string {
    return route.pathFromRoot
      .map((r) => r.url.map((segment) => segment.path).join('/'))
      .filter(Boolean)
      .join('/');
  }

  shouldDetach(route: ActivatedRouteSnapshot): boolean {
    return this.keepAlive(route);
  }

  store(route: ActivatedRouteSnapshot, handle: DetachedRouteHandle | null): void {
    const key = this.key(route);
    if (!handle) {
      this.handles.delete(key);
      return;
    }
    this.handles.delete(key);
    this.handles.set(key, handle);
    while (this.handles.size > MAX_KEPT) {
      const [oldestKey, oldest] = this.handles.entries().next().value as [string, DetachedRouteHandle];
      this.handles.delete(oldestKey);
      destroyHandle(oldest);
    }
  }

  shouldAttach(route: ActivatedRouteSnapshot): boolean {
    return this.keepAlive(route) && this.handles.has(this.key(route));
  }

  retrieve(route: ActivatedRouteSnapshot): DetachedRouteHandle | null {
    if (!this.keepAlive(route)) {
      return null;
    }
    const key = this.key(route);
    const handle = this.handles.get(key) ?? null;
    // Re-insert: Map order doubles as least-recently-used order.
    if (handle) {
      this.handles.delete(key);
      this.handles.set(key, handle);
    }
    return handle;
  }

  shouldReuseRoute(future: ActivatedRouteSnapshot, curr: ActivatedRouteSnapshot): boolean {
    return future.routeConfig === curr.routeConfig;
  }

  /** Number of screens currently kept alive (for tests/diagnostics). */
  get size(): number {
    return this.handles.size;
  }
}

function destroyHandle(handle: DetachedRouteHandle): void {
  const ref = (handle as { componentRef?: { destroy(): void } }).componentRef;
  ref?.destroy();
}
