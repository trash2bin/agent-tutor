"""Тесты StudentRepo — студенты и расписание."""

from agent_tutor_sdk.db.repositories import StudentRepo


def test_get_student(test_db):
    """Test getting student information by valid ID."""
    repo = StudentRepo(test_db.connector)

    # Use a known student from fixtures.json
    student = repo.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    result = repo.get_student(student.id)
    assert result is not None
    assert result.name == "Валерия Константиновна Макарова"


def test_find_student_by_name(test_db):
    """Test finding student by name."""
    repo = StudentRepo(test_db.connector)

    result = repo.get_id_student("Валерия Константиновна Макарова")
    assert result is not None
    assert result.name == "Валерия Константиновна Макарова"


def test_get_schedule(test_db):
    """Test getting schedule for a group."""
    repo = StudentRepo(test_db.connector)

    # Need a valid group_id. Let's get it from the student
    student = repo.get_id_student("Валерия Константиновна Макарова")
    assert student is not None
    assert student.group is not None

    schedule = repo.get_schedule(student.group.id)
    assert isinstance(schedule, list)
    assert len(schedule) >= 0
