# configgen — Генерация конфига data-service из интроспекции БД

## Overview

Configgen — ядро интеллектуальной интроспекции: получает `datasource.Schema` (generic-схема БД), применяет skip-правила, строит декларативный `config.Config` с эндпоинтами, тулами и навигацией, на основе которого data-service обслуживает HTTP/MCP-запросы.

## Pipeline

```
datasource.Adapter.Introspect() → Schema
         │
         ▼
  configgen.Generate(schema, dsConfig, skipPrefixes)
         │
         ├── shouldSkip()               → фильтрация: SkipRule + prefixes
         ├── tableToEntity()            → Table → Entity (поля, FK, PK)
         ├── findSearchField()          → колонка для text search
         ├── buildFilterParams()        → query-параметры для find/list
         ├── findEnumColumns()          → enum-колонки для distinct
         ├── buildCRUDEndpoints()       → REST-endpoint'ы на entity
         ├── buildNavigationEndpoints() → FK → custom_query + endpoint
         ├── GenerateSchemaForLLM()     → LLM-дружественная схема (без SQL)
         └── GenerateMCPTools()         → эндпоинты → MCP-манифест
```

## File Map

| Файл | Ответственность | Ключевые экспорты | Размер |
|---|---|---|---|
| **`configgen.go`** | Skip-правила, публичное API (`Generate`), CRUD-эндпоинты, counters | `Generate()`, `SkipRule`, `DefaultSkipRules()`, `shouldSkip()`, `buildCRUDEndpoints()`, `buildCounters()`, `findSearchFieldFromEntity()` | ~370 строк |
| **`columns.go`** | Семантический анализ колонок — поиск name/enum/search полей, фильтр-параметры | `isNameField()`, `findSearchField()`, `findEnumColumns()`, `fieldTypeToParamType()`, `buildFilterParams()` | ~100 строк |
| **`entity.go`** | Преобразование `datasource.Table` → `config.Entity` (поля, FK → relations, PK) | `tableToEntity()` | ~55 строк |
| **`naming.go`** | Форматирование имён для UI и LLM: pluralization, title case, business names, display prefixes | `DisplayPrefixes`, `shortBusinessName()`, `titleCase()`, `shortColumnName()`, `pluralizeEntity()`, `toolDisplayName()` | ~100 строк |
| **`navigation.go`** | Построение навигационных эндпоинтов из FK-связей (child-by-parent, custom queries) | `buildNavigationEndpoints()` | ~60 строк |
| **`llm.go`** | LLM-дружественное представление схемы: типы `SchemaForLLM`, генерация хинтов | `SchemaForLLM`, `LLMEntity`, `FilterGroup`, `FilterField`, `LLMRelation`, `GenerateSchemaForLLM()`, `compactFilterSummary()` | ~270 строк |
| **`mcp.go`** | Генерация MCP-манифеста: эндпоинты → инструменты для LLM | `GenerateMCPTools()`, `deriveToolParams()`, `extractPathParams()` | ~180 строк |
| **`configgen_test.go`** | Unit-тесты (8) | `TestGenerate*` | ~500 строк |
| **`integration_test.go`** | Интеграционные тесты против реальной БД (11, `-tags=integration`) | `TestAutoparts_*` | ~300 строк |

### Структура пакета

```
internal/configgen/
├── configgen.go          // Skip-правила + оркестратор Generate
├── columns.go            // Анализ колонок: name/enum/search/filter поля
├── entity.go             // datasource.Table → config.Entity
├── naming.go             // Форматирование имён (plural, title, display)
├── navigation.go         // FK → custom_queries + navigation endpoints
├── llm.go                // SchemaForLLM — для system prompt агента
├── mcp.go                // GenerateMCPTools — MCP-манифест
├── configgen_test.go     // Unit-тесты
└── integration_test.go   // Integration-тесты против реальной БД
```

## Contracts — Who Calls What

### Inbound (data-service → configgen)

```
server/endpoint_builder.go:69  →  NewRouterFromConfig(ts *TenantStore, cfg *config.Config, ...)
server/tenant.go:259           →  ReloadTenant() → использует cfg
server/handlers/admin.go       →  adminRewriteHandler() → Introspect + Generate → SaveTenantConfig
```

### Outbound (configgen → data-service runtime)

```
configgen.Generate() → *config.Config → endpoint_builder.go → HTTP handlers
configgen.GenerateMCPTools() → []config.MCPTool → mcp_manifest.go → GET /mcp/manifest
configgen.GenerateSchemaForLLM() → *SchemaForLLM → tenant.go → GET /mcp/schema
```

### Cross-service (configgen → mcp-gateway → api-service)

```
data-service /mcp/schema
    → mcp-gateway GET /mcp/schema?tenant=...
        → api-service MCPClient._open_connection()
            → orchestrator._build_schema_message() → system prompt
```

## Core Types

### `SchemaForLLM` — LLM-friendly schema (NO raw SQL)

