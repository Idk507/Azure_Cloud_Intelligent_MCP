"""Local compatibility shim for azure namespace in restricted environments.

Extending the namespace lets optional Azure SDK packages (such as
``azure-ai-projects``) coexist with the lightweight test shims in this repo.
"""
from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
