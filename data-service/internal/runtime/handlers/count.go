package handlers

import (
	"fmt"
	"net/http"
	"strconv"
	"strings"
)

// CountHandler обрабатывает GET /entity/count?status=new&...
// Возвращает количество записей, соответствующих фильтрам.
//
// Пример: GET /orders/count?status=new → {"count": 42}
//
// Используй вместо find_*, когда нужно узнать КОЛИЧЕСТВО записей,
// а не сами данные — это быстрее и дешевле по токенам.
func CountHandler(c *Context, entityName string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		entity, ok := c.Resolver.Resolve(entityName)
		if !ok {
			RespondError(w, http.StatusInternalServerError, "config_error", "entity not found")
			return
		}

		translate := asPlaceholderFunc(c.Adapter)

		// Собираем все непустые query-параметры как фильтры
		var filterCols []string
		var filterVals []any
		var filterOps []string

		for _, f := range entity.Fields {
			if f.PrimaryKey {
				continue
			}
			val := r.URL.Query().Get(f.Name)
			if val == "" {
				continue
			}

			filterCols = append(filterCols, f.Name)

			switch f.Type {
			case "int":
				if intVal, err := strconv.ParseInt(val, 10, 64); err == nil {
					filterVals = append(filterVals, intVal)
					filterOps = append(filterOps, "eq")
				} else {
					RespondError(w, http.StatusBadRequest, "validation_error",
						fmt.Sprintf("param %q: expected integer, got %q", f.Name, val))
					return
				}
			case "float":
				if floatVal, err := strconv.ParseFloat(val, 64); err == nil {
					filterVals = append(filterVals, floatVal)
					filterOps = append(filterOps, "eq")
				} else {
					RespondError(w, http.StatusBadRequest, "validation_error",
						fmt.Sprintf("param %q: expected number, got %q", f.Name, val))
					return
				}
			default:
				filterVals = append(filterVals, val)
				filterOps = append(filterOps, "like")
			}
		}

		// Строим SELECT COUNT(*) вместо SELECT ...
		var countSQL string
		var args []any

		if len(filterCols) == 0 {
			countSQL = fmt.Sprintf("SELECT COUNT(*) FROM %s", c.Adapter.QuoteIdentifier(entity.Table))
		} else {
			// Используем BuildFilter чтобы получить WHERE-условия,
			// но заменяем SELECT ... на SELECT COUNT(*)
			query, err := c.Builder.BuildFilter(entity, filterCols, filterVals, filterOps)
			if err != nil {
				RespondError(w, http.StatusInternalServerError, "query_error", err.Error())
				return
			}
			// Заменяем "SELECT ... FROM" на "SELECT COUNT(*) FROM"
			upper := strings.ToUpper(query.SQL)
			fromIdx := strings.Index(upper, " FROM ")
			if fromIdx > 0 {
				countSQL = "SELECT COUNT(*)" + query.SQL[fromIdx:]
			} else {
				countSQL = "SELECT COUNT(*) FROM " + c.Adapter.QuoteIdentifier(entity.Table)
			}
			args = query.Args
		}

		// Добавляем tenant-фильтр
		tenantWhere, tenantArgs := tenantFilter(entityName, c.Auth, c.tenantID(r), len(args), translate)
		if tenantWhere != "" {
			if strings.Contains(strings.ToUpper(countSQL), " WHERE ") {
				countSQL += " AND " + tenantWhere
			} else {
				countSQL += " WHERE " + tenantWhere
			}
			args = append(args, tenantArgs...)
		}

		// Выполняем COUNT запрос
		rows, err := c.DB.QueryContext(r.Context(), countSQL, args...)
		if err != nil {
			RespondError(w, http.StatusInternalServerError, "db_error", err.Error())
			return
		}
		defer rows.Close() //nolint:errcheck

		var count int
		if rows.Next() {
			if err := rows.Scan(&count); err != nil {
			RespondError(w, http.StatusInternalServerError, "scan_error",
				fmt.Sprintf("failed to scan count for %q: %v", entityName, err))
			return
		}
		}

		RespondJSON(w, http.StatusOK, map[string]any{
			"entity": entityName,
			"count":  count,
		})
	}
}
