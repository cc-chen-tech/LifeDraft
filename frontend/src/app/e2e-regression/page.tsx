import {
  E2ERegressionPageContent,
  NarrativeLoadingFixture,
  type NarrativeLoadingFixtureState,
} from "./E2ERegressionClient";

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

export default async function E2ERegressionPage({ searchParams }: E2ERegressionPageProps) {
  const resolvedSearchParams = await searchParams;
  const narrativeLoadingFixtureState = resolveNarrativeLoadingFixtureState(
    resolvedSearchParams.narrativeLoading,
  );

  if (narrativeLoadingFixtureState) {
    return <NarrativeLoadingFixture initialState={narrativeLoadingFixtureState} />;
  }

  return <E2ERegressionPageContent />;
}
