import { CommonModule } from '@angular/common';
import { NgModule } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MonacoEditorModule } from 'ngx-monaco-editor-v2';

import { CellResultComponent } from './cell-result/cell-result.component';
import { ChartHelperComponent } from './chart-helper/chart-helper.component';
import { CodeCellComponent } from './code-cell/code-cell.component';
import { DataSourcePanelComponent } from './data-source-panel/data-source-panel.component';
import { LoadedVariablesComponent } from './loaded-variables/loaded-variables.component';
import { SavedQueriesComponent } from './saved-queries/saved-queries.component';

@NgModule({
  declarations: [
    CellResultComponent,
    CodeCellComponent,
    DataSourcePanelComponent,
    ChartHelperComponent,
    LoadedVariablesComponent,
    SavedQueriesComponent,
  ],
  imports: [CommonModule, FormsModule, MonacoEditorModule],
  exports: [
    CellResultComponent,
    CodeCellComponent,
    DataSourcePanelComponent,
    ChartHelperComponent,
    LoadedVariablesComponent,
    SavedQueriesComponent,
    CommonModule,
    FormsModule,
  ],
})
export class SharedModule {}
