import { createContext, useContext, useMemo, useState } from 'react';

import { IntakeResponse } from '../api/client';

type CaseContextValue = {
  intake: IntakeResponse | null;
  setIntake: (value: IntakeResponse | null) => void;
  clientId: number | null;
  dealId: number | null;
};

const CaseContext = createContext<CaseContextValue | null>(null);

export function CaseProvider({ children }: { children: React.ReactNode }) {
  const [intake, setIntake] = useState<IntakeResponse | null>(null);
  const value = useMemo(
    () => ({ intake, setIntake, clientId: intake?.client.id ?? null, dealId: intake?.deal.id ?? null }),
    [intake]
  );
  return <CaseContext.Provider value={value}>{children}</CaseContext.Provider>;
}

export function useCaseContext() {
  const ctx = useContext(CaseContext);
  if (!ctx) throw new Error('useCaseContext must be used in CaseProvider');
  return ctx;
}
