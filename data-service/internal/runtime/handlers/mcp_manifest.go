package handlers

import (
	"net/http"

	"github.com/agent-tutor/agent-tutor-go/config"
)

// MCPManifestHandler возвращает манифест MCP-инструментов,
// сформированный из конфига data-service — единственный source of truth.
//
// mcp-gateway вызывает этот эндпоинт при старте вместо того,
// чтобы парсить config.json самостоятельно.
func MCPManifestHandler(cfg *config.Config) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		RespondJSON(w, http.StatusOK, map[string]any{
			"endpoints":      cfg.Endpoints,
			"entities":       cfg.Entities,
			"custom_queries": cfg.CustomQueries,
			"mcp_tools":      cfg.MCPTools,
		})
	}
}
