package server

import (
	"context"
	"database/sql"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"sort"
	"strings"
	"testing"
	"time"

	_ "modernc.org/sqlite"

	"github.com/agent-tutor/agent-tutor-go/config"
	"github.com/agent-tutor/data-service/internal/datasource"
)

// ── Helpers ──

func newTestRegistry(t *testing.T) *datasource.Registry {
	t.Helper()
	return datasource.NewDefaultRegistry()
}

func newInMemoryConfig(t *testing.T) *config.Config {
	t.Helper()

	// Use file-based SQLite — :memory: creates separate databases per connection.
	// adapter.Connect() and this helper must see the same DB.
	tmpDir := t.TempDir()
	dbPath := tmpDir + "/test.db"

	// Create schema directly
	db, err := sql.Open("sqlite", dbPath+"?_journal_mode=WAL&_foreign_keys=on")
	if err != nil {
		t.Fatalf("open test db: %v", err)
	}
	db.SetMaxOpenConns(1)
	if _, err := db.ExecContext(t.Context(),
		"CREATE TABLE groups (id TEXT PRIMARY KEY, name TEXT);"+
			"CREATE TABLE courses (id TEXT PRIMARY KEY, name TEXT);"); err != nil {
		db.Close()
		t.Fatalf("create schema: %v", err)
	}
	db.Close()

	return &config.Config{
		Version: 1,
		DataSource: config.DataSourceConfig{
			Driver: config.DriverSQLite,
			DSN:    dbPath,
		},
		Entities: []config.Entity{
			{Name: "group", Table: "groups", IDColumn: "id", Fields: []config.EntityField{
				{Name: "id", Column: "id", Type: config.FieldTypeString},
				{Name: "name", Column: "name", Type: config.FieldTypeString},
			}},
		},
		Endpoints: []config.Endpoint{
			{Method: "GET", Path: "/health", Op: config.OpBuiltinHealth},
			{Method: "GET", Path: "/groups", Op: config.OpList, Entity: "group"},
			{Method: "GET", Path: "/groups/{id}", Op: config.OpGetByID, Entity: "group"},
		},
	}
}

func newTestTenantStore(t *testing.T) *TenantStore {
	t.Helper()
	registry := newTestRegistry(t)
	return NewTenantStore(registry)
}

func addDefaultTenant(t *testing.T, ts *TenantStore) {
	t.Helper()
	cfg := newInMemoryConfig(t)
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()
	if err := ts.SetDefault(ctx, "default", cfg, ""); err != nil {
		t.Fatalf("SetDefault: %v", err)
	}
}

// ── TenantStore Construction ──

func TestTenantStore_NewEmpty(t *testing.T) {
	ts := newTestTenantStore(t)
	if len(ts.ListTenants()) != 0 {
		t.Error("expected zero tenants")
	}
	if ts.defaultID != "" {
		t.Error("defaultID should be empty")
	}
}

// ── SetDefault ──

func TestTenantStore_SetDefault(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	inst, ok := ts.GetTenant("default")
	if !ok {
		t.Fatal("default tenant not found")
	}
	if inst.ID != "default" {
		t.Errorf("id = %q, want default", inst.ID)
	}
	if inst.Router == nil {
		t.Error("router is nil")
	}
	if inst.Conn == nil {
		t.Error("conn is nil")
	}
}

func TestTenantStore_SetDefault_DuplicateCall_Panics(t *testing.T) {
	ts := newTestTenantStore(t)

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	cfg1 := newInMemoryConfig(t)
	if err := ts.SetDefault(ctx, "default", cfg1, ""); err != nil {
		t.Fatalf("first SetDefault: %v", err)
	}

	cfg2 := newInMemoryConfig(t)
	err := ts.SetDefault(ctx, "other", cfg2, "")
	if err == nil {
		t.Error("expected error on second SetDefault with different ID")
	}
}

