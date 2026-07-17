import { Component, OnInit } from '@angular/core';

import { UserProfileService } from '../../core/user-profile.service';
import { LessonSummary } from '../../models/api.models';
import { GuidedService } from '../services/guided.service';

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
}
