# SplitMate backend

## Authentication token storage

Login and refresh responses contain a short-lived JWT access token and an opaque refresh token. The client receives both raw values; the access token is valid for 15 minutes and the refresh token for seven days by default (`REFRESH_TOKEN_EXPIRE_DAYS`).

PostgreSQL stores refresh-token records in `refresh_tokens`, never the raw refresh token. Each record contains the user ID, SHA-256 token hash, creation time, expiry time, and optional revocation time. Hashing means a database disclosure cannot be used directly as a bearer credential, while the high-entropy random token can still be located deterministically when a client presents it.

On refresh, the presented token hash is looked up, and the record must be unrevoked, unexpired, and associated with an existing user. The old record is revoked and a newly generated seven-day token is stored and returned with a new access token. Logout revokes the matching record; repeated logout calls are safe and do not restore token usability.