func TestTenantStore_SetDefault_SameOK(t *testing.T) {
	ts := newTestTenantStore(t)
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	cfg := newInMemoryConfig(t)
	if err := ts.SetDefault(ctx, "default", cfg, ""); err != nil {
		t.Fatalf("first SetDefault: %v", err)
	}
	// Same ID with new config (replace) — should work
	cfg2 := newInMemoryConfig(t)
	cfg2.Entities = append(cfg2.Entities, config.Entity{Name: "student", Table: "students", IDColumn: "id", Fields: []config.EntityField{
		{Name: "id", Column: "id", Type: config.FieldTypeString},
	}})
	if err := ts.SetDefault(ctx, "default", cfg2, ""); err != nil {
		t.Fatalf("second SetDefault with same ID: %v", err)
	}
}

// ── AddTenant / RemoveTenant ──

func TestTenantStore_AddTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	cfg := newInMemoryConfig(t)
	cfg.Entities = []config.Entity{
		{Name: "course", Table: "courses", IDColumn: "id", Fields: []config.EntityField{
			{Name: "id", Column: "id", Type: config.FieldTypeString},
		}},
	}

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	inst, err := ts.AddTenant(ctx, "tenant-b", cfg, "")
	if err != nil {
		t.Fatalf("AddTenant: %v", err)
	}
	if inst.ID != "tenant-b" {
		t.Errorf("id = %q", inst.ID)
	}

	// Verify it appears in list
	all := ts.ListTenants()
	if len(all) != 2 {
		t.Fatalf("expected 2 tenants, got %d", len(all))
	}

	// Verify GetTenant
	if _, ok := ts.GetTenant("tenant-b"); !ok {
		t.Error("tenant-b not found via GetTenant")
	}
}

func TestTenantStore_AddTenant_DuplicateID(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	cfg := newInMemoryConfig(t)
	_, err := ts.AddTenant(ctx, "default", cfg, "")
	if err == nil {
		t.Error("expected error on duplicate tenant")
	}
}

func TestTenantStore_RemoveTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	cfg := newInMemoryConfig(t)
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	if _, err := ts.AddTenant(ctx, "tenant-b", cfg, ""); err != nil {
		t.Fatalf("AddTenant: %v", err)
	}
	cancel()

	ctx2, cancel2 := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel2()
	if err := ts.RemoveTenant(ctx2, "tenant-b"); err != nil {
		t.Fatalf("RemoveTenant: %v", err)
	}

	if _, ok := ts.GetTenant("tenant-b"); ok {
		t.Error("tenant-b should be removed")
	}
	if len(ts.ListTenants()) != 1 {
		t.Error("expected 1 tenant after removal")
	}
}

func TestTenantStore_RemoveDefaultTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	err := ts.RemoveTenant(ctx, "default")
	if err == nil {
		t.Error("expected error when removing default tenant")
	}
}

func TestTenantStore_RemoveTenant_NotFound(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()

	err := ts.RemoveTenant(ctx, "nonexistent")
	if err == nil {
		t.Error("expected error")
	}
}

// ── ListTenants ordering ──

func TestTenantStore_ListTenants_SortedByCreatedAt(t *testing.T) {
	ts := newTestTenantStore(t)
	ctx, cancel := context.WithTimeout(t.Context(), 10*time.Second)
	defer cancel()

	cfg1 := newInMemoryConfig(t)
	if err := ts.SetDefault(ctx, "default", cfg1, ""); err != nil {
		t.Fatal(err)
	}

	// Small sleep to ensure distinct timestamps
	time.Sleep(10 * time.Millisecond)

	cfg2 := newInMemoryConfig(t)
	if _, err := ts.AddTenant(ctx, "b", cfg2, ""); err != nil {
		t.Fatal(err)
	}

	time.Sleep(10 * time.Millisecond)

	cfg3 := newInMemoryConfig(t)
	if _, err := ts.AddTenant(ctx, "c", cfg3, ""); err != nil {
		t.Fatal(err)
	}

	all := ts.ListTenants()
	if len(all) != 3 {
		t.Fatalf("expected 3 tenants, got %d", len(all))
	}

	// Check sorted by creation time (ascending)
	for i := 1; i < len(all); i++ {
		if all[i].CreatedAt.Before(all[i-1].CreatedAt) {
			t.Errorf("tenants not sorted: %s before %s",
				all[i-1].ID, all[i].ID)
		}
	}
}

