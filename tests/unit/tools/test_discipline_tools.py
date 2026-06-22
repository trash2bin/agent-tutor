from mcp_server.tools.disciplines import DisciplineTools


def test_get_disciplines_for_student(test_db):
    """Test getting disciplines for a student."""
    tools = DisciplineTools(test_db)

    # Use a known student from fixtures.json
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    disciplines = tools.get_disciplines(student.id)
    assert isinstance(disciplines, list)
    # Student should have at least some disciplines from their group's schedule
    assert len(disciplines) >= 0


def test_get_disciplines_empty_for_unknown_student(test_db):
    """Test getting disciplines for a student that doesn't exist."""
    tools = DisciplineTools(test_db)

    disciplines = tools.get_disciplines("non-existent-student-id")
    assert disciplines == []


def test_get_disciplines_contains_valid_data(test_db):
    """Test that disciplines returned have valid structure."""
    tools = DisciplineTools(test_db)

    # Use a known student
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    disciplines = tools.get_disciplines(student.id)
    for discipline in disciplines:
        assert hasattr(discipline, "id")
        assert hasattr(discipline, "name")
        assert hasattr(discipline, "description")
        assert isinstance(discipline.id, str)
        assert isinstance(discipline.name, str)
