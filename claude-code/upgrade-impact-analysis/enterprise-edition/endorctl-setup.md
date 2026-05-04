# endorctl Setup

The Enterprise Edition Endor Labs Upgrade Impact Analysis uses read-only Endor lookups
through `endorctl api` for package scores, license classification, and
similar-package signals. Install and authenticate `endorctl` before
using the Enterprise Edition artifact.

Required version: `>=1.0`

The recipe documents these read-only API invocation groups:

- `lookup_current_package_version_uuid`
- `lookup_target_package_version_uuid`
- `get_current_package_scores`
- `get_target_package_scores`
- `get_target_package_license`
- `query_similar_packages`

The only allowed `endorctl api create` call is the documented
QuerySimilarPackages query-service lookup; every other v0 command must
be a read-only list/get/query operation. If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.
