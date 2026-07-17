import { NgModule } from '@angular/core';
import { RouterModule } from '@angular/router';

import { SharedModule } from '../shared/shared-module';
import { GuidedHomeComponent } from './guided-home/guided-home.component';
import { GuidedLessonComponent } from './guided-lesson/guided-lesson.component';
import { GuidedRoutingModule } from './guided-routing-module';

@NgModule({
  declarations: [GuidedHomeComponent, GuidedLessonComponent],
  imports: [SharedModule, GuidedRoutingModule, RouterModule],
})
export class GuidedModule {}
