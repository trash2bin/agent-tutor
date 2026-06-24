"""Тесты TeacherRepo — преподаватели и расписание."""

from agent_tutor_sdk.db.repositories import TeacherRepo


def test_get_teacher_by_name(test_db):
    """Test getting teacher information by name."""
    repo = TeacherRepo(test_db.connector)

    # Use a known teacher from fixtures.json
    teacher = repo.get_teacher_by_name("Влас Иосипович Гуляев")
    assert teacher is not None
    assert teacher.name == "Влас Иосипович Гуляев"
    assert "Алгоритмы и структуры данных" in teacher.disciplines


def test_get_teacher_by_name_not_found(test_db):
    """Test getting teacher that doesn't exist."""
    repo = TeacherRepo(test_db.connector)

    teacher = repo.get_teacher_by_name("Несуществующий Учитель")
    assert teacher is None


def test_get_teacher_schedule(test_db):
    """Test getting schedule for a teacher."""
    repo = TeacherRepo(test_db.connector)

    # Get schedule for a known teacher
    schedule = repo.get_teacher_schedule("Влас Иосипович Гуляев")
    assert isinstance(schedule, list)
    assert len(schedule) >= 0


def test_get_teacher_schedule_with_day(test_db):
    """Test getting schedule for a teacher on a specific day."""
    repo = TeacherRepo(test_db.connector)

    schedule = repo.get_teacher_schedule("Влас Иосипович Гуляев", day="Понедельник")
    assert isinstance(schedule, list)
    assert len(schedule) >= 0


def test_get_teacher_schedule_nonexistent_teacher(test_db):
    """Test getting schedule for a teacher that doesn't exist."""
    repo = TeacherRepo(test_db.connector)

    schedule = repo.get_teacher_schedule("Несуществующий Учитель")
    assert schedule == []
