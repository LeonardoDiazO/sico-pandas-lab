import { NgModule } from '@angular/core';

import { SharedModule } from '../shared/shared-module';
import { NotebookHomeComponent } from './notebook-home/notebook-home.component';
import { NotebookRoutingModule } from './notebook-routing-module';

@NgModule({
  declarations: [NotebookHomeComponent],
  imports: [SharedModule, NotebookRoutingModule],
})
export class NotebookModule {}
