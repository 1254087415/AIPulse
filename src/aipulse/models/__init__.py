"""SQLAlchemy models for v0.3 follow + learning domain."""

# Import the submodules so that Base.metadata is populated whenever any caller
# imports ``aipulse.models`` (which is the convention for Alembic autogenerate
# and ``Base.metadata.create_all``).
from aipulse.models import followed_up  # noqa: F401
from aipulse.models import followed_up_collections  # noqa: F401
from aipulse.models import learning_events  # noqa: F401