```go
// llm.go:15
type SchemaForLLM struct {
    Entities      []LLMEntity   `json:"entities"`
    WorkflowHints []string      `json:"workflow_hints,omitempty"`
}

// llm.go:26
type LLMEntity struct {
    Name         string        `json:"name"`          // "Product (catalog_product)"
    ToolPrefix   string        `json:"-"`             // raw entity name for tool refs
    Description  string        `json:"description"`
    SearchFields string        `json:"search_fields"` // e.g. "partial match on 'name'"
    FilterFields []FilterGroup `json:"filter_fields"` // grouped by type
    Relations    []LLMRelation `json:"relations"`     // FK relationships
}

// llm.go:49
type FilterGroup struct {
    Label  string        `json:"label"`  // "exact" | "bool" | "range" | "text search"
    Fields []FilterField `json:"fields"`
}
```

### Blocking/non-blocking contract

```go
// ALL functions are pure — no I/O, no side effects.
func Generate(schema *datasource.Schema, ds config.DataSourceConfig, skipPrefixes []string) *config.Config
func GenerateSchemaForLLM(schema *datasource.Schema, cfg *config.Config) *SchemaForLLM
func GenerateMCPTools(endpoints []config.Endpoint, entities []config.Entity) []config.MCPTool
```

## Skip Rules — How Tables Are Filtered

### `SkipRule` struct

```go
// configgen.go
type SkipRule struct {
    Prefix   string  // "auth_", "django_", "sqlite_"
    Suffix   string  // "_log", "_cache"
    Contains string  // "migration", "session"
    Reason   string  // "Django auth system"
}
```

`matches(name)` AND-ит все непустые поля. Правила статичны, но можно передать `skipPrefixes []string` в `Generate()` для кастомных.

### Default rules (`DefaultSkipRules()`)

| Prefix/Contains | Reason | Framework |
|---|---|---|
| `sqlite_` | SQLite system table | SQLite |
| `pg_`, `pg_catalog`, `information_schema` | PG system tables | PostgreSQL |
| `auth_` | Django auth system | Django |
| `django_` | Django framework internals | Django |
| `session` | Django session storage | Django |
| `documents` | RAG internal table | Helperium |
| `migrations` | Framework migration tracking | Laravel |
| `jobs`, `failed_jobs` | Queue internals | Laravel |
| `schema_migrations` | Rails migration tracking | Rails |
| `ar_internal_metadata` | Rails internals | Rails |

### Schema-awareness in `shouldSkip()`

```go
// Matching checks both schema-qualified (public.auth_group) and short (auth_group):
shouldSkip("public.auth_group", rules, nil) == true  // matches Prefix: "auth_"
```

## DisplayPrefixes — Configurable Name Stripping

### Single source of truth

```go
// naming.go:14  —  var в naming.go
var DisplayPrefixes = []string{"catalog_", "auth_", "django_"}
```

### Where it's used (5 sites, all reference `DisplayPrefixes`)

| Function | Purpose | File |
|---|---|---|
| `shortBusinessName()` | Entity display name: `catalog_Product` → `Product` | naming.go |
| `pluralizeEntity()` | Pluralization input: `catalog_cartitem` → `cartitem` | naming.go |
| `toolDisplayName()` | Tool display name: `get catalog_product` → `get product` | naming.go |
| `GenerateMCPTools()` | Nav tool name: `products_by_brand` (child side) | mcp.go |
| `GenerateMCPTools()` | Nav tool name: `products_by_brand` (parent side) | mcp.go |

### Adding a prefix

```go
// For WordPress tables:
DisplayPrefixes = []string{"wp_", "catalog_", "auth_", "django_"}
// → "wp_posts" → "Posts", "wp_usermeta" → "Usermeta"
```

## Endpoint Generation Logic

### Phase 1: Table → Entity

```go
// entity.go
Parse: datastore.Table → config.Entity
  - Name: "public.students" → "students" (strip schema prefix)
  - IDColumn: PK column (first PK col, or first col as fallback)
  - Fields: all columns → config.EntityField
  - Relations: FK → many_to_one relationship
```

### Phase 2: Endpoint creation (per entity)

```go
// configgen.go — buildCRUDEndpoints()
```

| Condition | Endpoint | Tool Name |
|---|---|---|
| Always (if PK exists) | `GET /{entity}/{id}` | `get_{entity}` |
| Has name/search field | `GET /{entity}?name=...` | `find_{entity}` |
| No name field | `GET /{entity}` (list all) | `list_{entity}` |
| Has enum columns | `GET /{entity}/distinct?column=X` | `distinct_{entity}` |
| Always | `GET /{entity}/count` | `count_{entity}` |
| Each FK relation | `GET /{parent}/{id}/{child}` | `{child_plural}_by_{parent}` |

### Phase 3: Navigation from FK

```go
// navigation.go — buildNavigationEndpoints()
```

For each FK relation in entity:
  - parent = resolve parent entity
  - queryID = `"{child_table}_by_{parent_table}_{fk_column}"`
  - SQL: `SELECT t.* FROM {child_table} t WHERE t.{fk_col} = ?`
  - Endpoint: path `/{parent}/{id}/{child}`, op `custom_query`
  - MCP tool: name `"{child_plural}_by_{parent_short}"`

## Search Field Detection

