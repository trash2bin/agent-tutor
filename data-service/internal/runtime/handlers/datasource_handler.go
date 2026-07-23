package handlers

import (
	"log/slog"
	"net/http"

	"github.com/trash2bin/helperium/data-service/internal/datasource"
)

// DataSourceHandler — универсальный HTTP handler для DataSource-based инструментов.
//
// Принимает datasource.DataSource и маршрутизирует по методу.
// Поддерживает: schema, search, filter.
// В будущем — get_by_id, count, distinct.
type DataSourceHandler struct {
	ds     datasource.DataSource
	entity string
	method string // "schema", "search", "filter"
}

// NewDataSourceHandler создаёт DataSourceHandler.
func NewDataSourceHandler(ds datasource.DataSource, entity, method string) *DataSourceHandler {
	return &DataSourceHandler{ds: ds, entity: entity, method: method}
}

func (h *DataSourceHandler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	switch h.method {
	case "schema":
		info, err := h.ds.Schema(r.Context(), h.entity)
		if err != nil {
			slog.Error("DataSource schema error", "err", err, "entity", h.entity)
			RespondError(w, http.StatusInternalServerError, "query_failed", "Schema query failed.")
			return
		}
		RespondJSON(w, http.StatusOK, info)

	case "search":
		result, err := h.ds.Search(r.Context(), &datasource.Query{Entity: h.entity})
		if err != nil {
			slog.Error("DataSource search error", "err", err, "entity", h.entity)
			RespondError(w, http.StatusInternalServerError, "query_failed", "Search query failed.")
			return
		}
		RespondJSON(w, http.StatusOK, result)

	case "filter":
		result, err := h.ds.Filter(r.Context(), &datasource.Query{Entity: h.entity})
		if err != nil {
			slog.Error("DataSource filter error", "err", err, "entity", h.entity)
			RespondError(w, http.StatusInternalServerError, "query_failed", "Filter query failed.")
			return
		}
		RespondJSON(w, http.StatusOK, result)

	default:
		RespondError(w, http.StatusNotImplemented, "not_implemented", "Method not supported yet")
	}
}
