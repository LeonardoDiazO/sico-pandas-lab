import { NgModule } from '@angular/core';

import { SharedModule } from '../shared/shared-module';
import { ConvatecHomeComponent } from './convatec-home/convatec-home.component';
import { ConvatecRoutingModule } from './convatec-routing-module';

@NgModule({
  declarations: [ConvatecHomeComponent],
  imports: [SharedModule, ConvatecRoutingModule],
})
export class ConvatecModule {}
