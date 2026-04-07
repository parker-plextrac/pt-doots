# Integration Architecture Snapshot

> **Last updated**: 2026-03-30
> **WARNING**: This is a point-in-time snapshot. The Research step in the skill MUST re-read the actual files to detect any drift from this snapshot.

## File Map

### Core Types
- `libs/common/src/integration-worker/api-integration/data/types.ts`
  - `ApiIntegrationKindEnum` — all integration kinds
  - `ApiIntegrationSettings` — shared settings shape (`apiUrl?`, `apiKey?`, `providerTenantId?`, `region?`)
  - `ApiIntegrationSecrets` — shared secrets shape (`apiSecret?`)
  - `ApiIntegrationSentinel` — sync state (`offset?`, `lastScannedTimestamp?`, `lastSeenTime?`)

### Synqly Provider Configs
- `libs/common/src/integration-worker/api-integration/synqly/types.ts`
  - `SynqlyProviderConfig` union type
  - Per-integration config types (e.g. `QualysProviderConfig`, `Rapid7ProviderConfig`)

### Plugin Files (per integration)
- `plugins/{name}/types.ts` — Zod schemas (`settingsSchema`, `secretsSchema`)
- `plugins/{name}/util.ts` — `{Name}PluginUtil` class with static `parseSettings` and `parseSecrets`

### Factory
- `plugins/factory.ts` — `ApiIntegrationPluginFactory`
  - `createPlugin()` switch-case routes by `ApiIntegrationKindEnum`
  - `build{Name}Plugin()` methods construct the actual plugin
  - Synqly integrations return `SynqlyVulnerabilityPlugin` or `SynqlyAppSecPlugin`
  - Stub integrations return `DevelopmentApiIntegrationPlugin`

### Registration Points
- `libs/common/src/integration-worker/constants.ts` — `IntegrationLicenseMap`, `IntegrationFeatureFlagMap`
- `apps/plextracapi/src/domains/rbac/constants/license.ts` — license constants
- `apps/plextracapi/src/domains/featureFlags/module/features.ts` — feature flags
- `apps/integration-worker/src/modules/metrics.ts` — `KIND_DISPLAY_NAMES` for Grafana

### Tests
- `plugins/factory.test.ts` — factory wiring tests (Mocha + Chai + moq.ts)
- Run with: `NODE_ENV=development LOG_LEVEL=error npx mocha --config .mocharc.apps-libs.js '{path}'`

## Auth Patterns

| Pattern | Credential Type | Settings Fields | Secrets Fields | Example |
|---------|----------------|-----------------|----------------|---------|
| Token | `{ type: 'token', secret }` | `apiUrl` | `apiSecret` | Rapid7, Tenable |
| Basic | `{ type: 'basic', username, secret }` | `apiUrl`, `apiKey` | `apiSecret` | Qualys |
| Token + Org | `{ type: 'token', secret }` | `providerTenantId`, `region` | `apiSecret` | Snyk |
| OAuth | Custom SDK | `apiUrl`, `providerTenantId`, `apiKey` | `apiSecret` | Defender |

## Synqly Provider Types (known)

| Integration | Provider Type String |
|-------------|---------------------|
| Qualys | `vulnerabilities_qualys_cloud` |
| Tenable TVM | `vulnerabilities_tenable_cloud` |
| Snyk | `appsec_snyk` |
| Rapid7 | `vulnerabilities_rapid7_insight_cloud` |

Check https://docs.synqly.com/api-reference/management/integrations/integrations_list.md for new provider types.

## Stub Integrations (as of 2026-03-30)

These have enum entries but use `DevelopmentApiIntegrationPlugin`:
- CrowdStrike
- Horizon3
- Wiz
