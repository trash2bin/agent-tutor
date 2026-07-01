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
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/go-chi/chi/v5"

	"github.com/agent-tutor/agent-tutor-go/config"
	"github.com/agent-tutor/data-service/internal/configgen"
	"github.com/agent-tutor/data-service/internal/datasource"
	"github.com/agent-tutor/data-service/internal/runtime"
	"github.com/agent-tutor/data-service/internal/runtime/handlers"
)

// ── TenantInstance ──

// TenantInstance holds all state for one tenant: config, DB connection, and router.
type TenantInstance struct {
	ID         string                // tenant identifier (matches X-Tenant-ID header)
	Config     *config.Config        // loaded and validated
	Conn       datasource.Conn       // tenant's own DB connection pool
	Adapter    datasource.Adapter    // full adapter for admin/introspection
	AdapterSub runtime.AdapterSubset // Conn+Adapter wrapper for handlers
	Router     http.Handler          // built chi router for this tenant
	ConfigPath string                // path to the JSON config file (for hot reload)
	CreatedAt  time.Time

	Healthy   bool   // last health ping result
	LastError string // last error message if unhealthy
}

// ConnAdapter wraps datasource.Conn + datasource.Adapter into runtime.AdapterSubset.
// Extracted from main.go to be reusable by TenantStore.
type ConnAdapter struct {
	Conn datasource.Conn
	Adp  datasource.Adapter
}

func (c *ConnAdapter) QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error) {
	return c.Conn.QueryContext(ctx, query, args...)
}
func (c *ConnAdapter) PingContext(ctx context.Context) error  { return c.Conn.PingContext(ctx) }
func (c *ConnAdapter) QuoteIdentifier(name string) string      { return c.Adp.QuoteIdentifier(name) }
func (c *ConnAdapter) TranslatePlaceholder(index int) string   { return c.Adp.TranslatePlaceholder(index) }

// ── TenantStore ──

// TenantStore manages multiple TenantInstances with RWMutex and
// implements http.Handler — routing by X-Tenant-ID from context.
type TenantStore struct {
	mu      sync.RWMutex
	tenants map[string]*TenantInstance

	registry *datasource.Registry // all registered datasource.Adapter drivers

	defaultID   string       // fallback tenant when X-Tenant-ID is empty
	adminRouter http.Handler // chi sub-router for /admin/* (built once)
}

// NewTenantStore creates an empty TenantStore with the given registry.
func NewTenantStore(registry *datasource.Registry) *TenantStore {
	return &TenantStore{
		tenants:  make(map[string]*TenantInstance),
		registry: registry,
	}
}

// SetDefault bootstraps the default tenant. Must be called before ServeHTTP.
// Returns error if a default is already set with a different ID.
func (ts *TenantStore) SetDefault(ctx context.Context, id string, cfg *config.Config, configPath string) error {
	if ts.defaultID != "" && ts.defaultID != id {
		return fmt.Errorf("default tenant already set to %q, cannot change to %q", ts.defaultID, id)
	}

	inst, err := buildTenantInstance(ctx, ts, ts.registry, id, cfg, configPath)
	if err != nil {
		return fmt.Errorf("set default tenant %q: %w", id, err)
	}

	ts.mu.Lock()
	ts.tenants[id] = inst
	ts.defaultID = id
	ts.mu.Unlock()

	slog.Info("tenant store: default tenant set",
		"id", id,
		"driver", cfg.DataSource.Driver,
		"entities", len(cfg.Entities),
		"endpoints", len(cfg.Endpoints),
	)
	return nil
}

// ── Tenant Lifecycle ──

// AddTenant creates a new TenantInstance: validates config, connects DB,
// builds router, and stores it atomically.
func (ts *TenantStore) AddTenant(ctx context.Context, id string, cfg *config.Config, configPath string) (*TenantInstance, error) {
	ts.mu.RLock()
	_, exists := ts.tenants[id]
	ts.mu.RUnlock()
	if exists {
		return nil, fmt.Errorf("tenant %q already exists", id)
	}

	inst, err := buildTenantInstance(ctx, ts, ts.registry, id, cfg, configPath)
	if err != nil {
		return nil, fmt.Errorf("add tenant %q: %w", id, err)
	}

	ts.mu.Lock()
	// Double-check after acquiring write lock
	if _, exists := ts.tenants[id]; exists {
		ts.mu.Unlock()
		// Clean up the connection we just opened
		inst.Conn.Close()
		return nil, fmt.Errorf("tenant %q already exists", id)
	}
	ts.tenants[id] = inst
	ts.mu.Unlock()

	slog.Info("tenant store: tenant added",
		"id", id,
		"driver", cfg.DataSource.Driver,
		"entities", len(cfg.Entities),
		"endpoints", len(cfg.Endpoints),
	)
	return inst, nil
}

