import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';

import { GuidedHomeComponent } from './guided-home/guided-home.component';
import { GuidedLessonComponent } from './guided-lesson/guided-lesson.component';

const routes: Routes = [
  { path: '', component: GuidedHomeComponent },
  { path: ':id', component: GuidedLessonComponent },
];

@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule],
})
export class GuidedRoutingModule {}
