from app.schemas.risk_management import RiskEventCreate, RiskEventUpdate


def test_risk_event_create_accepts_chemical_id():
    data = RiskEventCreate(
        object_id="o1", accident_type="火灾",
        chemical_id="c1",
    )
    assert data.chemical_id == "c1"


def test_risk_event_update_accepts_chemical_id():
    data = RiskEventUpdate(chemical_id="c2")
    assert data.chemical_id == "c2"


def test_risk_event_model_has_chemical_id_column():
    from app.models.risk_management import RiskEvent
    cols = {c.name for c in RiskEvent.__table__.columns}
    assert "chemical_id" in cols
