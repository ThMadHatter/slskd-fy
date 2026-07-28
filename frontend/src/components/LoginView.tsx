'use client';

import React, { useState } from 'react';
import { useAuthStore } from '../store/authStore';
import { ShieldCheck, ShieldAlert, Key, User, CornerDownLeft, Loader2, CheckSquare, Square } from 'lucide-react';
import Input from './ui/Input';
import Button from './ui/Button';

export default function LoginView() {
  const { login, verify2FA, twoFactorRequired, tempToken, loading } = useAuthStore();

  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [trustDevice, setTrustDevice] = useState(false);
  const [errorMsg, setErrorInput] = useState<string | null>(null);

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorInput(null);
    if (!usernameInput.trim() || !passwordInput) {
      setErrorInput('Username and password are required');
      return;
    }

    try {
      await login(usernameInput, passwordInput);
    } catch (err: any) {
      setErrorInput(err?.message || 'Invalid credentials. Please try again.');
    }
  };

  const handle2FASubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorInput(null);
    if (!totpCode.trim()) {
      setErrorInput('Please enter your 2FA code');
      return;
    }

    try {
      await verify2FA(totpCode, trustDevice);
    } catch (err: any) {
      setErrorInput(err?.message || 'Invalid 2FA verification code');
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0a0b] flex items-center justify-center p-6 select-none font-sans">
      <div className="w-full max-w-md bg-[#131314] border border-[#27272a] p-8 flex flex-col gap-6 animate-fade-in-up">

        {/* Header Molecules */}
        <div className="text-center flex flex-col items-center gap-2">
          <div className="w-12 h-12 bg-[#1c1b1c] border border-[#27272a] flex items-center justify-center text-[#10b981]">
            {twoFactorRequired ? <ShieldAlert size={24} /> : <ShieldCheck size={24} />}
          </div>
          <div>
            <h1 className="font-headline-md text-headline-sm font-bold text-[#e5e2e3] uppercase tracking-tight">
              {twoFactorRequired ? 'Two-Factor Challenge' : 'Sonic Archive Portal'}
            </h1>
            <p className="font-data-mono text-[10px] text-[#bbcabf] opacity-75 mt-1 uppercase tracking-wider">
              {twoFactorRequired ? 'Enter TOTP Security Key' : 'Secure Admin Authentication Required'}
            </p>
          </div>
        </div>

        {errorMsg && (
          <div className="bg-red-500/10 border border-red-500/30 p-3 text-red-400 font-data-mono text-[11px] text-center">
            {errorMsg}
          </div>
        )}

        {/* Form elements */}
        {!twoFactorRequired ? (
          <form onSubmit={handleLoginSubmit} className="flex flex-col gap-5">
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase tracking-wider">
                Username
              </label>
              <Input
                icon={User}
                placeholder="e.g. admin"
                value={usernameInput}
                onChange={(e) => setUsernameInput(e.target.value)}
                disabled={loading}
              />
            </div>

            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase tracking-wider">
                Password
              </label>
              <Input
                icon={Key}
                type="password"
                placeholder="••••••••"
                value={passwordInput}
                onChange={(e) => setPasswordInput(e.target.value)}
                disabled={loading}
              />
            </div>

            <Button type="submit" variant="primary" className="mt-2 w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  AUTHENTICATING...
                </>
              ) : (
                <>
                  LOG IN TO ARCHIVE
                  <CornerDownLeft size={14} />
                </>
              )}
            </Button>
          </form>
        ) : (
          <form onSubmit={handle2FASubmit} className="flex flex-col gap-5">
            <div>
              <label className="block font-label-caps text-[10px] text-[#bbcabf] mb-1.5 uppercase tracking-wider">
                6-Digit Security Token
              </label>
              <Input
                icon={Key}
                type="text"
                placeholder="e.g. 123456"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                disabled={loading}
              />
            </div>

            {/* Trust this device checkbox */}
            <label className="flex items-center gap-2.5 cursor-pointer group mt-1 select-none">
              <input
                type="checkbox"
                checked={trustDevice}
                onChange={(e) => setTrustDevice(e.target.checked)}
                className="hidden"
                disabled={loading}
              />
              {trustDevice ? (
                <CheckSquare size={16} className="text-[#10b981]" />
              ) : (
                <Square size={16} className="text-[#bbcabf] group-hover:text-[#10b981]" />
              )}
              <span className="font-body-md text-xs text-[#bbcabf] group-hover:text-[#e5e2e3]">
                Trust this laptop/device for 30 days
              </span>
            </label>

            <Button type="submit" variant="primary" className="mt-2 w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 size={14} className="animate-spin" />
                  VERIFYING CODE...
                </>
              ) : (
                <>
                  VERIFY & PROCEED
                  <CornerDownLeft size={14} />
                </>
              )}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