// RemoveTenant removes a tenant and closes its connection pool.
// The default tenant cannot be removed.
func (ts *TenantStore) RemoveTenant(ctx context.Context, id string) error {
	if id == ts.defaultID {
		return fmt.Errorf("cannot remove default tenant %q", id)
	}

	ts.mu.Lock()
	inst, ok := ts.tenants[id]
	if !ok {
		ts.mu.Unlock()
		return fmt.Errorf("tenant %q not found", id)
	}
	delete(ts.tenants, id)
	ts.mu.Unlock()

	// Close connection outside the lock to avoid blocking readers
	if inst.Conn != nil {
		if err := inst.Conn.Close(); err != nil {
			slog.Warn("tenant store: error closing connection", "id", id, "error", err)
		}
	}

	slog.Info("tenant store: tenant removed", "id", id)
	return nil
}

// GetTenant returns the TenantInstance for the given id, or (nil, false).
func (ts *TenantStore) GetTenant(id string) (*TenantInstance, bool) {
	ts.mu.RLock()
	inst, ok := ts.tenants[id]
	ts.mu.RUnlock()
	return inst, ok
}

// ListTenants returns a snapshot of all tenants, sorted by creation time.
func (ts *TenantStore) ListTenants() []*TenantInstance {
	ts.mu.RLock()
	result := make([]*TenantInstance, 0, len(ts.tenants))
	for _, inst := range ts.tenants {
		result = append(result, inst)
	}
	ts.mu.RUnlock()

	sort.Slice(result, func(i, j int) bool {
		return result[i].CreatedAt.Before(result[j].CreatedAt)
	})
	return result
}

// ReloadTenant reloads the config for a specific tenant from disk and rebuilds its router.
func (ts *TenantStore) ReloadTenant(ctx context.Context, tenantID string, configPath string) error {
	newCfg, err := config.Load(configPath)
	if err != nil {
		return fmt.Errorf("reload tenant %q: load config: %w", tenantID, err)
	}

	ts.mu.RLock()
	inst, ok := ts.tenants[tenantID]
	ts.mu.RUnlock()
	if !ok {
		return fmt.Errorf("reload tenant %q: not found", tenantID)
	}

	// Build new router using existing connection
	newRouter, err := NewRouterFromConfig(ts, newCfg, inst.AdapterSub, inst.AdapterSub, inst.Adapter, configPath, nil)
	if err != nil {
		return fmt.Errorf("reload tenant %q: build router: %w", tenantID, err)
	}

	ts.mu.Lock()
	inst.Config = newCfg
	inst.Router = newRouter
	inst.ConfigPath = configPath
	ts.mu.Unlock()

	slog.Info("tenant store: config reloaded",
		"tenant", tenantID,
		"entities", len(newCfg.Entities),
		"endpoints", len(newCfg.Endpoints),
	)
	return nil
}

// ── http.Handler Implementation ──

// ServeHTTP implements http.Handler. Routing:
//
//	/admin/*     → adminRouter (tenant management + config)
//	/health      → multiTenantHealthHandler
//	all others   → extract tenantID from context → tenant's Router
func (ts *TenantStore) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path

	// Health endpoint
	if path == "/health" {
		ts.multiTenantHealthHandler(w, r)
		return
	}

	// Resolve tenant
	inst := ts.resolveTenant(r)
	if inst == nil {
		handlers.RespondError(w, http.StatusNotFound, "tenant_not_found",
			"no tenant configured — set up a default tenant first")
		return
	}

	inst.Router.ServeHTTP(w, r)
}

