import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { ConvatecHomeComponent } from './convatec-home/convatec-home.component';
import { ConvatecMaestrosComponent } from './convatec-maestros/convatec-maestros.component';

const routes: Routes = [
  { path: '', component: ConvatecHomeComponent },
  { path: 'maestros', component: ConvatecMaestrosComponent },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class ConvatecRoutingModule {}
