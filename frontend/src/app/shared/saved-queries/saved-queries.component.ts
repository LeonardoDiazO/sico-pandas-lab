import { Component, EventEmitter, Input, Output } from '@angular/core';

import { Snippet } from '../../core/snippets.service';

/**
 * Personal library of named, reusable code the learner saved on purpose from
 * a cell (see CodeCellComponent's "💾 Guardar"). Purely a display + insert/
 * remove surface -- persistence lives in SnippetsService, kept in the parent
 * so it stays the single source of truth for the current list.
 */
@Component({
  selector: 'app-saved-queries',
  standalone: false,
  templateUrl: './saved-queries.component.html',
  styleUrl: './saved-queries.component.scss',
})
export class SavedQueriesComponent {
  @Input() snippets: Snippet[] = [];
  @Output() insert = new EventEmitter<string>();
  @Output() remove = new EventEmitter<string>();
}
