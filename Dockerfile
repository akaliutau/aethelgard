# Use the Alpine version of Redis 7.2 to match Aethelgard's requirements
FROM redis:7.2-alpine

# Enable Append-Only File (AOF) for durable queue persistence
CMD ["redis-server", "--appendonly", "yes"]