// resolveTenant extracts tenantID from request context or query parameter, and looks up the tenant.
// Falls back to defaultID if no X-Tenant-ID header and no 'tenant' query param.
func (ts *TenantStore) resolveTenant(r *http.Request) *TenantInstance {
	// 1. Try header from context (already populated by middleware)
	tenantID, _ := r.Context().Value(tenantIDKey).(string)

	// 2. Fallback to query parameter ?tenant=... (critical for Swagger UI / Browser)
	if tenantID == "" {
		tenantID = r.URL.Query().Get("tenant")
	}

	if tenantID == "" {
		tenantID = ts.defaultID
	}
	if tenantID == "" {
		return nil
	}

	ts.mu.RLock()
	inst := ts.tenants[tenantID]
	ts.mu.RUnlock()
	return inst
}

// ── Health ──

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

			pingCtx, cancel := context.WithTimeout(ctx, 2*time.Second)
			defer cancel()

			if err := ti.Conn.PingContext(pingCtx); err != nil {
				h.Status = "unhealthy"
				h.Error = err.Error()
			} else {
				h.Status = "healthy"
			}

			// Update instance health cache
			ti.Healthy = (h.Status == "healthy")
			if h.Error != "" {
				ti.LastError = h.Error
			}

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

// ── buildTenantInstance ──

// buildTenantInstance validates config, connects to DB, and builds a router.
// Used by both SetDefault and AddTenant.
func buildTenantInstance(ctx context.Context, ts *TenantStore, registry *datasource.Registry, id string, cfg *config.Config, configPath string) (*TenantInstance, error) {
	// Open DB connection
	adapter, ok := registry.Get(string(cfg.DataSource.Driver))
	if !ok {
		return nil, fmt.Errorf("unsupported driver: %s", cfg.DataSource.Driver)
	}

	dsn := cfg.DataSource.DSN
	if dsn != "" && !filepath.IsAbs(dsn) && configPath != "" {
		configDir := filepath.Dir(configPath)
		dsn = filepath.Join(configDir, dsn)
	}
	conn, err := adapter.Connect(ctx, dsn)
	if err != nil {
		return nil, fmt.Errorf("connect to database: %w", err)
	}

	adapterSub := &ConnAdapter{Conn: conn, Adp: adapter}

	// Build router (no admin endpoints — those are on TenantStore)
	router, err := NewRouterFromConfig(ts, cfg, adapterSub, adapterSub, adapter, configPath, nil)
	if err != nil {
		conn.Close() // clean up on failure
		return nil, fmt.Errorf("build router: %w", err)
	}

	return &TenantInstance{
		ID:         id,
		Config:     cfg,
		Conn:       conn,
		Adapter:    adapter,
		AdapterSub: adapterSub,
		Router:     router,
		ConfigPath: configPath,
		CreatedAt:  time.Now(),
		Healthy:    true,
	}, nil
}

// ── Admin Router ──

// BuildAdminRouter creates the chi sub-router for /admin/* endpoints.
func (ts *TenantStore) BuildAdminRouter(adapter datasource.Adapter, configPath string) http.Handler {
	r := chi.NewRouter()

	// All admin endpoints require ADMIN_TOKEN
	r.Use(AdminAuthMiddleware)

	// Tenant management
	r.Post("/tenants", ts.adminAddTenantHandler)
	r.Get("/tenants", ts.adminListTenantsHandler)
	r.Get("/tenants/{id}", ts.adminGetTenantHandler)
	r.Delete("/tenants/{id}", ts.adminRemoveTenantHandler)

	// Config management (operates on default tenant)
	r.Get("/config", ts.adminConfigDefaultHandler)
	r.Post("/config", ts.adminConfigUpdateDefaultHandler)
	r.Post("/config/reload", ts.adminConfigReloadDefaultHandler)
	r.Get("/config/versions", ts.adminConfigVersionsHandler)
	r.Post("/config/rewrite", ts.adminRewriteDefaultHandler(adapter, configPath))

	// Schema discovery (operates on default tenant)
	if adapter != nil {
		r.Get("/discover", ts.adminDiscoverDefaultHandler(adapter))
	}

	ts.adminRouter = r
	return r
}

// ── Admin Tenant Management Handlers ──

type addTenantRequest struct {
	ID         string          `json:"id"`
	Config     json.RawMessage `json:"config"`
	ConfigPath string          `json:"config_path,omitempty"`
}

