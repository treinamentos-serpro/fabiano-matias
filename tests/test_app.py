from copy import deepcopy

import pytest
from fastapi.testclient import TestClient


def test_root_redirects_to_frontend(client: TestClient):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_get_activities(client: TestClient, activity_data):
    response = client.get("/activities")

    assert response.status_code == 200
    assert response.json() == activity_data
    assert response.json()["Soccer Team"]["participants"] == []


def test_signup_adds_participant_once(client: TestClient, activity_data):
    expected = deepcopy(activity_data)
    email = "new.student@mergington.edu"
    expected["Chess Club"]["participants"].append(email)

    response = client.post(
        "/activities/Chess Club/signup", params={"email": email}
    )

    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for Chess Club"}
    assert client.get("/activities").json() == expected


def test_duplicate_signup_leaves_data_unchanged(client: TestClient, activity_data):
    expected = deepcopy(activity_data)

    response = client.post(
        "/activities/Chess Club/signup",
        params={"email": "michael@mergington.edu"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Student is already signed up for this activity"
    }
    assert client.get("/activities").json() == expected


def test_signup_for_unknown_activity(client: TestClient, activity_data):
    expected = deepcopy(activity_data)

    response = client.post(
        "/activities/Unknown Club/signup",
        params={"email": "new.student@mergington.edu"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Activity not found"}
    assert client.get("/activities").json() == expected


def test_unregister_preserves_other_participants(client: TestClient, activity_data):
    expected = deepcopy(activity_data)
    email = "michael@mergington.edu"
    expected["Chess Club"]["participants"].remove(email)

    response = client.delete(
        "/activities/Chess Club/participants", params={"email": email}
    )

    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert client.get("/activities").json() == expected


@pytest.mark.parametrize(
    ("activity", "email", "detail"),
    [
        ("Unknown Club", "michael@mergington.edu", "Activity not found"),
        (
            "Chess Club",
            "not.registered@mergington.edu",
            "Student is not signed up for this activity",
        ),
        (
            "Soccer Team",
            "not.registered@mergington.edu",
            "Student is not signed up for this activity",
        ),
    ],
)
def test_unregister_errors_leave_data_unchanged(
    client: TestClient, activity_data, activity: str, email: str, detail: str
):
    expected = deepcopy(activity_data)

    response = client.delete(
        f"/activities/{activity}/participants", params={"email": email}
    )

    assert response.status_code == 404
    assert response.json() == {"detail": detail}
    assert client.get("/activities").json() == expected


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/activities/Chess Club/signup"),
        ("DELETE", "/activities/Chess Club/participants"),
    ],
)
def test_email_is_required(
    client: TestClient, activity_data, method: str, path: str
):
    expected = deepcopy(activity_data)

    response = client.request(method, path)

    assert response.status_code == 422
    assert any(
        error["loc"] == ["query", "email"] and error["type"] == "missing"
        for error in response.json()["detail"]
    )
    assert client.get("/activities").json() == expected


def test_unregister_removes_legacy_duplicates(client: TestClient, activity_data):
    email = "michael@mergington.edu"
    activity_data["Chess Club"]["participants"].extend([email, email])
    expected = deepcopy(activity_data)
    expected["Chess Club"]["participants"] = ["daniel@mergington.edu"]

    response = client.delete(
        "/activities/Chess Club/participants", params={"email": email}
    )

    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from Chess Club"}
    assert client.get("/activities").json() == expected


def test_signup_and_unregister_round_trip(client: TestClient, activity_data):
    original = deepcopy(activity_data)
    expected = deepcopy(original)
    email = "round.trip@mergington.edu"
    expected["Soccer Team"]["participants"].append(email)

    signup = client.post(
        "/activities/Soccer Team/signup", params={"email": email}
    )

    assert signup.status_code == 200
    assert client.get("/activities").json() == expected

    removal = client.delete(
        "/activities/Soccer Team/participants", params={"email": email}
    )

    assert removal.status_code == 200
    assert client.get("/activities").json() == original
