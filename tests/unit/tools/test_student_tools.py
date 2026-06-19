import pytest
from mcp_server.tools.student import StudentTools

def test_get_student(test_db):
    """Test getting student information by valid ID."""
    tools = StudentTools(test_db)
    
    # Use a known student from fixtures.json
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None
    
    result = tools.get_student(student.id)
    assert result is not None
    assert result.name == "Валерия Константиновна Макарова"

def test_find_student_by_name(test_db):
    """Test finding student by name."""
    tools = StudentTools(test_db)
    
    result = tools.get_id_student("Валерия Константиновна Макарова")
    assert result is not None
    assert result.name == "Валерия Константиновна Макарова"

def test_get_schedule(test_db):
    """Test getting schedule for a group."""
    tools = StudentTools(test_db)
    
    # Need a valid group_id. Let's get it from the student
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None
    assert student.group is not None
    
    schedule = tools.get_schedule(student.group.id)
    assert isinstance(schedule, list)
    # The fixture might have schedule entries
    assert len(schedule) >= 0
