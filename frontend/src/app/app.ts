import { Component, signal } from '@angular/core';

import { UserProfileService } from './core/user-profile.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.html',
  standalone: false,
  styleUrl: './app.scss'
})
export class App {
  protected readonly title = signal('frontend');

  userName: string | null = null;
  nameInput = '';

  constructor(private profile: UserProfileService) {
    this.userName = this.profile.name;
  }

  saveName(): void {
    if (!this.nameInput.trim()) {
      return;
    }
    this.profile.setName(this.nameInput);
    this.userName = this.profile.name;
  }

  editName(): void {
    this.nameInput = this.userName ?? '';
    this.userName = null;
  }
}
