from uuid import uuid4

from app.api.routers.parent import _guardian_id


def test_guardian_id_comes_from_token_subject():
    guardian_id = uuid4()

    assert _guardian_id({"sub": str(guardian_id), "role": "guardian"}) == guardian_id
