package handlers

import (
	"context"
	"fmt"
	"net/http"
	"strconv"
	"strings"

	"github.com/trash2bin/helperium/data-service/internal/runtime"
)

const (
	defaultLimit = 100
	maxLimit     = 1000
)

// readPagination извлекает limit и offset из query params.
func readPagination(r *http.Request) (limit, offset int) {
	limit = defaultLimit
	offset = 0

	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
			if limit > maxLimit {
				limit = maxLimit
			}
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}
	return limit, offset
}

// appendPagination добавляет LIMIT и OFFSET к SQL запросу.
func appendPagination(sql string, limit, offset int) string {
	sql += fmt.Sprintf(" LIMIT %d OFFSET %d", limit, offset)
	return sql
}

// countQuery заменяет SELECT ... FROM на SELECT COUNT(*) FROM, сохраняя WHERE.
// Удаляет LIMIT/OFFSET если есть — COUNT не нуждается в пагинации.
func countQuery(selectSQL string) string {
	upper := strings.ToUpper(selectSQL)
	idx := strings.Index(upper, " FROM ")
	if idx < 0 {
		return ""
	}
	result := "SELECT COUNT(*)" + selectSQL[idx:]
	// Удаляем LIMIT ... OFFSET ...
	limIdx := strings.LastIndex(strings.ToUpper(result), " LIMIT ")
	if limIdx > 0 {
		result = strings.TrimSpace(result[:limIdx])
	}
	return result
}

// runCountQuery выполняет COUNT запрос и возвращает общее число записей.
func runCountQuery(ctx context.Context, db runtime.AdapterSubset, countSQL string, args []any) int {
	rows, err := db.QueryContext(ctx, countSQL, args...)
	if err != nil {
		return -1
	}
	defer rows.Close() //nolint:errcheck
	var total int
	if rows.Next() {
		_ = rows.Scan(&total)
	}
	return total
}

// setPaginationHeaders устанавливает заголовки пагинации в ответе.
func setPaginationHeaders(w http.ResponseWriter, total int, limit, offset int) {
	if total >= 0 {
		w.Header().Set("X-Total-Count", strconv.Itoa(total))
	}
	w.Header().Set("X-Limit", strconv.Itoa(limit))
	w.Header().Set("X-Offset", strconv.Itoa(offset))
}
