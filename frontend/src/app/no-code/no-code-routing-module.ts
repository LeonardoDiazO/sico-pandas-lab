import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { NoCodeHomeComponent } from './no-code-home/no-code-home.component';

const routes: Routes = [{ path: '', component: NoCodeHomeComponent }];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class NoCodeRoutingModule {}
