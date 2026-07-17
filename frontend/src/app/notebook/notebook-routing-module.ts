import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { NotebookHomeComponent } from './notebook-home/notebook-home.component';

const routes: Routes = [{ path: '', component: NotebookHomeComponent }];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class NotebookRoutingModule {}
