import { Component, OnInit, inject } from '@angular/core';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { AuthService } from './core/auth.service';

@Component({
  selector: 'lb-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  templateUrl: './app.html',
  styleUrl: './app.css',
})
export class App implements OnInit {
  protected readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  ngOnInit(): void {
    // After a page reload the tokens are still stored, but the profile isn't: fetch it once.
    if (this.auth.isLoggedIn() && !this.auth.user()) {
      this.auth.loadUser().subscribe({ error: () => undefined }); // a 401 is handled by the interceptor
    }
  }

  logout(): void {
    this.auth.logout();
    void this.router.navigate(['/login']);
  }
}
