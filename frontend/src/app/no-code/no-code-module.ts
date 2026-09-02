import { NgModule } from '@angular/core';
import { RouterModule } from '@angular/router';

import { SharedModule } from '../shared/shared-module';
import { NoCodeHomeComponent } from './no-code-home/no-code-home.component';
import { NoCodeRoutingModule } from './no-code-routing-module';

@NgModule({
  declarations: [NoCodeHomeComponent],
  imports: [SharedModule, NoCodeRoutingModule, RouterModule],
})
export class NoCodeModule {}
