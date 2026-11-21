import { ToastService } from '../../core/toast.service';
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

// One screen per page of the lesson: each step, then the challenge (when the
// lesson has one), then the closing page - user feedback: scrolling down a
// long lesson to find the next step was uncomfortable.
export interface LessonPage {
  kind: 'step' | 'challenge' | 'finish';
  index: number; // step index for kind 'step'
  label: string;
}

const CONNECTION_ERROR_RESULT: CellResult = {
  stdout: null,
  result_html: null,
  result_text: null,
  chart_svg: null,
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
  knownVariables: KnownVariable[] = [];

  challengeCode = '';
  challengeResult: CellResult | null = null;
  challengeVerdict: { passed: boolean; message: string } | null = null;
  challengeRunning = false;

  pageIndex = 0;
  direction: 'forward' | 'back' = 'forward';

  constructor(
    private route: ActivatedRoute,
    private guided: GuidedService,
    private notebook: NotebookService,
    private profile: UserProfileService,
    private tour: TourService,
    private toast: ToastService,
  ) {}

  get pages(): LessonPage[] {
    const pages: LessonPage[] = this.steps.map((step, i) => ({ kind: 'step' as const, index: i, label: step.title }));
    if (this.lesson?.challenge) {
      pages.push({ kind: 'challenge', index: -1, label: 'Reto' });
    }
    pages.push({ kind: 'finish', index: -1, label: 'Cierre' });
    return pages;
  }

  get currentPage(): LessonPage | null {
    return this.pages[this.pageIndex] ?? null;
  }

  // A step counts as done once it ran without error; the challenge once passed.
  isPageDone(page: LessonPage): boolean {
    if (page.kind === 'step') {
      const step = this.steps[page.index];
      return !!step?.result && !step.result.error;
    }
    if (page.kind === 'challenge') {
      return !!this.challengeVerdict?.passed || this.isComplete;
    }
    return false;
  }

  goToPage(index: number): void {
    if (index < 0 || index >= this.pages.length || index === this.pageIndex) {
      return;
    }
    this.direction = index > this.pageIndex ? 'forward' : 'back';
    this.pageIndex = index;
    if (typeof window !== 'undefined' && window.scrollY > 0) {
      const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
      document.querySelector('.lesson-progress')?.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
    }
  }

  get nextLabel(): string {
    const next = this.pages[this.pageIndex + 1];
    if (!next) {
      return '';
    }
    if (next.kind === 'challenge') {
      return 'Siguiente: el reto';
    }
    if (next.kind === 'finish') {
      return 'Terminar la lección';
    }
    return 'Siguiente paso';
  }

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
    this.pageIndex = 0;
    this.direction = 'forward';
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
    // Review finding (Story 11.2): without this reset, an already-passed
    // challenge run again keeps `challengeVerdict` truthy the whole time,
    // so the @if block in the template never leaves the DOM between
    // attempts and the .passed entrance animation (this story's whole
    // point) only plays on the very first pass, never on a repeat.
    this.challengeVerdict = null;
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
    this.toast.show(message.text, message.ok);
  }

  onLoaded(result: LoadResult): void {
    const existing = this.knownVariables.find((v) => v.name === result.variable);
    if (existing) {
      existing.columns = result.columns;
    } else {
      this.knownVariables = [...this.knownVariables, { name: result.variable, columns: result.columns }];
    }
    this.refreshStepContent();
  }

  // After uploading an Excel mid-lesson, the backend can now generate example
  // code/explanations against the learner's own columns instead of the fixed
  // synthetic table (see WorkerManager.remember_profile / data_context.py) --
  // refetch so the steps already on screen pick it up without a full page
  // reload. Preserves each step's already-run `result` so re-uploading never
  // discards output the learner already produced.
  private refreshStepContent(): void {
    if (!this.lesson) {
      return;
    }
    this.guided.getLesson(this.lesson.id).subscribe({
      next: (res) => {
        this.lesson = res.data;
        this.steps = res.data.steps.map((s, i) => ({
          ...s,
          result: this.steps[i]?.result ?? null,
          running: false,
        }));
      },
    });
  }

  get isComplete(): boolean {
    return !!this.lesson && this.profile.isLessonComplete(this.lesson.id);
  }

  get userName(): string | null {
    return this.profile.name;
  }
}
