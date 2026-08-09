# Design

The test persists a unique owner and game in the configured database, publishes
events through the router's public cache helper, and reads the actual authenticated
SSE endpoint with `once=true`. It avoids image providers and browser automation,
while still exercising JWT authentication, ownership lookup, serialization, cache
key replacement, and replay filtering together.
