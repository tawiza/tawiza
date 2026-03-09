/**
 * Tawiza anonymous telemetry — opt-out via NEXT_PUBLIC_TELEMETRY_ENABLED=false
 *
 * See TELEMETRY.md at the root of the repository for full details.
 */

import posthog from 'posthog-js';

const TELEMETRY_ENABLED =
  typeof window !== 'undefined' &&
  process.env.NEXT_PUBLIC_TELEMETRY_ENABLED !== 'false' &&
  process.env.NEXT_PUBLIC_TELEMETRY_ENABLED !== '0';

// PostHog project key — points to the Tawiza team's analytics dashboard.
// This is a write-only key (cannot read data). Users can opt out entirely
// by setting NEXT_PUBLIC_TELEMETRY_ENABLED=false.
const POSTHOG_KEY = 'phc_PIhsounBxTTOTt7xYTitoorK6pXfmXHGaKZfLQsSvIo';
const POSTHOG_HOST = 'https://eu.i.posthog.com';

let initialized = false;

export function initTelemetry() {
  if (!TELEMETRY_ENABLED || !POSTHOG_KEY || initialized) return;
  if (typeof window === 'undefined') return;

  try {
    posthog.init(POSTHOG_KEY, {
      api_host: POSTHOG_HOST,
      autocapture: false,          // no automatic click tracking
      capture_pageview: true,      // page views only
      capture_pageleave: false,
      disable_session_recording: true, // no session replay
      persistence: 'memory',       // no cookies, no localStorage
      ip: false,                   // don't capture IP
      property_denylist: [         // extra safety
        '$ip',
        '$user_email',
        '$user_name',
      ],
    });
    initialized = true;
  } catch {
    // telemetry must never break the app
  }
}

export function capture(event: string, properties?: Record<string, unknown>) {
  if (!TELEMETRY_ENABLED || !initialized) return;
  try {
    posthog.capture(event, properties);
  } catch {
    // fail silently
  }
}

export function captureFeature(feature: string, props?: Record<string, unknown>) {
  capture(`feature:${feature}`, props);
}

export function capturePageView(page: string) {
  capture('page:view', { page });
}
