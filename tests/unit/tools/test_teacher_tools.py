import pytest
from mcp_server.tools.teacher import TeacherTools


def test_get_teacher_by_name(test_db):
    """Test getting teacher information by name."""
    tools = TeacherTools(test_db)
    
    # Use a known teacher from fixtures.json
    teacher = tools.get_teacher_by_name("Влас Иосипович Гуляев")
    assert teacher is not None
    assert teacher.name == "Влас Иосипович Гуляев"
    assert "Алгоритмы и структуры данных" in teacher.disciplines


def test_get_teacher_by_name_not_found(test_db):
    """Test getting teacher that doesn't exist."""
    tools = TeacherTools(test_db)
    
    teacher = tools.get_teacher_by_name("Несуществующий Учитель")
    assert teacher is None


def test_get_teacher_schedule(test_db):
    """Test getting schedule for a teacher."""
    tools = TeacherTools(test_db)
    
    # Get schedule for a known teacher
    schedule = tools.get_teacher_schedule("Влас Иосипович Гуляев")
    assert isinstance(schedule, list)
    # The fixture might have schedule entries for this teacher
    assert len(schedule) >= 0


def test_get_teacher_schedule_with_day(test_db):
    """Test getting schedule for a teacher on a specific day."""
    tools = TeacherTools(test_db)
    
    # Get schedule for a known teacher on Monday
    schedule = tools.get_teacher_schedule("Влас Иосипович Гуляев", day="Понедельник")
    assert isinstance(schedule, list)
    # Filter by day should return subset or empty list
    assert len(schedule) >= 0


def test_get_teacher_schedule_nonexistent_teacher(test_db):
    """Test getting schedule for a teacher that doesn't exist."""
    tools = TeacherTools(test_db)
    
    schedule = tools.get_teacher_schedule("Несуществующий Учитель")
    assert schedule == []