type tenantResponse struct {
	ID        string `json:"id"`
	Driver    string `json:"driver"`
	Entities  int    `json:"entities"`
	Endpoints int    `json:"endpoints"`
	Healthy   bool   `json:"healthy"`
	Error     string `json:"error,omitempty"`
	CreatedAt string `json:"created_at"`
}

func tenantResponseFromInstance(inst *TenantInstance) tenantResponse {
	return tenantResponse{
		ID:        inst.ID,
		Driver:    string(inst.Config.DataSource.Driver),
		Entities:  len(inst.Config.Entities),
		Endpoints: len(inst.Config.Endpoints),
		Healthy:   inst.Healthy,
		Error:     inst.LastError,
		CreatedAt: inst.CreatedAt.UTC().Format(time.RFC3339),
	}
}

func (ts *TenantStore) adminAddTenantHandler(w http.ResponseWriter, r *http.Request) {
	var req addTenantRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "invalid_json",
			fmt.Sprintf("failed to parse body: %v", err))
		return
	}

	if req.ID == "" {
		handlers.RespondError(w, http.StatusBadRequest, "missing_id", "id is required")
		return
	}

	// Parse config (decode does basic type validation)
	var cfg config.Config
	if err := json.Unmarshal(req.Config, &cfg); err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "invalid_config",
			fmt.Sprintf("failed to decode config: %v", err))
		return
	}

	// Validate config against schema (skipped if schema file unavailable)
	if err := config.Validate(req.Config, ""); err != nil {
		slog.Warn("admin add tenant: schema validation skipped (schema file unavailable)", "error", err)
	}

	// Save config to disk if path provided
	configPath := req.ConfigPath
	if configPath != "" {
		prettyJSON, err := json.MarshalIndent(cfg, "", "  ")
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "marshal_error",
				fmt.Sprintf("failed to marshal config: %v", err))
			return
		}
		if err := os.WriteFile(configPath, prettyJSON, 0644); err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "write_error",
				fmt.Sprintf("failed to write config: %v", err))
			return
		}
	}

	// Add tenant
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	inst, err := ts.AddTenant(ctx, req.ID, &cfg, configPath)
	if err != nil {
		// Check if it's a duplicate
		if _, exists := ts.GetTenant(req.ID); exists {
			handlers.RespondError(w, http.StatusConflict, "duplicate", err.Error())
		} else {
			handlers.RespondError(w, http.StatusInternalServerError, "add_failed", err.Error())
		}
		return
	}

	handlers.RespondJSON(w, http.StatusCreated, map[string]any{
		"status": "created",
		"tenant": tenantResponseFromInstance(inst),
	})
}

func (ts *TenantStore) adminRemoveTenantHandler(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	if id == "" {
		handlers.RespondError(w, http.StatusBadRequest, "missing_id", "tenant id is required")
		return
	}

	if id == ts.defaultID {
		handlers.RespondError(w, http.StatusForbidden, "forbidden",
			"cannot remove the default tenant")
		return
	}

	ctx, cancel := context.WithTimeout(r.Context(), 10*time.Second)
	defer cancel()

	if err := ts.RemoveTenant(ctx, id); err != nil {
		handlers.RespondError(w, http.StatusNotFound, "not_found", err.Error())
		return
	}

	handlers.RespondJSON(w, http.StatusOK, map[string]string{
		"status": "removed",
		"id":     id,
	})
}

func (ts *TenantStore) adminListTenantsHandler(w http.ResponseWriter, r *http.Request) {
	instances := ts.ListTenants()
	resp := make([]tenantResponse, len(instances))
	for i, inst := range instances {
		resp[i] = tenantResponseFromInstance(inst)
	}
	handlers.RespondJSON(w, http.StatusOK, map[string]any{"tenants": resp})
}

func (ts *TenantStore) adminGetTenantHandler(w http.ResponseWriter, r *http.Request) {
	id := chi.URLParam(r, "id")
	inst, ok := ts.GetTenant(id)
	if !ok {
		handlers.RespondError(w, http.StatusNotFound, "not_found",
			fmt.Sprintf("tenant %q not found", id))
		return
	}
	handlers.RespondJSON(w, http.StatusOK, tenantResponseFromInstance(inst))
}

