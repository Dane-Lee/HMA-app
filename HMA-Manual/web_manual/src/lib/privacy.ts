import type { ConsentPayload } from "./types";

export const PRIVACY_NOTICE_VERSION = "hma-manual-privacy-notice-v1";

export const PRIVACY_POSTURE_STATEMENT =
  "Use of HMA-Manual is voluntary and for ergonomic/wellness screening and provider support only; results and temporary review videos are confidential, access-limited, and not used as a stand-alone basis for employment decisions.";

export function buildConsentPayload(): ConsentPayload {
  return {
    notice_version: PRIVACY_NOTICE_VERSION,
    voluntary_wellness: true,
    purpose_limited: true,
    no_employment_decision: true,
    video_retention_acknowledged: true
  };
}
