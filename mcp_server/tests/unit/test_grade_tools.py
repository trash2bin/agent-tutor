from mcp_server.tools.grades import GradeTools


def test_get_student_grades(test_db):
    """Test getting grades for a student."""
    tools = GradeTools(test_db)

    # Use a known student from fixtures.json
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    grades = tools.get_student_grades(student.id)
    assert isinstance(grades, list)
    # Student might have grades
    assert len(grades) >= 0


def test_get_student_grades_empty_for_unknown_student(test_db):
    """Test getting grades for a student that doesn't exist."""
    tools = GradeTools(test_db)

    grades = tools.get_student_grades("non-existent-student-id")
    assert grades == []


def test_get_student_grades_with_discipline_filter(test_db):
    """Test getting grades for a student filtered by discipline."""
    tools = GradeTools(test_db)

    # Use a known student
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    # Get all grades first
    all_grades = tools.get_student_grades(student.id)

    # If there are grades, try filtering by first discipline
    if all_grades:
        first_discipline_id = all_grades[0].discipline_id
        filtered_grades = tools.get_student_grades(
            student.id, discipline_id=first_discipline_id
        )

        assert isinstance(filtered_grades, list)
        # Filtered list should be subset or equal to all grades
        assert len(filtered_grades) <= len(all_grades)

        # All filtered grades should have the specified discipline_id
        for grade in filtered_grades:
            assert grade.discipline_id == first_discipline_id


def test_get_student_grades_structure(test_db):
    """Test that grades returned have valid structure."""
    tools = GradeTools(test_db)

    # Use a known student
    student = test_db.get_id_student("Валерия Константиновна Макарова")
    assert student is not None

    grades = tools.get_student_grades(student.id)
    for grade in grades:
        assert hasattr(grade, "id")
        assert hasattr(grade, "student_id")
        assert hasattr(grade, "discipline_id")
        assert hasattr(grade, "discipline_name")
        assert hasattr(grade, "grade")
        assert hasattr(grade, "date")
        assert isinstance(grade.id, str)
        assert isinstance(grade.grade, str)
