import { HTTP_INTERCEPTORS, provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { LOCALE_ID, NgModule, provideBrowserGlobalErrorListeners } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BrowserModule } from '@angular/platform-browser';
import { RouteReuseStrategy } from '@angular/router';
import { MonacoEditorModule } from 'ngx-monaco-editor-v2';

import { registerLocaleData } from '@angular/common';
import localeEsCO from '@angular/common/locales/es-CO';

// Colombian number/currency formatting ("." thousands, "," decimals, "$" for
// COP) for every `number`/`currency` pipe in the app - this is a Colombian
// accounting tool (SICO), so es-CO is the right default everywhere, not just
// for the money-detected KPI values.
registerLocaleData(localeEsCO);

import { App } from './app';
import { AppRoutingModule } from './app-routing-module';
import { KeepAliveRouteReuseStrategy } from './core/keep-alive-route-reuse.strategy';
import { SessionInterceptor } from './core/session.interceptor';
import { ToastHostComponent } from './core/toast-host/toast-host.component';
import { TourOverlayComponent } from './core/tour-overlay/tour-overlay.component';

@NgModule({
  declarations: [App, TourOverlayComponent, ToastHostComponent],
  imports: [
    BrowserModule,
    FormsModule,
    AppRoutingModule,
    // Must point straight at loader.js's folder -- the library only expands a
    // bare 'assets' to '/monaco/min/vs' automatically, any other string (like
    // our 'assets/monaco') is used as-is and 404s, leaving Monaco stuck
    // uninitialized (an inert empty box that never accepts keystrokes).
    MonacoEditorModule.forRoot({ baseUrl: 'assets/monaco/min/vs' }),
  ],
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideHttpClient(withInterceptorsFromDi()),
    { provide: HTTP_INTERCEPTORS, useClass: SessionInterceptor, multi: true },
    { provide: LOCALE_ID, useValue: 'es-CO' },
    // Main screens stay alive while switching tabs (see the strategy).
    { provide: RouteReuseStrategy, useClass: KeepAliveRouteReuseStrategy },
  ],
  bootstrap: [App],
})
export class AppModule {}
