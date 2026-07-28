import { create } from 'zustand';

interface UserProfile {
  username: string;
  is_admin: boolean;
  two_factor_enabled: boolean;
}

interface AuthState {
  user: UserProfile | null;
  loading: boolean;
  twoFactorRequired: boolean;
  tempToken: string | null;
  checking: boolean;

  setUser: (user: UserProfile | null) => void;
  checkAuth: () => Promise<void>;
  login: (username: string, password: string) => Promise<{ twoFactorRequired: boolean; tempToken?: string }>;
  verify2FA: (code: string, trustDevice: boolean) => Promise<void>;
  logout: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  loading: false,
  twoFactorRequired: false,
  tempToken: null,
  checking: true,

  setUser: (user) => set({ user }),

  checkAuth: async () => {
    set({ checking: true });
    try {
      const res = await fetch('/api/auth/me');
      if (res.ok) {
        const profile = await res.json();
        set({ user: profile });
      } else {
        set({ user: null });
      }
    } catch {
      set({ user: null });
    } finally {
      set({ checking: false });
    }
  },

  login: async (username, password) => {
    set({ loading: true });
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Login failed');
      }
      const data = await res.json();
      if (data.two_factor_required) {
        set({ twoFactorRequired: true, tempToken: data.temp_token, loading: false });
        return { twoFactorRequired: true, tempToken: data.temp_token };
      } else {
        set({ user: { username: data.username, is_admin: data.is_admin, two_factor_enabled: false }, twoFactorRequired: false, tempToken: null, loading: false });
        return { twoFactorRequired: false };
      }
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  verify2FA: async (code, trustDevice) => {
    set({ loading: true });
    const { tempToken } = get();
    if (!tempToken) throw new Error('No temporary session token found');

    try {
      const res = await fetch('/api/auth/2fa/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ temp_token: tempToken, code, trust_device: trustDevice }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || '2FA code verification failed');
      }
      const data = await res.json();
      set({
        user: { username: data.username, is_admin: data.is_admin, two_factor_enabled: true },
        twoFactorRequired: false,
        tempToken: null,
        loading: false
      });
    } catch (err) {
      set({ loading: false });
      throw err;
    }
  },

  logout: async () => {
    try {
      await fetch('/api/auth/logout', { method: 'POST' });
    } catch {
      // Ignored
    }
    set({ user: null, twoFactorRequired: false, tempToken: null });
  },
}));
export type { UserProfile };