// ── HealthCheck ──

func TestTenantStore_HealthCheck(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	health := ts.HealthCheck(t.Context())
	if len(health) != 1 {
		t.Fatalf("expected 1 health entry, got %d", len(health))
	}
	if health[0].Status != "healthy" {
		t.Errorf("expected healthy, got %s: %s", health[0].Status, health[0].Error)
	}
	if health[0].Driver != "sqlite" {
		t.Errorf("driver = %s", health[0].Driver)
	}
}

func TestTenantStore_HealthCheck_Empty(t *testing.T) {
	ts := newTestTenantStore(t)
	health := ts.HealthCheck(t.Context())
	if len(health) != 0 {
		t.Errorf("expected 0 entries, got %d", len(health))
	}
	overall := computeOverallStatus(health)
	if overall != "unhealthy" {
		t.Errorf("overall = %s, want unhealthy", overall)
	}
}

func TestTenantStore_HealthCheck_Degraded(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	// Add a tenant, then close its connection to simulate DB going away
	cfg := newInMemoryConfig(t)
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	inst, err := ts.AddTenant(ctx, "to-break", cfg, "")
	cancel()
	if err != nil {
		t.Fatalf("AddTenant: %v", err)
	}

	// Close connection to break health check
	inst.Conn.Close()

	health := ts.HealthCheck(t.Context())
	if len(health) != 2 {
		t.Fatalf("expected 2 entries, got %d", len(health))
	}

	// Sort for deterministic
	sort.Slice(health, func(i, j int) bool { return health[i].ID < health[j].ID })

	// "to-break" should now be unhealthy (connection closed)
	if health[1].Status != "unhealthy" {
		t.Errorf("to-break should be unhealthy after close, got %s: %s", health[1].Status, health[1].Error)
	}
	if health[0].Status != "healthy" {
		t.Errorf("default should be healthy, got %s", health[0].Status)
	}

	overall := computeOverallStatus(health)
	if overall != "degraded" {
		t.Errorf("overall = %s, want degraded", overall)
	}
}

// ── ServeHTTP: Routing ──

func TestTenantStore_ServeHTTP_RoutesToDefault(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	// Health endpoint (backward-compatible)
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	rec := httptest.NewRecorder()
	ts.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("health: expected 200, got %d: %s", rec.Code, rec.Body.String())
	}
	var hr map[string]string
	json.Unmarshal(rec.Body.Bytes(), &hr)
	if hr["status"] != "ok" {
		t.Errorf("health status = %s", hr["status"])
	}

	// Tenant-specific endpoint (no X-Tenant-ID → routes to default)
	req2 := httptest.NewRequest(http.MethodGet, "/groups", nil)
	rec2 := httptest.NewRecorder()
	ts.ServeHTTP(rec2, req2)

	if rec2.Code != http.StatusOK {
		t.Errorf("/groups: expected 200, got %d: %s", rec2.Code, rec2.Body.String())
	}
}

