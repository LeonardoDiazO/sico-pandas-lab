import { Component, OnInit } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

import { TourService } from '../../core/tour.service';
import { UserProfileService } from '../../core/user-profile.service';
import { CellResult, Lesson, LoadResult } from '../../models/api.models';
import { NotebookService } from '../../notebook/services/notebook.service';
import { KnownVariable } from '../../shared/chart-helper/chart-helper.component';
import { GuidedService } from '../services/guided.service';
import { GUIDED_TOUR_STEPS } from './guided-tour-steps';

interface GuidedStep {
  title: string;
  explanation: string;
  code: string;
  result: CellResult | null;
  running: boolean;
}

const CONNECTION_ERROR_RESULT: CellResult = {
  stdout: null,
  result_html: null,
  result_text: null,
  image_base64: null,
  error: { type: 'RedError', message: 'No se pudo contactar el servidor.', traceback: '' },
};

@Component({
  selector: 'app-guided-lesson',
  standalone: false,
  templateUrl: './guided-lesson.component.html',
  styleUrl: './guided-lesson.component.scss',
})
export class GuidedLessonComponent implements OnInit {
  lesson: Lesson | null = null;
  steps: GuidedStep[] = [];
  banner: { text: string; ok: boolean } | null = null;
  knownVariables: KnownVariable[] = [];

  challengeCode = '';
  challengeResult: CellResult | null = null;
  challengeVerdict: { passed: boolean; message: string } | null = null;
  challengeRunning = false;

  constructor(
    private route: ActivatedRoute,
    private guided: GuidedService,
    private notebook: NotebookService,
    private profile: UserProfileService,
    private tour: TourService,
  ) {}

  startTour(): void {
    this.tour.start('guided', GUIDED_TOUR_STEPS);
  }

  ngOnInit(): void {
    // Reacts to param changes so clicking "Siguiente lección" (same route
    // pattern, different :id) actually reloads the content instead of Angular
    // reusing the component instance with stale data.
    this.route.paramMap.subscribe((params) => {
      const id = params.get('id')!;
      this.loadLesson(id);
    });
  }

  private loadLesson(id: string): void {
    this.lesson = null;
    this.steps = [];
    this.challengeCode = '';
    this.challengeResult = null;
    this.challengeVerdict = null;
    this.challengeRunning = false;
    this.guided.getLesson(id).subscribe({
      next: (res) => {
        this.lesson = res.data;
        this.steps = res.data.steps.map((s) => ({ ...s, result: null, running: false }));
        if (res.data.challenge) {
          this.challengeCode = res.data.challenge.starter_code;
        }
        setTimeout(() => this.tour.startIfFirstVisit('guided', GUIDED_TOUR_STEPS));
      },
    });
  }

  // Runs guided cells through the exact same execution engine as the free
  // notebook, so variables carry across steps just like a real notebook.
  runStep(index: number, code: string): void {
    const step = this.steps[index];
    step.code = code;
    step.running = true;
    this.notebook.execute(code).subscribe({
      next: (res) => {
        step.result = res.data;
        step.running = false;
        // Lessons with a challenge only count as complete once the challenge
        // is actually passed (see runChallenge) -- running the demo steps
        // alone no longer marks them done.
        if (this.lesson && index === this.steps.length - 1 && !res.data.error && !this.lesson.challenge) {
          this.profile.markLessonComplete(this.lesson.id);
        }
      },
      error: () => {
        step.running = false;
        step.result = CONNECTION_ERROR_RESULT;
      },
    });
  }

  runChallenge(code: string): void {
    if (!this.lesson?.challenge) {
      return;
    }
    this.challengeCode = code;
    this.challengeRunning = true;
    this.guided.checkChallenge(this.lesson.challenge.id, code).subscribe({
      next: (res) => {
        this.challengeRunning = false;
        this.challengeResult = res.data;
        this.challengeVerdict = res.data.challenge;
        if (this.challengeVerdict?.passed && this.lesson) {
          this.profile.markLessonComplete(this.lesson.id);
        }
      },
      error: () => {
        this.challengeRunning = false;
        this.challengeResult = CONNECTION_ERROR_RESULT;
        this.challengeVerdict = null;
      },
    });
  }

  onMessage(message: { text: string; ok: boolean }): void {
    this.banner = message;
  }

  onLoaded(result: LoadResult): void {
    const existing = this.knownVariables.find((v) => v.name === result.variable);
    if (existing) {
      existing.columns = result.columns;
    } else {
      this.knownVariables = [...this.knownVariables, { name: result.variable, columns: result.columns }];
    }
  }

  get isComplete(): boolean {
    return !!this.lesson && this.profile.isLessonComplete(this.lesson.id);
  }

  get userName(): string | null {
    return this.profile.name;
  }
}
