import { notFound } from "next/navigation";

import {
  E2ERegressionPageContent,
  NarrativeLoadingFixture,
  VisualFoundationFixture,
  type NarrativeLoadingFixtureState,
} from "./E2ERegressionClient";
import {
  PlayExperienceFixture,
  type PlayExperienceFixtureState,
} from "./PlayExperienceFixture";

interface E2ERegressionPageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function resolveNarrativeLoadingFixtureState(
  value: string | string[] | undefined,
): NarrativeLoadingFixtureState | null {
  switch (value) {
    case "initial":
    case "partial":
    case "delayed":
    case "reconnecting":
    case "polling":
    case "failed":
      return value;
    default:
      return null;
  }
}

function resolveVisualFoundationFixture(
  value: string | string[] | undefined,
): boolean {
  return value === "foundation";
}

function resolvePlayExperienceFixtureState(
  value: string | string[] | undefined,
): PlayExperienceFixtureState | null {
  switch (value) {
    case "options":
    case "choosing":
    case "result":
    case "summary":
    case "history":
    case "reconnecting":
    case "polling":
    case "failed":
      return value;
    default:
      return null;
  }
}

export default async function E2ERegressionPage({
  searchParams,
}: E2ERegressionPageProps) {
  if (
    process.env.NODE_ENV === "production" &&
    process.env.ENABLE_E2E_REGRESSION_FIXTURES !== "1"
  ) {
    notFound();
  }

  const resolvedSearchParams = await searchParams;
  const narrativeLoadingFixtureState = resolveNarrativeLoadingFixtureState(
    resolvedSearchParams.narrativeLoading,
  );
  const visualFoundationFixture = resolveVisualFoundationFixture(
    resolvedSearchParams.visualSystem,
  );
  const playExperienceFixtureState = resolvePlayExperienceFixtureState(
    resolvedSearchParams.playState,
  );

  if (narrativeLoadingFixtureState) {
    return (
      <NarrativeLoadingFixture initialState={narrativeLoadingFixtureState} />
    );
  }

  if (playExperienceFixtureState) {
    return <PlayExperienceFixture initialState={playExperienceFixtureState} />;
  }

  if (visualFoundationFixture) {
    return <VisualFoundationFixture />;
  }

  return <E2ERegressionPageContent />;
}
