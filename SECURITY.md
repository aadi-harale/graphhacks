# Local synthetic demo only

The demonstration contains fictional merchants, products, promises and documents. It does not contain real payment or tax information.

The supplier-response route simulates a supplier; it does NOT authenticate suppliers. Review is simulated on behalf of a retailer. Both mutation routes are protected only by local environment flags, not user login. **Do not deploy this service publicly or use it for real disputes.**

Port mappings in Docker Compose use 127.0.0.1. No external messaging or payments exist.

Production requirements before any real pilot: tenant identity and authorization, true supplier/retailer authentication, evidence upload hardening, event provenance, deduplication, atomic idempotent allocation, retention and deletion policy, auditability, and consent.

Never claim simulation or quantity matching proves physical delivery or monetary recovery.
