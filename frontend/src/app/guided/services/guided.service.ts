import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiResponse, ChallengeResult, Lesson, LessonSummary } from '../../models/api.models';

@Injectable({ providedIn: 'root' })
export class GuidedService {
  private readonly base = environment.apiUrl;

  constructor(private http: HttpClient) {}

  listLessons(): Observable<ApiResponse<{ lessons: LessonSummary[] }>> {
    return this.http.get<ApiResponse<{ lessons: LessonSummary[] }>>(`${this.base}/api/guided/lessons`);
  }

  getLesson(id: string): Observable<ApiResponse<Lesson>> {
    return this.http.get<ApiResponse<Lesson>>(`${this.base}/api/guided/lessons/${id}`);
  }

  checkChallenge(challengeId: string, code: string): Observable<ApiResponse<ChallengeResult>> {
    return this.http.post<ApiResponse<ChallengeResult>>(`${this.base}/api/guided/challenge/check`, {
      challenge_id: challengeId,
      code,
    });
  }
}
