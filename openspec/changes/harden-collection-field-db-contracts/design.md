# Design

The test persists two users, two games, and image records through the configured
database. It calls the real `CollectionService` with a real `PlayerState`, avoiding
network providers while exercising SQL filters, response schema conversion, image
version choice, and ownership checks.
