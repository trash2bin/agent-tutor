// Package server — multi-tenant support (фаза 3.7).
//
// TenantStore manages N configurations, N database connections, and N routers
// per process. Implements http.Handler — routing by X-Tenant-ID from context.
//
// Architecture:
//
//	                   ┌─ tenant-a → config_a → pg_a → router_a
//	X-Tenant-ID: a ────┤
//	                   ├─ tenant-b → config_b → pg_b → router_b
//	X-Tenant-ID: b ────┤
//	                   └─ default (no header)
//
// Lifecycle:
//   - SetDefault bootstraps the fallback tenant (no X-Tenant-ID → default)
//   - AddTenant adds new tenants at runtime via admin API
//   - RemoveTenant closes connections and removes from map
//   - ReloadTenant rebuilds router for a tenant from updated config
package server

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"github.com/trash2bin/helperium/helperium-go/config"
	"github.com/trash2bin/helperium/data-service/internal/datasource"
	"github.com/trash2bin/helperium/data-service/internal/runtime"
	"github.com/trash2bin/helperium/data-service/internal/runtime/handlers"
)

// ── TenantInstance ──

// TenantInstance holds all state for one tenant: config, DB connection, and router.
type TenantInstance struct {
	ID         string                // tenant identifier (matches X-Tenant-ID header)
	Config     *config.Config        // loaded and validated
	Conn       datasource.Conn       // tenant's main DB connection pool (readwrite DSN)
	ReadonlyConn datasource.Conn     // tenant's read-only DB connection (when readonly_dsn is set; nil otherwise)
	Adapter    datasource.Adapter    // full adapter for admin/introspection
	AdapterSub runtime.AdapterSubset // Conn+Adapter wrapper for handlers — wraps ReadonlyConn if set, else Conn
	Router     http.Handler          // built chi router for this tenant
	ConfigPath string                // path to the JSON config file (for hot reload)
	CreatedAt  time.Time

	// healthMu guards Healthy and LastError — health check goroutines write,
	// admin handlers read. Both must acquire healthMu.Lock() before access.
	// Pointer to prevent data races when TenantInstance is inadvertently copied.
	healthMu           *sync.Mutex
	Healthy            bool                 // (guarded by healthMu) last health ping result
	LastError          string               // (guarded by healthMu) last error message if unhealthy
	ApprovedTools      map[string]bool      // approved write endpoints (key = path, set on load from cfg.ApprovedTools)
	IntrospectedSchema *datasource.Schema   // cached result of last Introspect (set by /admin/config/rewrite)
}

// ── TenantStore ──

// TenantStore manages multiple TenantInstances with RWMutex and
// implements http.Handler — routing by X-Tenant-ID from context.
type TenantStore struct {
	mu      sync.RWMutex
	tenants map[string]*TenantInstance

	registry *datasource.Registry // all registered datasource.Adapter drivers

	adminRouter http.Handler // chi sub-router for /admin/* (built once)
	hasAdmin    bool         // true when introspect adapter is available (for /openapi.json)

	TenantsDir string // directory for persisting tenant configs (.data/tenants/)
}

// NewTenantStore creates an empty TenantStore with the given registry.
func NewTenantStore(registry *datasource.Registry, tenantsDir string) *TenantStore {
	return &TenantStore{
		tenants:    make(map[string]*TenantInstance),
		registry:   registry,
		TenantsDir: tenantsDir,
	}
}

// ── Config Persistence ──

// TenantConfigPath returns the filesystem path for persisting this tenant's config.
// Uses TenantsDir/{id}.json. Creates the directory if needed.
func (ts *TenantStore) TenantConfigPath(id string) string {
	if ts.TenantsDir == "" {
		return ""
	}
	return filepath.Join(ts.TenantsDir, id+".json")
}

// SaveTenantConfig persists the tenant config to disk and returns the config path.
// Returns empty string if TenantsDir is not configured.
func (ts *TenantStore) SaveTenantConfig(id string, cfg *config.Config) string {
	if ts.TenantsDir == "" {
		return ""
	}
	if err := os.MkdirAll(ts.TenantsDir, 0755); err != nil {
		slog.Warn("save config: failed to create tenants directory", "tenant", id, "error", err)
		return ""
	}
	persistPath := filepath.Join(ts.TenantsDir, id+".json")
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		slog.Warn("save config: marshal error", "tenant", id, "error", err)
		return ""
	}
	if err := os.WriteFile(persistPath, data, 0644); err != nil {
		slog.Warn("save config: write error", "tenant", id, "path", persistPath, "error", err)
		return ""
	}
	slog.Info("save config: persisted", "tenant", id, "path", persistPath)
	return persistPath
}

// DeleteTenantConfig removes the persisted config file for a tenant.
func (ts *TenantStore) DeleteTenantConfig(id string) {
	if ts.TenantsDir == "" {
		return
	}
	configPath := filepath.Join(ts.TenantsDir, id+".json")
	if err := os.Remove(configPath); err != nil && !os.IsNotExist(err) {
		slog.Warn("delete config: remove error", "tenant", id, "error", err)
	}
}

// ── http.Handler Implementation ──

// ServeHTTP implements http.Handler. Routing:
//
//	/admin/*     → adminRouter (tenant management + config)
//	/health      → multiTenantHealthHandler
//	all others   → extract tenantID from context → tenant's Router
func (ts *TenantStore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path

	// System endpoints (no tenant required)
	switch path {
	case "/health":
		ts.multiTenantHealthHandler(w, r)
		return
	case "/docs":
		SwaggerHandler(w, r)
		return
	case "/openapi.json":
		NewOpenAPIHandler(ts, ts.hasAdmin)(w, r)
		return
	}

	// Resolve tenant
	inst := ts.resolveTenant(r)
	if inst == nil {
		handlers.RespondError(w, http.StatusNotFound, "tenant_not_found",
			"no tenant identifier provided — please use X-Tenant-ID header or ?tenant= query parameter")
		return
	}

	inst.Router.ServeHTTP(w, r)
}

// resolveTenant extracts tenantID from request context or query parameter, and looks up the tenant.
// Handles comma-separated X-Tenant-ID (e.g. "shop,default" from composite sessions)
// by using the first tenant in the list.
func (ts *TenantStore) resolveTenant(r *http.Request) *TenantInstance {
	// 1. Try context (populated by TenantIDMiddleware when present)
	tenantID, _ := r.Context().Value(tenantIDKey).(string)

	// 2. Fallback: direct header read (for tests / when middleware not applied)
	if tenantID == "" {
		tenantID = r.Header.Get("X-Tenant-ID")
	}

	// 3. Fallback to query parameter ?tenant=... (critical for Swagger UI / Browser)
	if tenantID == "" {
		tenantID = r.URL.Query().Get("tenant")
	}

	// Handle comma-separated tenant IDs (e.g. "shop,default" from composite MCP sessions)
	// Use the first tenant only for routing to data-service
	if tenantID != "" && strings.Contains(tenantID, ",") {
		parts := strings.Split(tenantID, ",")
		tenantID = strings.TrimSpace(parts[0])
	}

	ts.mu.RLock()
	inst := ts.tenants[tenantID]
	ts.mu.RUnlock()
	return inst
}
