## Context

`ImageGenerator` builds MiniMax requests, makes HTTP calls, downloads returned image URLs, and maps provider failures to typed application errors. Existing pure contracts cover helper methods; existing broader provider tests mutate environment state, so they cannot enter the maintained gate. A stdlib HTTP server can exercise the real requests session solely on `127.0.0.1`.

## Goals / Non-Goals

**Goals:**

- Cover text generation, image editing, image download, and typed provider-response handling through the public generator methods.
- Use explicit configuration and loopback transport only, without mocks, environment mutation, external network, or credentials.
- Keep both maintained workflow selections identical.

**Non-Goals:**

- Contact MiniMax or any public endpoint.
- Test retry timing, production credentials, or browser UI behavior.
- Change production image-generation behavior.

## Decisions

- Use an in-process `ThreadingHTTPServer` rather than a mock session so the request serialization, `requests` transport, response parsing, and binary download paths run together.
- Use a unique fixed prompt per test and one retry to avoid cache collisions and sleeps.
- Assert request path, authorization header, and exact provider payload fields, then assert typed failures at the public API boundary.

## Risks / Trade-offs

- [Loopback server can leak a thread] -> Close the server and join its thread in a context manager.
- [Global image cache can hide a request] -> Use distinct constant prompts and assert captured request count.
- [A local HTTP test is slower than pure helper tests] -> Keep the suite to four focused scenarios and avoid external I/O.
