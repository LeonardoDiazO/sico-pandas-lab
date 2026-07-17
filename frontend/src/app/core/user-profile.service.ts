import { Injectable } from '@angular/core';

export interface UserProfile {
  name: string;
  completedLessonIds: string[];
}

const EMPTY_PROFILE: UserProfile = { name: '', completedLessonIds: [] };

/**
 * Name + guided-lesson progress, kept only in this browser (localStorage).
 * No backend call, no account -- by explicit product decision this stays
 * local-only for now, so it never reopens the "no login" architecture call.
 */
@Injectable({ providedIn: 'root' })
export class UserProfileService {
  private readonly key = 'sico-pandas-lab-profile';

  get profile(): UserProfile {
    const raw = localStorage.getItem(this.key);
    if (!raw) {
      return EMPTY_PROFILE;
    }
    try {
      const parsed = JSON.parse(raw);
      return {
        name: typeof parsed.name === 'string' ? parsed.name : '',
        completedLessonIds: Array.isArray(parsed.completedLessonIds) ? parsed.completedLessonIds : [],
      };
    } catch {
      return EMPTY_PROFILE;
    }
  }

  get name(): string | null {
    return this.profile.name.trim() || null;
  }

  setName(name: string): void {
    this.save({ ...this.profile, name: name.trim() });
  }

  isLessonComplete(lessonId: string): boolean {
    return this.profile.completedLessonIds.includes(lessonId);
  }

  markLessonComplete(lessonId: string): void {
    const current = this.profile;
    if (current.completedLessonIds.includes(lessonId)) {
      return;
    }
    this.save({ ...current, completedLessonIds: [...current.completedLessonIds, lessonId] });
  }

  private save(profile: UserProfile): void {
    localStorage.setItem(this.key, JSON.stringify(profile));
  }
}
