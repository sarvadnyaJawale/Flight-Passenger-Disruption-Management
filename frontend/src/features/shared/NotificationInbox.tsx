import { Inbox } from '@novu/react';

export function NotificationInbox() {
  const applicationIdentifier = import.meta.env.VITE_NOVU_APPLICATION_IDENTIFIER;

  if (!applicationIdentifier) {
    return null;
  }

  return (
    <Inbox
      applicationIdentifier={applicationIdentifier}
      subscriberId="occ-operator-demo"
      appearance={{
        variables: {
          colorPrimary: 'oklch(0.205 0 0)',
          colorPrimaryForeground: 'oklch(0.985 0 0)',
          colorSecondary: 'oklch(0.97 0 0)',
          colorSecondaryForeground: 'oklch(0.205 0 0)',
          colorBackground: 'oklch(1 0 0)',
          colorForeground: 'oklch(0.145 0 0)',
          colorNeutral: 'oklch(0.922 0 0)',
          fontSize: '14px',
        },
      }}
    />
  );
}
