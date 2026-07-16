# Repository package

Repositories own database access. Router and service layers must not issue raw SQL or access SQLAlchemy models directly for aggregate queries.
