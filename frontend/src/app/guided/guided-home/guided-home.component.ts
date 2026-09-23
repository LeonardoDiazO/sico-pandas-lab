import { Component, OnInit } from '@angular/core';

import { UserProfileService } from '../../core/user-profile.service';
import { LessonSummary } from '../../models/api.models';
import { GuidedService } from '../services/guided.service';

// Story 11.1: 3 estados de progreso derivados en el frontend - no hay campo
// de backend ni de localStorage para "actual"/"bloqueada" (ver Boundaries
// del spec), se recalculan a partir de isComplete() en cada acceso.
export type LessonMapState = 'completada' | 'actual' | 'bloqueada';

export interface LessonMapItem {
  lesson: LessonSummary;
  state: LessonMapState;
}

@Component({
  selector: 'app-guided-home',
  standalone: false,
  templateUrl: './guided-home.component.html',
  styleUrl: './guided-home.component.scss',
})
export class GuidedHomeComponent implements OnInit {
  lessons: LessonSummary[] = [];
  loading = true;

  constructor(
    private guided: GuidedService,
    private profile: UserProfileService,
  ) {}

  ngOnInit(): void {
    this.guided.listLessons().subscribe({
      next: (res) => {
        this.lessons = res.data.lessons;
        this.loading = false;
      },
      error: () => (this.loading = false),
    });
  }

  isComplete(lessonId: string): boolean {
    return this.profile.isLessonComplete(lessonId);
  }

  // "Actual" = primera lección (en el orden ya devuelto por el backend) que
  // no está completa. Todo lo que sigue después de ella queda "bloqueada"
  // hasta que se complete la actual; todo lo anterior (o completo) nunca se
  // bloquea. Si todas están completas, no hay "actual" ni "bloqueada".
  get lessonsWithState(): LessonMapItem[] {
    let currentAssigned = false;
    return this.lessons.map((lesson) => {
      if (this.isComplete(lesson.id)) {
        return { lesson, state: 'completada' as const };
      }
      if (!currentAssigned) {
        currentAssigned = true;
        return { lesson, state: 'actual' as const };
      }
      return { lesson, state: 'bloqueada' as const };
    });
  }
}
