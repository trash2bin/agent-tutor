// ── Health ──

package server

import (
	"context"
	"net/http"
	"sort"
	"sync"
	"time"

	"github.com/trash2bin/helperium/data-service/internal/runtime/handlers"
)

// TenantHealth is the DTO for per-tenant health status.
type TenantHealth struct {
	ID       string `json:"id"`
	Driver   string `json:"driver"`
	Status   string `json:"status"`
	Error    string `json:"error,omitempty"`
	Entities int    `json:"entities"`
}

// HealthCheck pings all tenant databases and returns aggregated status.
func (ts *TenantStore) HealthCheck(ctx context.Context) []TenantHealth {
	instances := ts.ListTenants()

	results := make([]TenantHealth, len(instances))

	var wg sync.WaitGroup
	for i, inst := range instances {
		wg.Add(1)
		go func(idx int, ti *TenantInstance) {
			defer wg.Done()

			h := TenantHealth{
				ID:       ti.ID,
				Driver:   string(ti.Config.DataSource.Driver),
				Entities: len(ti.Config.Entities),
			}

			// Health from Ping, or assume healthy if no Conn (e.g. test instances)
			if ti.Conn != nil {
				pingCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
				defer cancel()

				if err := ti.Conn.PingContext(pingCtx); err != nil {
					h.Status = "unhealthy"
					h.Error = err.Error()
				} else {
					h.Status = "healthy"
				}
			} else {
				h.Status = "healthy"
			}

			// Update instance health cache
			ti.healthMu.Lock()
			ti.Healthy = (h.Status == "healthy")
			ti.LastError = h.Error
			ti.healthMu.Unlock()

			results[idx] = h
		}(i, inst)
	}

	wg.Wait()

	// Sort by ID for deterministic output
	sort.Slice(results, func(i, j int) bool {
		return results[i].ID < results[j].ID
	})
	return results
}

// multiTenantHealthHandler serves GET /health with per-tenant status.
func (ts *TenantStore) multiTenantHealthHandler(w http.ResponseWriter, r *http.Request) {
	health := ts.HealthCheck(r.Context())

	// Backward-compatible single-tenant response
	if len(health) == 1 && health[0].Status == "healthy" {
		handlers.RespondJSON(w, http.StatusOK, map[string]string{"status": "ok"})
		return
	}

	// Multi-tenant / degraded response
	overall := computeOverallStatus(health)
	statusCode := http.StatusOK
	if overall == "unhealthy" {
		statusCode = http.StatusServiceUnavailable
	}

	handlers.RespondJSON(w, statusCode, map[string]any{
		"status":  overall,
		"tenants": health,
	})
}

func computeOverallStatus(health []TenantHealth) string {
	if len(health) == 0 {
		return "unhealthy"
	}
	allHealthy := true
	anyHealthy := false
	for _, h := range health {
		if h.Status == "healthy" {
			anyHealthy = true
		} else {
			allHealthy = false
		}
	}
	if allHealthy {
		return "healthy"
	}
	if anyHealthy {
		return "degraded"
	}
	return "unhealthy"
}
