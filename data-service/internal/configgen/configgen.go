// Package configgen генерирует конфиг data-service из интроспекции БД.
//
// Берёт datasource.Schema (таблицы, колонки, FK) и превращает в готовый
// config.Config с entities, endpoint'ами и stats. Без custom_queries —
// их пишет клиент под свою бизнес-логику.
//
// Использование:
//
//	adapter := datasource.SqliteAdapter{}
//	conn, _ := adapter.Connect(ctx, "university.db")
//	schema, _ := adapter.Introspect(ctx, conn)
//	cfg := configgen.Generate(schema, datasourceConfig, nil)
//	json.NewEncoder(os.Stdout).Encode(cfg)
package configgen

import (
	"fmt"
	"sort"
	"strings"

	"github.com/trash2bin/helperium/data-service/internal/datasource"
	"github.com/trash2bin/helperium/helperium-go/config"
)

// ── Skip rules ──

// SkipRule defines a pattern for tables to exclude from tool generation.
// Matching is done against the table name; multiple fields are AND-ed.
type SkipRule struct {
	Prefix   string // Match table name prefix (e.g., "auth_", "django_")
	Suffix   string // Match table name suffix
	Contains string // Match substring
	Reason   string // Human-readable reason for skipping
}

// matches returns true if the table name satisfies this rule.
func (r SkipRule) matches(name string) bool {
	if r.Prefix != "" && !strings.HasPrefix(name, r.Prefix) {
		return false
	}
	if r.Suffix != "" && !strings.HasSuffix(name, r.Suffix) {
		return false
	}
	if r.Contains != "" && !strings.Contains(name, r.Contains) {
		return false
	}
	return true
}

// DefaultSkipRules returns framework-agnostic rules for system tables.
// Used by Generate to filter out Django, Laravel, Rails, and DB-internal tables.
func DefaultSkipRules() []SkipRule {
	return []SkipRule{
		// SQLite internals
		{Prefix: "sqlite_", Reason: "SQLite system table"},
		// PostgreSQL internals
		{Prefix: "pg_", Reason: "PostgreSQL system table"},
		{Prefix: "pg_catalog", Reason: "PostgreSQL catalog"},
		{Prefix: "information_schema", Reason: "SQL information schema"},
		// Django framework
		{Prefix: "auth_", Reason: "Django auth system (not business data)"},
		{Prefix: "django_", Reason: "Django framework internals"},
		{Prefix: "session", Reason: "Django session storage"},
		// RAG internal
		{Prefix: "documents", Reason: "RAG internal table"},
		// Laravel (future)
		{Prefix: "migrations", Reason: "Framework migration tracking"},
		{Prefix: "jobs", Reason: "Queue internals"},
		{Prefix: "failed_jobs", Reason: "Queue internals"},
		// Rails (future)
		{Prefix: "schema_migrations", Reason: "Rails migration tracking"},
		{Prefix: "ar_internal_metadata", Reason: "Rails internals"},
	}
}

// shouldSkip checks if a table name matches any skip rule.
// If skipRules is provided, uses structured SkipRule matching.
// Otherwise falls back to legacy prefix-only matching.
func shouldSkip(name string, skipRules []SkipRule, legacyPrefixes []string) bool {
	// For schema-qualified names (e.g. "public.auth_group"),
	// match against both the full name and the short name (after last dot).
	shortName := name
	if idx := strings.LastIndex(name, "."); idx >= 0 {
		shortName = name[idx+1:]
	}

	for _, rule := range skipRules {
		if rule.matches(name) || rule.matches(shortName) {
			return true
		}
	}
	for _, p := range legacyPrefixes {
		if strings.HasPrefix(name, p) || strings.HasPrefix(shortName, p) {
			return true
		}
	}
	return false
}