func TestTenantStore_ServeHTTP_RoutesToSpecificTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	// Create a separate DB for tenant-b with 'courses' table
	tmpDir := t.TempDir()
	dbPath := tmpDir + "/tenant_b.db"
	db, _ := sql.Open("sqlite", dbPath+"?_journal_mode=WAL&_foreign_keys=on")
	db.SetMaxOpenConns(1)
	db.ExecContext(t.Context(), "CREATE TABLE courses (id TEXT PRIMARY KEY, name TEXT)")
	db.Close()

	cfg := &config.Config{
		Version: 1,
		DataSource: config.DataSourceConfig{Driver: config.DriverSQLite, DSN: dbPath},
		Entities: []config.Entity{
			{Name: "course", Table: "courses", IDColumn: "id", Fields: []config.EntityField{
				{Name: "id", Column: "id", Type: config.FieldTypeString},
			}},
		},
		Endpoints: []config.Endpoint{
			{Method: "GET", Path: "/health", Op: config.OpBuiltinHealth},
			{Method: "GET", Path: "/courses", Op: config.OpList, Entity: "course"},
		},
	}

	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	defer cancel()
	if _, err := ts.AddTenant(ctx, "tenant-b", cfg, ""); err != nil {
		t.Fatalf("AddTenant: %v", err)
	}

	// Request with X-Tenant-ID: tenant-b
	req := httptest.NewRequest(http.MethodGet, "/courses", nil)
	req = req.WithContext(context.WithValue(req.Context(), tenantIDKey, "tenant-b"))

	rec := httptest.NewRecorder()
	ts.ServeHTTP(rec, req)

	if rec.Code != http.StatusOK {
		t.Errorf("expected 200 from tenant-b, got %d: %s", rec.Code, rec.Body.String())
	}
}

func TestTenantStore_ServeHTTP_TenantNotFound(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	req := httptest.NewRequest(http.MethodGet, "/groups", nil)
	req = req.WithContext(context.WithValue(req.Context(), tenantIDKey, "nonexistent"))

	rec := httptest.NewRecorder()
	ts.ServeHTTP(rec, req)

	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d", rec.Code)
	}
}

func TestTenantStore_ServeHTTP_AdminRoutesIgnored(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	req := httptest.NewRequest(http.MethodGet, "/admin/config", nil)
	rec := httptest.NewRecorder()
	ts.ServeHTTP(rec, req)

	// adminRouter is nil until BuildAdminRouter is called
	// So it returns 404 "admin not configured"
	if rec.Code != http.StatusNotFound {
		t.Errorf("expected 404 (admin not configured), got %d", rec.Code)
	}
}

// ── Admin Handler: Add Tenant ──

func TestAdminHandler_AddTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	os.Setenv("ADMIN_TOKEN", "test-token")
	defer os.Unsetenv("ADMIN_TOKEN")

	inst, _ := ts.GetTenant("default")
	ts.BuildAdminRouter(inst.Adapter, "/tmp/config.json")

	adminSrv := httptest.NewServer(ts.adminRouter)
	defer adminSrv.Close()

	cfg := newInMemoryConfig(t)
	cfgJSON, _ := json.Marshal(cfg)

	body := strings.NewReader(`{"id":"tenant-b","config":` + string(cfgJSON) + `}`)
	req, _ := http.NewRequest(http.MethodPost, adminSrv.URL+"/tenants", body)
	req.Header.Set("Authorization", "Bearer test-token")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusCreated {
		b, _ := io.ReadAll(resp.Body)
		t.Errorf("expected 201, got %d: %s", resp.StatusCode, string(b))
	}
	// Log for debugging
	if _, ok := ts.GetTenant("tenant-b"); !ok {
		all := ts.ListTenants()
		for _, inst := range all {
			t.Logf("existing tenant: %s", inst.ID)
		}
		t.Error("tenant-b not found after POST /admin/tenants")
	}
}

func TestAdminHandler_AddTenant_Duplicate(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	os.Setenv("ADMIN_TOKEN", "test-token")
	defer os.Unsetenv("ADMIN_TOKEN")

	inst, _ := ts.GetTenant("default")
	ts.BuildAdminRouter(inst.Adapter, "/tmp/config.json")

	adminSrv := httptest.NewServer(ts.adminRouter)
	defer adminSrv.Close()

	cfg := newInMemoryConfig(t)
	cfgJSON, _ := json.Marshal(cfg)

	body := strings.NewReader(`{"id":"default","config":` + string(cfgJSON) + `}`)
	req, _ := http.NewRequest(http.MethodPost, adminSrv.URL+"/tenants", body)
	req.Header.Set("Authorization", "Bearer test-token")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusConflict {
		t.Errorf("expected 409, got %d", resp.StatusCode)
	}
}

