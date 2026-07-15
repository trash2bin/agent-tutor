package configgen

import (
	"context"
	"fmt"
	"testing"

	"github.com/trash2bin/helperium/data-service/internal/datasource"
	"github.com/trash2bin/helperium/helperium-go/config"
)

// TestShop_IntrospectRelations проверяет на реальной shop базе данных,
// что FK introspection + configgen генерируют правильные relations.
func TestShop_IntrospectRelations(t *testing.T) {
	ctx := context.Background()
	adapter := datasource.SqliteAdapter{}

	conn, err := adapter.Connect(ctx, "../../testdata/scenarios/shop/data.db")
	if err != nil {
		t.Fatalf("connect: %v", err)
	}
	defer conn.Close() //nolint:errcheck

	schema, err := adapter.Introspect(ctx, conn)
	if err != nil {
		t.Fatalf("introspect: %v", err)
	}

	// Проверяем что FK introspection работает
	fkCount := 0
	for _, tbl := range schema.Tables {
		fkCount += len(tbl.ForeignKeys)
	}
	t.Logf("schema: %d tables, %d foreign keys", len(schema.Tables), fkCount)
	if fkCount == 0 {
		t.Fatal("expected at least 1 FK in shop schema")
	}

	// Генерируем конфиг
	ds := config.DataSourceConfig{
		Driver: "sqlite",
		DSN:    "../../../testdata/scenarios/shop/data.db",
	}
	cfg := Generate(schema, ds, nil)

	// Подсчитываем relations
	totalRelations := 0
	for _, e := range cfg.Entities {
		totalRelations += len(e.Relations)
	}
	t.Logf("configgen: %d entities, %d endpoints, %d relations, %d MCP tools, %d custom_queries",
		len(cfg.Entities), len(cfg.Endpoints), totalRelations, len(cfg.MCPTools), len(cfg.CustomQueries))

	// Shop schema has 5 FK constraints:
	//   products.category_id → categories.id
	//   orders.customer_id → customers.id
	//   order_items.order_id → orders.id
	//   order_items.product_id → products.id
	//   reviews.product_id → products.id
	//   reviews.customer_id → customers.id
	if totalRelations < 5 {
		t.Errorf("expected at least 5 relations from FK, got %d", totalRelations)
	}

	// Проверяем конкретные relations
	relationMap := make(map[string]string) // "entity.field" → "target_table"
	for _, e := range cfg.Entities {
		for _, r := range e.Relations {
			key := fmt.Sprintf("%s.%s", e.Name, r.Field)
			relationMap[key] = r.Table
		}
	}

	expectedRelations := map[string]string{
		"products.category_id": "categories",
		"orders.customer_id":   "customers",
		"order_items.order_id": "orders",
		"order_items.product_id": "products",
		"reviews.product_id":   "products",
		"reviews.customer_id":  "customers",
	}

	for key, expectedTable := range expectedRelations {
		if actual, ok := relationMap[key]; !ok {
			t.Errorf("missing relation %s", key)
		} else if actual != expectedTable {
			t.Errorf("relation %s: expected %s, got %s", key, expectedTable, actual)
		}
	}

	// Логируем для наглядности
	for _, e := range cfg.Entities {
		if len(e.Relations) > 0 {
			t.Logf("  %s relations:", e.Name)
			for _, r := range e.Relations {
				t.Logf("    %s (FK=%s) → %s [%s]", r.Field, r.LocalFK, r.Table, r.Kind)
			}
		}
	}

	// ── Phase 2: Navigation Endpoints ──
	// Проверяем что для каждого FK сгенерирован navigation endpoint
	navEndpoints := make(map[string]bool)
	for _, ep := range cfg.Endpoints {
		if ep.Op == config.OpCustomQuery {
			navEndpoints[ep.Path] = true
			t.Logf("  nav endpoint: %s (query=%s)", ep.Path, ep.QueryID)
		}
	}

	expectedNavEndpoints := []string{
		"/categories/{id}/products",
		"/customers/{id}/orders",
		"/customers/{id}/reviews",
		"/orders/{id}/order_items",
		"/products/{id}/order_items",
		"/products/{id}/reviews",
	}

	for _, ep := range expectedNavEndpoints {
		if !navEndpoints[ep] {
			t.Errorf("missing navigation endpoint %s", ep)
		}
	}

	// Проверяем custom queries
	if len(cfg.CustomQueries) != 6 {
		t.Errorf("expected 6 custom queries, got %d", len(cfg.CustomQueries))
	}
	for queryID, cq := range cfg.CustomQueries {
		if cq.SQL == "" {
			t.Errorf("custom query %s has empty SQL", queryID)
		}
		if len(cq.Params) != 1 {
			t.Errorf("custom query %s: expected 1 param, got %d", queryID, len(cq.Params))
		}
		t.Logf("  query %s: %s (param=%s)", queryID, cq.SQL, cq.Params[0])
	}

	// ── Phase 4: Pagination ──
	// Проверяем что limit/offset параметры добавлены к find/list endpoints
	paginationParams := make(map[string]bool)
	for _, ep := range cfg.Endpoints {
		if ep.Op == config.OpFind || ep.Op == config.OpList {
			for _, p := range ep.Params {
				paginationParams[ep.Path+":"+p.Name] = true
			}
		}
	}
	for _, path := range []string{"/products", "/customers", "/categories"} {
		if !paginationParams[path+":limit"] {
			t.Errorf("missing 'limit' param on %s", path)
		}
		if !paginationParams[path+":offset"] {
			t.Errorf("missing 'offset' param on %s", path)
		}
	}

	// ── Phase 6: Distinct Endpoints ──
	// Проверяем что distinct endpoint'ы сгенерированы для enum-колонок
	distinctEndpoints := make(map[string]bool)
	for _, ep := range cfg.Endpoints {
		if ep.Op == config.OpDistinct {
			distinctEndpoints[ep.Path] = true
			t.Logf("  distinct endpoint: %s", ep.Path)
		}
	}
	// orders.status → /orders/distinct
	// customers.city → /customers/distinct
	if !distinctEndpoints["/orders/distinct"] {
		t.Error("missing /orders/distinct endpoint (status is enum)")
	}
	if !distinctEndpoints["/customers/distinct"] {
		t.Error("missing /customers/distinct endpoint (city is enum)")
	}
}
