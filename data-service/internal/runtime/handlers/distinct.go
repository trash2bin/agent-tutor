package handlers

import (
	"database/sql"
	"fmt"
	"net/http"
)

// DistinctHandler обрабатывает GET /entity/distinct?column=status.
// Возвращает уникальные значения указанной колонки (максимум 50).
// Используется агентами для определения допустимых значений enum-полей.
//
// Пример: GET /orders/distinct?column=status → ["new", "processing", "shipped"]
func DistinctHandler(c *Context, entityName string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		entity, ok := c.Resolver.Resolve(entityName)
		if !ok {
			RespondError(w, http.StatusInternalServerError, "config_error", "entity not found")
			return
		}

		column := r.URL.Query().Get("column")
		if column == "" {
			RespondError(w, http.StatusBadRequest, "missing_param",
				"parameter 'column' is required")
			return
		}

		// Проверяем что колонка существует в entity
		var foundCol string
		for _, f := range entity.Fields {
			if f.Name == column || f.Column == column {
				foundCol = f.Column
				break
			}
		}
		if foundCol == "" {
			RespondError(w, http.StatusBadRequest, "invalid_column",
				fmt.Sprintf("column %q not found in entity %q", column, entityName))
			return
		}

		translate := asPlaceholderFunc(c.Adapter)

		// SELECT DISTINCT column FROM table WHERE column IS NOT NULL LIMIT 50
		query := fmt.Sprintf("SELECT DISTINCT %s FROM %s WHERE %s IS NOT NULL ORDER BY %s LIMIT 50",
			c.Adapter.QuoteIdentifier(foundCol),
			c.Adapter.QuoteIdentifier(entity.Table),
			c.Adapter.QuoteIdentifier(foundCol),
			c.Adapter.QuoteIdentifier(foundCol),
		)

		// Добавляем tenant-фильтр
		tenantWhere, tenantArgs := tenantFilter(entityName, c.Auth, c.tenantID(r), 0, translate)
		if tenantWhere != "" {
			query += " AND " + tenantWhere
		}

		rows, err := c.DB.QueryContext(r.Context(), query, tenantArgs...)
		if err != nil {
			RespondError(w, http.StatusInternalServerError, "db_error", err.Error())
			return
		}
		defer rows.Close() //nolint:errcheck

		var values []string
		for rows.Next() {
			var val sql.NullString
			if err := rows.Scan(&val); err != nil {
				continue
			}
			if val.Valid {
				values = append(values, val.String)
			}
		}
		if values == nil {
			values = []string{}
		}

		RespondJSON(w, http.StatusOK, map[string]any{
			"column":  column,
			"entity":  entityName,
			"values":  values,
			"count":   len(values),
			"truncated": len(values) >= 50,
		})
	}
}
