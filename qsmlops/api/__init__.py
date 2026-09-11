"""API routers: foundation endpoints (Part 1) and dashboard routes."""
from qsmlops.api.app import create_app, register_dashboard_routes
from qsmlops.api.foundation import register_foundation_routes

__all__ = ["create_app", "register_dashboard_routes", "register_foundation_routes"]