// ── Admin Config Handlers (operating on default tenant) ──

func (ts *TenantStore) adminConfigDefaultHandler(w http.ResponseWriter, r *http.Request) {
	inst, ok := ts.GetTenant(ts.defaultID)
	if !ok {
		handlers.RespondError(w, http.StatusInternalServerError, "no_default",
			"no default tenant configured")
		return
	}

	resp := adminConfigResponseFromConfig(inst.Config)
	handlers.RespondJSON(w, http.StatusOK, resp)
}

func (ts *TenantStore) adminConfigUpdateDefaultHandler(w http.ResponseWriter, r *http.Request) {
	inst, ok := ts.GetTenant(ts.defaultID)
	if !ok {
		handlers.RespondError(w, http.StatusInternalServerError, "no_default",
			"no default tenant configured")
		return
	}

	// Parse body
	var raw json.RawMessage
	if err := json.NewDecoder(r.Body).Decode(&raw); err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "invalid_json",
			fmt.Sprintf("failed to parse body: %v", err))
		return
	}

	var newCfg config.Config
	if err := json.Unmarshal(raw, &newCfg); err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "invalid_config",
			fmt.Sprintf("failed to unmarshal config: %v", err))
		return
	}

	// Validate
	if err := config.Validate(raw, ""); err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "validation_error",
			fmt.Sprintf("config validation failed: %v", err))
		return
	}

	// Dry-run build
	_, err := NewRouterFromConfig(ts, &newCfg, inst.AdapterSub, inst.AdapterSub, inst.Adapter, inst.ConfigPath, nil)
	if err != nil {
		handlers.RespondError(w, http.StatusBadRequest, "build_error",
			fmt.Sprintf("router build failed: %v", err))
		return
	}

	// Archive old config
	archiveCurrentConfig(inst.ConfigPath)

	// Save to disk
	prettyJSON, err := json.MarshalIndent(newCfg, "", "  ")
	if err != nil {
		handlers.RespondError(w, http.StatusInternalServerError, "marshal_error", err.Error())
		return
	}
	if err := os.WriteFile(inst.ConfigPath, prettyJSON, 0644); err != nil {
		handlers.RespondError(w, http.StatusInternalServerError, "write_error", err.Error())
		return
	}

	// Reload tenant
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	if err := ts.ReloadTenant(ctx, ts.defaultID, inst.ConfigPath); err != nil {
		handlers.RespondError(w, http.StatusInternalServerError, "reload_error",
			fmt.Sprintf("config saved but reload failed: %v", err))
		return
	}

	handlers.RespondJSON(w, http.StatusOK, map[string]any{
		"status":    "applied",
		"path":      inst.ConfigPath,
		"entities":  len(newCfg.Entities),
		"endpoints": len(newCfg.Endpoints),
	})
}

func (ts *TenantStore) adminConfigReloadDefaultHandler(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
	defer cancel()

	if err := ts.ReloadTenant(ctx, ts.defaultID, ""); err != nil {
		handlers.RespondError(w, http.StatusInternalServerError, "reload_error", err.Error())
		return
	}
	handlers.RespondJSON(w, http.StatusOK, map[string]string{
		"status": "reloaded",
	})
}