```go
// columns.go
func findSearchFieldFromEntity(entity config.Entity) string
```

**Matches:** `name`, `full_name`, `first_name`, `last_name`, `title` (string type only).
**Priority:** First matching field in entity definition order.

## Filter Parameter Generation

```go
// columns.go
func buildFilterParamsFromEntity(entity config.Entity, searchCol string) []config.EndpointParam
```

### Field type → param mapping

| Field type | Param type | SQL operator | Notes |
|---|---|---|---|
| `string` (search) | `ParamTypeString` | ILIKE/LIKE | only if col == searchCol |
| `int` | `ParamTypeInt` | `=` | exact match |
| `float` | `ParamTypeFloat` | `=` | exact match |
| `bool` | `ParamTypeBool` | `=` | true/false |
| `datetime` / `date` | `ParamTypeString` | comparison | ISO-8601 ("2024-01-15") |

## LLM Schema Injection

### Data flow

```
data-service /mcp/schema?tenant=autoparts
  → mcp-gateway GET /mcp/schema (proxy)
    → api-service MCPClient._open_connection()
      → cached per-connection (conn.schema)
        → orchestrator._run_turn()
          → _build_schema_message() → system prompt
```

### Format

```
=== STRUCTURE OF DATA (auto-loaded from DB) ===

📦 Product (catalog_product)
   Search: partial match on 'name'
   Filters (bool): is_available, is_popular, is_new...
   Filters (range): price, brand_id (FK → Brand)...
   Filters (exact): article, oem_number...
   Relations: brand_id → Brand, category_id → Category

📦 Brand (catalog_brand)
   Search: partial match on 'name'
   ...

💡 Categories = part type (brake pads, shock absorbers).
   Brands = manufacturer (Bosch, KYB, TRW).
   Search category first, then find products via products_by_category.
```

### What's NOT in schema

- ❌ Raw SQL types (TEXT, INTEGER, JSONB) — only "string", "int", "bool", "json"
- ❌ Schema-qualified table names — only business names
- ❌ Primary keys, indexes, constraints
- ❌ System tables (auth_*, django_*, pg_*)

## Tool Description Optimization

### Naming conventions

| Op | Tool Name | Display Name | Description |
|---|---|---|---|
| `get_by_id` | `get_product` | `product by ID` | "Get a single record by its unique ID. Use after find_product when you have a specific ID." |
| `find` | `find_product` | `Find product` | "Search products by name (partial match). Filters: ..." |
| `list` | `list_product` | `All products` | "List all products. Use when find_product returns no results." |
| `count` | `count_product` | `Count products` | "Count products matching filters. Returns {entity, count}." |
| `distinct` | `distinct_product` | `Distinct products` | "Get unique values for enum columns in products." |
| `custom_query` | `products_by_brand` | `products by brand` | "Get all products for a given brand." |

### Strategic hints in descriptions

Some tools include workflow guidance in `mcp.go`:
- `find_product`: "If user asks about a type (e.g. 'muffler', 'brake pads'), search categories first, then navigate to products."
- `products_by_category`: "Use after find_category, then call this to list related products."
- Filter summary: `"partial match on 'name'; exact: article, price, +22 more; bool: is_available"`

### JSONB fields

**Do NOT generate filter params** for JSON/JSONB columns — ILIKE/LIKE does not work on them.

## Testing

### Unit tests (no DB needed)

```bash
go test ./data-service/internal/configgen/ -v           # 8 tests, ~50ms
```

### Integration tests (require running PG DB)

```bash
go test -tags=integration ./data-service/internal/configgen/ -run TestAutoparts -v  # 11 tests
```

### Integration test coverage

| Test | Checks |
|---|---|
| `TestAutoparts_Introspect` | Correct table count (17 raw), column types |
| `TestAutoparts_GenerateEntities` | 7 entities (not 17), filtered skip rules |
| `TestAutoparts_Relations` | FK relations found |
| `TestAutoparts_BoolFilters` | Bool params |
| `TestAutoparts_CountEndpoints` | 7 count_* endpoints |
| `TestAutoparts_MCPTools` | MCP tools, display names in English |
| `TestAutoparts_CustomQueries` | Navigation queries from FK |
| `TestAutoparts_ToolCount` | Stable tool count (29) |

## Adding a New Adapter (MySQL, MSSQL)

1. Create `mysql_adapter.go` implementing `datasource.Adapter`
2. Register in `datasource.NewDefaultRegistry()`
3. Add `DriverMySQL` to `helperium-go/config/types.go`
4. Add MySQL-specific skip rules to `DefaultSkipRules()` if needed
5. Integration test: register tenant with MySQL DSN, run rewrite

**No changes needed in configgen** — adapter pattern keeps everything generic.

## Related docs

- `doc/api-flow.md` — HTTP communication between services
- `AGENTS.md` — §2a MCP Architecture, §2b Tenant Lifecycle, §6 Tenant Isolation
- `helperium-go/config/types.go` — `Config`, `Entity`, `Endpoint`, `MCPTool` types
- `data-service/internal/datasource/adapter.go` — `Adapter` interface, `Schema`, `Table`, `Column`
