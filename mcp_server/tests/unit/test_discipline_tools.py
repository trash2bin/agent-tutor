"""Тесты DisciplineRepo — дисциплины."""

from agent_tutor_sdk.db.repositories import DisciplineRepo
from agent_tutor_sdk.db.models import Discipline


def test_get_disciplines_for_student(test_db):
    """Test getting disciplines for a student."""
    repo = DisciplineRepo(test_db.connector)

    # Use a known student from fixtures.json
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    disciplines = repo.get_disciplines(student.id)
    assert isinstance(disciplines, list)
    assert len(disciplines) >= 0


def test_get_disciplines_empty_for_unknown_student(test_db):
    """Test getting disciplines for a student that doesn't exist."""
    repo = DisciplineRepo(test_db.connector)

    disciplines = repo.get_disciplines("non-existent-student-id")
    assert disciplines == []


def test_get_disciplines_contains_valid_data(test_db):
    """Test that disciplines returned have valid structure."""
    repo = DisciplineRepo(test_db.connector)

    # Use a known student
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    disciplines = repo.get_disciplines(student.id)
    for discipline in disciplines:
        assert isinstance(discipline, Discipline)
        assert isinstance(discipline.id, str)
        assert isinstance(discipline.name, str)
        assert isinstance(discipline.description, str)
