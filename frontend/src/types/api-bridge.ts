/**
 * API Type Bridge — Re-exports auto-generated OpenAPI types as friendly names.
 *
 * This file maps the auto-generated types from `api-generated.d.ts` to the
 * names used throughout the frontend codebase.  Hand-written types in
 * `src/lib/types.ts` can be gradually replaced by importing from here instead.
 *
 * Regenerate the source types with:
 *   npm run export:openapi && npm run generate:api-types
 */

import type { components } from './api-generated';

// ─── Convenience alias ───────────────────────────────────────────────
type Schemas = components['schemas'];

// ─── Auth ────────────────────────────────────────────────────────────
export type ApiAuthResponse = Schemas['AuthResponse'];
export type ApiUserInfo = Schemas['UserInfo'];
export type ApiLoginRequest = Schemas['LoginRequest'];
export type ApiRegisterRequest = Schemas['RegisterRequest'];

// ─── Games ───────────────────────────────────────────────────────────
export type ApiGameListItem = Schemas['GameListItem'];
export type ApiGameStateResponse = Schemas['GameStateResponse'];
export type ApiCreateGameRequest = Schemas['CreateGameRequest'];
export type ApiSaveGameResponse = Schemas['SaveGameResponse'];

// ─── Presets ─────────────────────────────────────────────────────────
export type ApiPresetInfo = Schemas['PresetInfo'];
export type ApiCreatePresetRequest = Schemas['CreatePresetRequest'];

// ─── Gameplay / Story ────────────────────────────────────────────────
export type ApiMakeChoiceRequest = Schemas['MakeChoiceRequest'];
export type ApiCustomChoiceRequest = Schemas['CustomChoiceRequest'];
export type ApiOpeningStoryRequest = Schemas['OpeningStoryRequest'];
export type ApiRewriteStoryRequest = Schemas['RewriteStoryRequest'];
export type ApiRegenerateStoryRequest = Schemas['RegenerateStoryRequest'];
export type ApiStoryChatRequest = Schemas['StoryChatRequest'];
export type ApiStoryChatResponse = Schemas['StoryChatResponse'];

// ─── Images ──────────────────────────────────────────────────────────
export type ApiImageResponse = Schemas['ImageResponse'];
export type ApiImageListResponse = Schemas['ImageListResponse'];
export type ApiOpeningIllustrationResponse = Schemas['OpeningIllustrationResponse'];
export type ApiRoundSceneResponse = Schemas['RoundSceneResponse'];
export type ApiGenerateImageRequest = Schemas['GenerateImageRequest'];
export type ApiGenerateOpeningIllustrationRequest = Schemas['GenerateOpeningIllustrationRequest'];
export type ApiGenerateRoundSceneRequest = Schemas['GenerateRoundSceneRequest'];

// ─── Collection ──────────────────────────────────────────────────────
export type ApiCollectionResponse = Schemas['CollectionResponse'];
export type ApiCharacterCollectionItem = Schemas['CharacterCollectionItem'];
export type ApiItemCollectionItem = Schemas['ItemCollectionItem'];
export type ApiLandmarkCollectionItem = Schemas['LandmarkCollectionItem'];

// ─── Music ───────────────────────────────────────────────────────────
export type ApiMusicRecommendationRequest = Schemas['MusicRecommendationRequest'];
export type ApiMusicRecommendationResponse = Schemas['MusicRecommendationResponse'];
export type ApiSongResponse = Schemas['SongResponse'];

// ─── Save Points ─────────────────────────────────────────────────────
export type ApiSavePointItem = Schemas['SavePointItem'];
export type ApiSavePointListResponse = Schemas['SavePointListResponse'];
export type ApiStateSnapshotItem = Schemas['StateSnapshotItem'];
export type ApiStateTimelineResponse = Schemas['StateTimelineResponse'];

// ─── Character Generation ────────────────────────────────────────────
export type ApiBatchGenerateCharactersRequest = Schemas['BatchGenerateCharactersRequest'];
export type ApiGenerateAttributesRequest = Schemas['GenerateAttributesRequest'];
export type ApiGenerateRelationshipRequest = Schemas['GenerateRelationshipRequest'];
export type ApiGenerateSettingRequest = Schemas['GenerateSettingRequest'];
export type ApiGenerateSummaryRequest = Schemas['GenerateSummaryRequest'];
export type ApiRelationshipsSummaryRequest = Schemas['RelationshipsSummaryRequest'];

// ─── Misc ────────────────────────────────────────────────────────────
export type ApiMessageResponse = Schemas['MessageResponse'];
export type ApiHTTPValidationError = Schemas['HTTPValidationError'];
export type ApiValidationError = Schemas['ValidationError'];
export type ApiClientLogEntry = Schemas['ClientLogEntry'];
