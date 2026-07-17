// Mirror of the backend ApiResponse envelope (shared SICO contract).
export interface ApiResponse<T> {
  message: string;
  data: T;
  success: boolean;
  status: number;
}

export interface CellError {
  type: string;
  message: string;
  traceback: string;
}

export interface CellResult {
  stdout: string | null;
  result_html: string | null;
  result_text: string | null;
  image_base64: string | null;
  error: CellError | null;
  session_restarted?: boolean;
}

export interface TableInfo {
  schema: string;
  table: string;
}

export interface TablesPayload {
  schema: string;
  tables: TableInfo[];
  configured: boolean;
}

export interface LoadResult {
  variable: string;
  rows: number;
  columns: string[];
  note?: string | null;
}

export interface LessonSummary {
  id: string;
  title: string;
  summary: string;
}

export interface LessonStep {
  title: string;
  explanation: string;
  code: string;
}

export interface LessonChallenge {
  id: string;
  prompt: string;
  starter_code: string;
}

export interface Lesson {
  id: string;
  title: string;
  summary: string;
  steps: LessonStep[];
  challenge: LessonChallenge | null;
  next_lesson_id?: string | null;
  next_lesson_title?: string | null;
}

export interface ChallengeResult extends CellResult {
  challenge: { passed: boolean; message: string } | null;
}