// Generate создаёт *config.Config из интроспекции схемы БД.
//
// Параметры:
//   - schema — результат Introspect адаптера
//   - ds — data_source часть конфига (driver + dsn)
//   - skipPrefixes — дополнительные префиксы для исключения таблиц (nil = только дефолтные)
func Generate(schema *datasource.Schema, ds config.DataSourceConfig, skipPrefixes []string) *config.Config {
	skipRules := DefaultSkipRules()

	// Read-only by default
	readOnly := true
	if ds.ReadOnly == nil {
		ds.ReadOnly = &readOnly
	}

	cfg := &config.Config{
		Version:    1,
		DataSource: ds,
	}

	// Сортируем таблицы для детерминизма
	tables := append([]datasource.Table{}, schema.Tables...)
	sort.Slice(tables, func(i, j int) bool {
		return tables[i].Name < tables[j].Name
	})

	var entities []config.Entity
	for _, tbl := range tables {
		if shouldSkip(tbl.Name, skipRules, skipPrefixes) {
			continue
		}
		entities = append(entities, tableToEntity(tbl))
	}

	endpoints := buildCRUDEndpoints(entities)
	navEndpoints, customQueries := buildNavigationEndpoints(entities)
	endpoints = append(endpoints, navEndpoints...)

	// Системные эндпоинты
	endpoints = append(endpoints, config.Endpoint{
		Method: config.MethodGET,
		Path:   "/health",
		Op:     config.OpBuiltinHealth,
	})
	endpoints = append(endpoints, config.Endpoint{
		Method: config.MethodGET,
		Path:   "/stats",
		Op:     config.OpBuiltinStats,
	})

	cfg.Entities = entities
	cfg.Endpoints = endpoints
	cfg.Stats = &config.StatsConfig{Counters: buildCounters(entities)}

	if len(customQueries) > 0 {
		cfg.CustomQueries = customQueries
	}

	cfg.MCPTools = GenerateMCPTools(endpoints, entities)

	return cfg
}

// ── CRUD endpoint generation ──

// buildCRUDEndpoints creates CRUD endpoints (get_by_id, find, list, distinct, count)
// for each entity based on its table structure, including filter params.
func buildCRUDEndpoints(entities []config.Entity) []config.Endpoint {
	var endpoints []config.Endpoint

	for _, entity := range entities {
		// get_by_id (по entity.IDColumn)
		if entity.IDColumn != "" {
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s/{%s}", entity.Name, entity.IDColumn),
				Op:          config.OpGetByID,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns %s by identifier", entity.Name),
			})
		}

		// find (по name-полю) — поиск по тексту + фильтры
		searchCol := findSearchFieldFromEntity(entity)
		if searchCol != "" {
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s", entity.Name),
				Op:          config.OpFind,
				Entity:      entity.Name,
				SearchField: searchCol,
				QueryParam:  searchCol,
				Description: fmt.Sprintf("Searches %s by name. Returns all records when no query given.", entity.Name),
				Params:      buildFilterParamsFromEntity(entity, searchCol),
			})
		} else if entity.IDColumn != "" {
			// Нет name-поля — list как fallback с фильтрами
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s", entity.Name),
				Op:          config.OpList,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns all %s. Use filters to narrow results.", entity.Name),
				Params:      buildFilterParamsFromEntity(entity, ""),
			})
		}

		// distinct endpoint — enum-колонки
		enumCols := findEnumColumnsFromEntity(entity)
		if len(enumCols) > 0 {
			required := true
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s/distinct", entity.Name),
				Op:          config.OpDistinct,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns unique values for enum columns in %s", entity.Name),
				Params: []config.EndpointParam{
					{
						Name:     "column",
						In:       config.ParamInQuery,
						Type:     config.ParamTypeString,
						Required: &required,
						Description: fmt.Sprintf(
							"Column name to get distinct values from. Available columns: %s",
							strings.Join(enumCols, ", ")),
					},
				},
			})
		}

		// count endpoint
		endpoints = append(endpoints, config.Endpoint{
			Method:      config.MethodGET,
			Path:        fmt.Sprintf("/%s/count", entity.Name),
			Op:          config.OpCount,
			Entity:      entity.Name,
			Description: fmt.Sprintf("Counts %s records matching filters", entity.Name),
		})
	}

	return endpoints
}

// buildCounters creates stats counters for each entity.
func buildCounters(entities []config.Entity) []config.Counter {
	counters := make([]config.Counter, 0, len(entities))
	for _, entity := range entities {
		counters = append(counters, config.Counter{
			Name:   entity.Name,
			Entity: entity.Name,
		})
	}
	return counters
}
