import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

const routes: Routes = [
  { path: '', redirectTo: 'notebook', pathMatch: 'full' },
  {
    path: 'notebook',
    loadChildren: () => import('./notebook/notebook-module').then((m) => m.NotebookModule),
  },
  {
    path: 'guiado',
    loadChildren: () => import('./guided/guided-module').then((m) => m.GuidedModule),
  },
  { path: '**', redirectTo: 'notebook' },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
