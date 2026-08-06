import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { ConvatecHomeComponent } from './convatec-home/convatec-home.component';

const routes: Routes = [{ path: '', component: ConvatecHomeComponent }];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ConvatecRoutingModule {}