func (ts *TenantStore) adminConfigVersionsHandler(w http.ResponseWriter, r *http.Request) {
	inst, ok := ts.GetTenant(ts.defaultID)
	if !ok {
		handlers.RespondError(w, http.StatusInternalServerError, "no_default",
			"no default tenant configured")
		return
	}
	versionsDir := filepath.Join(filepath.Dir(inst.ConfigPath), "config_versions")
	entries, err := os.ReadDir(versionsDir)
	if err != nil {
		if os.IsNotExist(err) {
			handlers.RespondJSON(w, http.StatusOK, []string{})
			return
		}
		handlers.RespondError(w, http.StatusInternalServerError, "readdir_error", err.Error())
		return
	}

	type versionInfo struct {
		Name    string `json:"name"`
		Size    int64  `json:"size_bytes"`
		ModTime string `json:"mod_time"`
	}
	versions := make([]versionInfo, 0, len(entries))
	for _, e := range entries {
		if e.IsDir() || !strings.HasPrefix(e.Name(), "config.") {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		versions = append(versions, versionInfo{
			Name:    e.Name(),
			Size:    info.Size(),
			ModTime: info.ModTime().UTC().Format(time.RFC3339),
		})
	}
	sort.Slice(versions, func(i, j int) bool { return versions[i].Name > versions[j].Name })
	handlers.RespondJSON(w, http.StatusOK, versions)
}

func (ts *TenantStore) adminRewriteDefaultHandler(adapter datasource.Adapter, configPath string) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		inst, ok := ts.GetTenant(ts.defaultID)
		if !ok {
			handlers.RespondError(w, http.StatusInternalServerError, "no_default",
				"no default tenant configured")
			return
		}

		if adapter == nil {
			handlers.RespondError(w, http.StatusServiceUnavailable, "unavailable",
				"introspection adapter not available")
			return
		}

		conn, err := adapter.Connect(r.Context(), inst.Config.DataSource.DSN)
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "connect_error", err.Error())
			return
		}
		defer conn.Close()

		schema, err := adapter.Introspect(r.Context(), conn)
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "introspect_error", err.Error())
			return
		}

		dsConfig := config.DataSourceConfig{
			Driver: inst.Config.DataSource.Driver,
			DSN:    inst.Config.DataSource.DSN,
		}
		newCfg := configgen.Generate(schema, dsConfig, nil)

		data, err := json.MarshalIndent(newCfg, "", "  ")
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "marshal_error", err.Error())
			return
		}

		if err := os.WriteFile(configPath, data, 0644); err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "write_error", err.Error())
			return
		}

		// Reload
		ctx, cancel := context.WithTimeout(r.Context(), 30*time.Second)
		defer cancel()
		if err := ts.ReloadTenant(ctx, ts.defaultID, configPath); err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "reload_error",
				fmt.Sprintf("config saved but reload failed: %v", err))
			return
		}

		handlers.RespondJSON(w, http.StatusOK, map[string]any{
			"status":    "ok",
			"path":      configPath,
			"entities":  len(newCfg.Entities),
			"endpoints": len(newCfg.Endpoints),
			"note":      "Конфиг сохранён и применён без рестарта.",
		})
	}
}

func (ts *TenantStore) adminDiscoverDefaultHandler(adapter datasource.Adapter) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		inst, ok := ts.GetTenant(ts.defaultID)
		if !ok {
			handlers.RespondError(w, http.StatusInternalServerError, "no_default",
				"no default tenant configured")
			return
		}

		conn, err := adapter.Connect(r.Context(), inst.Config.DataSource.DSN)
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "connect_error", err.Error())
			return
		}
		defer conn.Close()

		schema, err := adapter.Introspect(r.Context(), conn)
		if err != nil {
			handlers.RespondError(w, http.StatusInternalServerError, "introspect_error", err.Error())
			return
		}

		dsConfig := config.DataSourceConfig{
			Driver: inst.Config.DataSource.Driver,
			DSN:    inst.Config.DataSource.DSN,
		}
		cfg := configgen.Generate(schema, dsConfig, nil)

		slog.Info("config generated via /admin/discover",
			"entities", len(cfg.Entities),
			"endpoints", len(cfg.Endpoints),
		)

		if r.URL.Query().Get("raw") == "true" {
			data, err := json.MarshalIndent(cfg, "", "  ")
			if err != nil {
				handlers.RespondError(w, http.StatusInternalServerError, "marshal_error", err.Error())
				return
			}
			w.Header().Set("Content-Type", "application/json")
			w.Write(data)
			return
		}

		handlers.RespondJSON(w, http.StatusOK, cfg)
	}
}

// adminConfigResponseFromConfig converts config.Config to admin-safe DTO.
func adminConfigResponseFromConfig(cfg *config.Config) adminConfigResponse {
	return adminConfigResponse{
		Version:       cfg.Version,
		Driver:        cfg.DataSource.Driver,
		Entities:      cfg.Entities,
		Endpoints:     cfg.Endpoints,
		CustomQueries: cfg.CustomQueries,
		Stats:         cfg.Stats,
		Auth:          cfg.Auth,
		MCPTools:      cfg.MCPTools,
		Introspection: cfg.Introspection,
	}
}
