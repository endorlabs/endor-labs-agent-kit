# endorctl Setup

The Endor Labs Package Risk Summary artifact uses read-only Endor lookups through `endorctl api`.
Install and authenticate `endorctl` before using this artifact.

Required version: `>=1.0`

The recipe documents these read-only API invocation groups:

- `lookup_package_version_uuid`
- `get_package_scores`
- `get_package_license`
- `query_similar_packages`

The only allowed `endorctl api create` call is the documented
QuerySimilarPackages query-service lookup; every other v0 command must
be a read-only list/get/query operation.

If `endorctl` is missing,
unauthenticated, or lacks access to a resource, the agent must record the
affected signal in `data_gaps` and continue with the evidence it already
gathered.
