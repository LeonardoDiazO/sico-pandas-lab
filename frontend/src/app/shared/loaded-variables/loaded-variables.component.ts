import { Component, Input } from '@angular/core';

import { KnownVariable } from '../chart-helper/chart-helper.component';

/**
 * Visible reminder of which DataFrames already exist in this session, so the
 * learner doesn't have to scroll back up to remember what they loaded and
 * what each variable is called.
 */
@Component({
  selector: 'app-loaded-variables',
  standalone: false,
  templateUrl: './loaded-variables.component.html',
  styleUrl: './loaded-variables.component.scss',
})
export class LoadedVariablesComponent {
  @Input() variables: KnownVariable[] = [];
}
