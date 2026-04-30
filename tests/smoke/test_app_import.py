def test_fastapi_app_imports():
    from app.api.main import app

    route_paths = {route.path for route in app.routes}

    assert "/health" in route_paths
    assert "/api/v1/lessons/generate" in route_paths
