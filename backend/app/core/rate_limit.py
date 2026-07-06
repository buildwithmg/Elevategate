"""
In-memory rate limiting (slowapi) keyed by client IP address.

MVP scope: this is per-process, in-memory state. It does not share counters across multiple
backend replicas — behind a load balancer with N instances, the effective limit is N times the
configured value. A production multi-instance deployment would back this with Redis instead
(slowapi supports it as a drop-in storage backend). Documented here and in
docs/BACKEND_THREAT_MODEL.md rather than left as a silent gap.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
