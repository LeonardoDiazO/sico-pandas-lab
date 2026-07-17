import { Component, EventEmitter, Input, Output } from '@angular/core';

import { CellResult } from '../../models/api.models';

/** Monaco editor options for a Python cell — kept minimal and beginner-friendly. */
const EDITOR_OPTIONS = {
  language: 'python',
  theme: 'vs',
  minimap: { enabled: false },
  scrollBeyondLastLine: false,
  fontSize: 14,
  automaticLayout: true,
  tabSize: 4,
  lineNumbers: 'on' as const,
};

export interface SnippetSaveRequest {
  name: string;
  note: string;
  code: string;
}

/**
 * A single editable + runnable code cell, backed by Monaco (the VS Code
 * editor) for real Python syntax highlighting — important for beginners who
 * are still learning to recognize Python syntax by sight.
 */
@Component({
  selector: 'app-code-cell',
  standalone: false,
  templateUrl: './code-cell.component.html',
  styleUrl: './code-cell.component.scss',
})
export class CodeCellComponent {
  @Input() code = '';
  @Input() running = false;
  @Input() result: CellResult | null = null;
  @Input() removable = true;
  @Input() runLabel = '▶ Ejecutar';
  // Off by default: only the free notebook wants "save as reusable snippet"
  // on its cells -- guided-lesson steps and the challenge cell don't wire up
  // a (save) handler, so a visible button there would just do nothing.
  @Input() allowSave = false;

  @Output() run = new EventEmitter<string>();
  @Output() remove = new EventEmitter<void>();
  @Output() codeChange = new EventEmitter<string>();
  @Output() save = new EventEmitter<SnippetSaveRequest>();

  readonly editorOptions = EDITOR_OPTIONS;

  savingOpen = false;
  saveName = '';
  saveNote = '';

  onRun(): void {
    if (!this.running && this.code.trim()) {
      this.run.emit(this.code);
    }
  }

  onCodeEdit(value: string): void {
    this.code = value;
    this.codeChange.emit(value);
  }

  // Monaco captures keyboard input itself, so Ctrl/Cmd+Enter is registered as
  // an editor command via its API rather than a template (keydown) handler.
  onEditorInit(editor: unknown): void {
    const monacoNs = (window as unknown as { monaco?: any }).monaco;
    if (!monacoNs) {
      return;
    }
    (editor as any).addCommand(monacoNs.KeyMod.CtrlCmd | monacoNs.KeyCode.Enter, () => this.onRun());
  }

  toggleSaveForm(): void {
    this.savingOpen = !this.savingOpen;
  }

  confirmSave(): void {
    const name = this.saveName.trim();
    if (!name) {
      return;
    }
    this.save.emit({ name, note: this.saveNote.trim(), code: this.code });
    this.cancelSave();
  }

  cancelSave(): void {
    this.savingOpen = false;
    this.saveName = '';
    this.saveNote = '';
  }
}
