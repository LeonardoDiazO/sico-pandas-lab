import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  { path: '', redirectTo: 'notebook', pathMatch: 'full' },
  {
    path: 'notebook',
    loadChildren: () => import('./notebook/notebook-module').then((m) => m.NotebookModule),
  },
  {
    path: 'sin-codigo',
    loadChildren: () => import('./no-code/no-code-module').then((m) => m.NoCodeModule),
  },
  {
    path: 'guiado',
    loadChildren: () => import('./guided/guided-module').then((m) => m.GuidedModule),
  },
  // Convatec (client-specific commission/assignment module) is disconnected
  // on request -- its code stays under src/app/convatec in case the demo
  // work with that client resumes later; just no longer routable.
  { path: '**', redirectTo: 'notebook' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
