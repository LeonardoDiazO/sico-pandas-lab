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

export interface ExcelProfileColumn {
  name: string;
  type: 'categorica' | 'numerica' | 'fecha' | 'descartable';
}

export interface ExcelProfile {
  verdict: 'usable' | 'usable_con_limpieza' | 'no_usable';
  headerRowIndex: number | null;
  columns: ExcelProfileColumn[];
  detail: string;
}

export interface LoadResult {
  variable: string;
  rows: number;
  columns: string[];
  note?: string | null;
  profile?: ExcelProfile;
  bound?: boolean;
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

export interface CardinalityWarning {
  column: string;
  uniqueCount: number;
  threshold: number;
  suggestion: string;
}

export interface ChartResult extends CellResult {
  needsConfirmation: boolean;
  cardinalityWarning: CardinalityWarning | null;
}

// Story 6.1: 'torta' | 'barras' | 'linea' | 'histograma' - mirrors ChartKind
// in shared/no-code-chart/no-code-chart.component.ts (Story 5.2), where the
// canonical type still lives (do not treat this as a second source of truth,
// it's the same closed set expressed as a string literal union here so this
// model file doesn't need to import from a component).
export interface ChartInterpretation {
  resolved: boolean;
  column: string | null;
  valueColumn: string | null;
  chartType: 'torta' | 'barras' | 'linea' | 'histograma' | null;
  reason: string | null;
}
