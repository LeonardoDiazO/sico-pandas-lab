import { NgModule } from '@angular/core';
import { RouterModule } from '@angular/router';

import { SharedModule } from '../shared/shared-module';
import { ConvatecHomeComponent } from './convatec-home/convatec-home.component';
import { ConvatecMaestrosComponent } from './convatec-maestros/convatec-maestros.component';
import { ConvatecRoutingModule } from './convatec-routing-module';

@NgModule({
  declarations: [ConvatecHomeComponent, ConvatecMaestrosComponent],
  imports: [SharedModule, ConvatecRoutingModule, RouterModule],
})
export class ConvatecModule {}
