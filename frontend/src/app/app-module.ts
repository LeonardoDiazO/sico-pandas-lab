import { HTTP_INTERCEPTORS, provideHttpClient, withInterceptorsFromDi } from '@angular/common/http';
import { NgModule, provideBrowserGlobalErrorListeners } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { BrowserModule } from '@angular/platform-browser';
import { MonacoEditorModule } from 'ngx-monaco-editor-v2';

import { App } from './app';
import { AppRoutingModule } from './app-routing-module';
import { SessionInterceptor } from './core/session.interceptor';
import { TourOverlayComponent } from './core/tour-overlay/tour-overlay.component';

@NgModule({
  declarations: [App, TourOverlayComponent],
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
  ],
  bootstrap: [App],
})
export class AppModule {}
