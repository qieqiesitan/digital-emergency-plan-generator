from app.models.data_dict import DataDict

def test_data_dict_table_metadata():
    assert DataDict.__tablename__ == "data_dicts"
    cols = DataDict.__table__.columns
    assert "id" in cols and "dict_type" in cols and "code" in cols and "value" in cols
    assert cols["enterprise_id"].nullable
    assert any(getattr(c, "name", None) == "uq_data_dicts_type_ent_code"
               for c in DataDict.__table__.constraints)

def test_data_dict_model_construct():
    row = DataDict(dict_type="measure_factors", code="engineering", label="工程技术",
                   value={"factor": 0.5}, scope="system", is_system=True)
    assert row.value["factor"] == 0.5
    assert row.enabled is True
    assert DataDict(enabled=False).enabled is False