func TestAdminHandler_ListTenants(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	os.Setenv("ADMIN_TOKEN", "test-token")
	defer os.Unsetenv("ADMIN_TOKEN")

	inst, _ := ts.GetTenant("default")
	ts.BuildAdminRouter(inst.Adapter, "/tmp/config.json")

	adminSrv := httptest.NewServer(ts.adminRouter)
	defer adminSrv.Close()

	req, _ := http.NewRequest(http.MethodGet, adminSrv.URL+"/tenants", nil)
	req.Header.Set("Authorization", "Bearer test-token")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}

	var result map[string]any
	json.NewDecoder(resp.Body).Decode(&result)
	tenants, ok := result["tenants"].([]any)
	if !ok || len(tenants) != 1 {
		t.Errorf("expected 1 tenant in list, got %v", result)
	}
}

func TestAdminHandler_RemoveTenant(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	cfg := newInMemoryConfig(t)
	ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
	if _, err := ts.AddTenant(ctx, "to-remove", cfg, ""); err != nil {
		t.Fatalf("AddTenant: %v", err)
	}
	cancel()

	os.Setenv("ADMIN_TOKEN", "test-token")
	defer os.Unsetenv("ADMIN_TOKEN")

	inst, _ := ts.GetTenant("default")
	ts.BuildAdminRouter(inst.Adapter, "/tmp/config.json")

	// Use httptest.Server so chi sets up route params correctly
	adminSrv := httptest.NewServer(ts.adminRouter)
	defer adminSrv.Close()

	req, _ := http.NewRequest(http.MethodDelete, adminSrv.URL+"/tenants/to-remove", nil)
	req.Header.Set("Authorization", "Bearer test-token")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		t.Fatalf("request: %v", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200, got %d", resp.StatusCode)
	}

	if _, ok := ts.GetTenant("to-remove"); ok {
		t.Error("to-remove should be deleted")
	}

	// Remove default attempt — should fail
	req2, _ := http.NewRequest(http.MethodDelete, adminSrv.URL+"/tenants/default", nil)
	req2.Header.Set("Authorization", "Bearer test-token")
	resp2, _ := http.DefaultClient.Do(req2)
	defer resp2.Body.Close()
	if resp2.StatusCode != http.StatusForbidden {
		t.Errorf("expected 403 for default tenant removal, got %d", resp2.StatusCode)
	}
}

// ── ReloadTenant ──

func TestTenantStore_ReloadTenant(t *testing.T) {
	// ReloadTenant calls config.Load which requires config.schema.json on disk.
	// Skip in unit tests — this is tested by integration/e2e tests.
	t.Skip("ReloadTenant requires config.schema.json on disk — tested in integration")
}

func TestTenantStore_ReloadTenant_NotFound(t *testing.T) {
	ts := newTestTenantStore(t)
	addDefaultTenant(t, ts)

	err := ts.ReloadTenant(t.Context(), "nonexistent", "/tmp/config.json")
	if err == nil {
		t.Error("expected error")
	}
}

// ── computeOverallStatus ──

func TestComputeOverallStatus(t *testing.T) {
	tests := []struct {
		name   string
		health []TenantHealth
		want   string
	}{
		{"empty", []TenantHealth{}, "unhealthy"},
		{"all healthy", []TenantHealth{{Status: "healthy"}, {Status: "healthy"}}, "healthy"},
		{"degraded", []TenantHealth{{Status: "healthy"}, {Status: "unhealthy"}}, "degraded"},
		{"all unhealthy", []TenantHealth{{Status: "unhealthy"}, {Status: "unhealthy"}}, "unhealthy"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := computeOverallStatus(tt.health); got != tt.want {
				t.Errorf("computeOverallStatus() = %v, want %v", got, tt.want)
			}
		})
	}
}
