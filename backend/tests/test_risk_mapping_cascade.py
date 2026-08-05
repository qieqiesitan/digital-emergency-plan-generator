from app.services.enterprise_cleanup_service import delete_enterprise_complete, delete_enterprise_risk_mapping


def test_cleanup_service_imports():
    assert callable(delete_enterprise_risk_mapping)
    assert callable(delete_enterprise_complete)
