package handlers

import (
	"testing"
)

func TestCountQuery(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  string
	}{
		{
			name:  "simple select",
			input: `SELECT "id", "name" FROM "students"`,
			want:  `SELECT COUNT(*) FROM "students"`,
		},
		{
			name:  "with where",
			input: `SELECT "id", "name" FROM "students" WHERE "course" = ?`,
			want:  `SELECT COUNT(*) FROM "students" WHERE "course" = ?`,
		},
		{
			name:  "with multiple conditions",
			input: `SELECT "id" FROM "students" WHERE "course" = ? AND "group_id" = ?`,
			want:  `SELECT COUNT(*) FROM "students" WHERE "course" = ? AND "group_id" = ?`,
		},
		{
			name:  "with limit",
			input: `SELECT "id" FROM "students" LIMIT 10 OFFSET 0`,
			want:  `SELECT COUNT(*) FROM "students"`,
		},
		{
			name:  "no FROM",
			input: `SELECT 1`,
			want:  "",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := countQuery(tt.input)
			if got != tt.want {
				t.Errorf("countQuery(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestAppendPagination(t *testing.T) {
	tests := []struct {
		name   string
		sql    string
		limit  int
		offset int
		want   string
	}{
		{
			name:   "basic",
			sql:    `SELECT * FROM "students"`,
			limit:  10,
			offset: 0,
			want:   `SELECT * FROM "students" LIMIT 10 OFFSET 0`,
		},
		{
			name:   "with offset",
			sql:    `SELECT * FROM "students"`,
			limit:  20,
			offset: 40,
			want:   `SELECT * FROM "students" LIMIT 20 OFFSET 40`,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := appendPagination(tt.sql, tt.limit, tt.offset)
			if got != tt.want {
				t.Errorf("appendPagination(%q, %d, %d) = %q, want %q",
					tt.sql, tt.limit, tt.offset, got, tt.want)
			}
		})
	}
}
