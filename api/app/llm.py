"""Back-compat shim.

This module used to own the Azure OpenAI wrapper. That lives in
`providers/` now. The shim stays so external imports keep
working; prefer `from .providers import get_provider` in new
code.
"""

from .providers import get_provider

__all__ = ["get_provider"]
