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

	"github.com/trash2bin/helperium/helperium-go/config"
	"github.com/trash2bin/helperium/data-service/internal/datasource"
)

// skipPrefixes — таблицы, начинающиеся с этих префиксов, исключаются.
// Можно расширять через Generate's skipPrefixes параметр.
var defaultSkipPrefixes = []string{
	"sqlite_",
	"pg_",
	"documents", // внутренняя таблица RAG
}

// isNameField возвращает true, если колонка похожа на поисковое имя.
// Критерий: тип string, название содержит name/last_name/first_name/title.
func isNameField(col datasource.Column) bool {
	lower := strings.ToLower(col.Name)
	return col.Type == datasource.TypeString &&
		(lower == "name" ||
			strings.HasSuffix(lower, "_name") ||
			strings.HasSuffix(lower, "_title") ||
			strings.HasPrefix(lower, "name"))
}

// findSearchField ищет колонку для поиска (первую подходящую).
func findSearchField(cols []datasource.Column) (datasource.Column, bool) {
	for _, c := range cols {
		if isNameField(c) {
			return c, true
		}
	}
	return datasource.Column{}, false
}

// Generate создаёт *config.Config из интроспекции схемы БД.
//
// Параметры:
//   - schema — результат Introspect адаптера
//   - ds — data_source часть конфига (driver + dsn)
//   - skipPrefixes — дополнительные префиксы для исключения таблиц (nil = только дефолтные)
func Generate(schema *datasource.Schema, ds config.DataSourceConfig, skipPrefixes []string) *config.Config {
	mergedSkip := append([]string{}, defaultSkipPrefixes...)
	mergedSkip = append(mergedSkip, skipPrefixes...)

	// Read-only by default: сгенерированный конфиг не должен мутировать БД.
	// Клиент может явно выставить read_only: false вручную через admin API.
	trueVal := true
	if ds.ReadOnly == nil {
		ds.ReadOnly = &trueVal
	}

	cfg := &config.Config{
		Version:    1,
		DataSource: ds,
	}

	entities := make([]config.Entity, 0)
	endpoints := make([]config.Endpoint, 0)
	counters := make([]config.Counter, 0)

	// Сортируем таблицы для детерминизма
	tables := append([]datasource.Table{}, schema.Tables...)
	sort.Slice(tables, func(i, j int) bool {
		return tables[i].Name < tables[j].Name
	})

	for _, tbl := range tables {
		if shouldSkip(tbl.Name, mergedSkip) {
			continue
		}

		entity := tableToEntity(tbl)
		entities = append(entities, entity)

		// get_by_id (по entity.IDColumn — реальному PK или fallback'у)
		if entity.IDColumn != "" {
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s/{%s}", entity.Name, entity.IDColumn),
				Op:          config.OpGetByID,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns %s by identifier", entity.Name),
			})
		}

		// find (по name-полю) — поиск по тексту + фильтры по всем полям
		if searchCol, ok := findSearchField(tbl.Columns); ok {
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s", entity.Name),
				Op:          config.OpFind,
				Entity:      entity.Name,
				SearchField: searchCol.Name,
				QueryParam:  searchCol.Name,
				Description: fmt.Sprintf("Searches %s by name. Returns all records when no query given.", entity.Name),
				Params:      buildFilterParams(tbl.Columns, entity, searchCol.Name),
			})
		} else if entity.IDColumn != "" {
			// Нет name-поля — list как fallback (чтобы агент мог получить все записи)
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s", entity.Name),
				Op:          config.OpList,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns all %s. Use filters to narrow results.", entity.Name),
				Params:      buildFilterParams(tbl.Columns, entity, ""),
			})
		}

		// distinct endpoint — возвращает уникальные значения enum-колонок
		// (status, type, city и т.д.), чтобы агент знал допустимые значения.
		enumCols := findEnumColumns(tbl.Columns, entity)
		if len(enumCols) > 0 {
			params := make([]config.EndpointParam, 0, len(enumCols))
			params = append(params, config.EndpointParam{
				Name:     "column",
				In:       config.ParamInQuery,
				Type:     config.ParamTypeString,
				Required: boolPtr(true),
				Description: fmt.Sprintf(
					"Column name to get distinct values from. "+
						"Available columns: %s", strings.Join(enumCols, ", ")),
			})
			endpoints = append(endpoints, config.Endpoint{
				Method:      config.MethodGET,
				Path:        fmt.Sprintf("/%s/distinct", entity.Name),
				Op:          config.OpDistinct,
				Entity:      entity.Name,
				Description: fmt.Sprintf("Returns unique values for enum columns in %s", entity.Name),
				Params:      params,
			})
		}

		// count endpoint — возвращает количество записей с фильтрами
		countParams := buildFilterParams(tbl.Columns, entity, "")
		endpoints = append(endpoints, config.Endpoint{
			Method:      config.MethodGET,
			Path:        fmt.Sprintf("/%s/count", entity.Name),
			Op:          config.OpCount,
			Entity:      entity.Name,
			Description: fmt.Sprintf("Counts %s records matching filters", entity.Name),
			Params:      countParams,
		})

		// stats — Counter.Name тоже должен пройти regex ^[a-z][a-z0-9_]*$
		// (JSON Schema строже чем Entity.Name? нет — оба проверяются).
		// Используем "короткое" имя (без schema prefix).
		counters = append(counters, config.Counter{
			Name:   entity.Name,
			Entity: entity.Name,
		})
	}

	// ── Phase 2: Auto-generate Navigation Endpoints from FK Relations ──
	//
	// FK relations уже заполнены в tableToEntity (Phase 1).
	// Для каждого FK генерируем:
	//   1. CustomQuery: SELECT * FROM child_table WHERE fk = ?
	//   2. Endpoint: GET /parent/{id}/child (custom_query)
	//   3. MCP tool автоматически через GenerateMCPTools.
	//
	// Реверс-направление (child.filter=fk_value) уже покрыто фильтрами
	// из buildFilterParams — это отдельный сценарий использования.
	customQueries := make(map[string]config.CustomQuery)
	for _, entity := range entities {
		for _, rel := range entity.Relations {
			// rel.Table — parent таблица (куда ссылается FK)
			// rel.LocalFK — колонка FK в текущей (child) таблице
			// rel.Kind = many_to_one: child.fk → parent.id
			//
			// Navigation endpoint: GET /parent/{id}/child_table
			// "Show me all children for a given parent"

			// Находим parent entity по имени таблицы
			var parentEntity *config.Entity
			for j := range entities {
				if entities[j].Table == rel.Table || entities[j].Name == rel.Table {
					parentEntity = &entities[j]
					break
				}
			}
			if parentEntity == nil {
				continue
			}

			// ID колонка parent'а для {id} в URL
			parentID := parentEntity.IDColumn
			if parentID == "" {
				continue
			}

			// custom_query ID: {child_table}_by_{parent_table}
			queryID := fmt.Sprintf("%s_by_%s", entity.Name, parentEntity.Name)
			if _, exists := customQueries[queryID]; exists {
				continue // уже добавлен (дублирующие FK)
			}

			// SELECT * FROM child_table WHERE fk = ?
			customQueries[queryID] = config.CustomQuery{
				SQL:         fmt.Sprintf("SELECT t.* FROM %s t WHERE t.%s = ?", entity.Table, rel.LocalFK),
				Params:      []string{rel.LocalFK},
				MaxRows:     1000,
				Description: fmt.Sprintf("All %s linked to a %s", entity.Name, parentEntity.Name),
			}

			// Navigation endpoint: GET /parent/{id}/child
			navPath := fmt.Sprintf("/%s/{%s}/%s", parentEntity.Name, parentID, entity.Name)
			// Проверяем дубликат
			dup := false
			for _, ep := range endpoints {
				if ep.Path == navPath && ep.Op == config.OpCustomQuery {
					dup = true
					break
				}
			}
			if !dup {
				endpoints = append(endpoints, config.Endpoint{
					Method:      config.MethodGET,
					Path:        navPath,
					Op:          config.OpCustomQuery,
					QueryID:     queryID,
					Entity:      entity.Name,
					Description: fmt.Sprintf("All %s for a given %s", entity.Name, parentEntity.Name),
				})
			}
		}
	}

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
	cfg.Stats = &config.StatsConfig{Counters: counters}

	// Привязываем сгенерированные custom queries к конфигу
	if len(customQueries) > 0 {
		cfg.CustomQueries = customQueries
	}

	// Generate MCP Tools from endpoints — с разговорными описаниями для LLM.
	cfg.MCPTools = GenerateMCPTools(endpoints, entities)

	return cfg
}

// tableToEntity конвертирует datasource.Table → config.Entity.
//
// Name в config.Entity должен проходить regex ^[a-z][a-z0-9_]*$ (JSON Schema),
// поэтому для многосхемных БД (Postgres: "public.customers") используем
// только последний сегмент (без префикса схемы). Table в config.Entity
// хранит полное имя — QueryBuilder использует его для SQL.
// Если у таблицы нет PRIMARY KEY (миграционные таблицы реальной prod-БД),
// id_column берётся как первая колонка — иначе JSON-Schema реджектит пустую.
func tableToEntity(tbl datasource.Table) config.Entity {
	shortName := tbl.Name
	if idx := strings.LastIndex(shortName, "."); idx >= 0 {
		shortName = shortName[idx+1:]
	}

	fields := make([]config.EntityField, 0, len(tbl.Columns))
	pkSet := make(map[string]bool, len(tbl.PrimaryKey))
	for _, pk := range tbl.PrimaryKey {
		pkSet[pk] = true
	}

	colNames := make([]string, 0, len(tbl.Columns))
	for _, col := range tbl.Columns {
		nullable := col.Nullable
		isPK := pkSet[col.Name]
		fields = append(fields, config.EntityField{
			Name:        col.Name,
			Column:      col.Name,
			Type:        config.FieldType(col.Type),
			Nullable:    &nullable,
			PrimaryKey:  &isPK,
			Description: col.Description,
		})
		colNames = append(colNames, col.Name)
	}

	idCol := firstPK(tbl.PrimaryKey)
	if idCol == "" && len(colNames) > 0 {
		idCol = colNames[0]
	}

	// Auto-generate Relations из ForeignKeys.
	// Каждый FK-constraint с одной колонкой → Relation (many_to_one).
	relations := make([]config.Relation, 0, len(tbl.ForeignKeys))
	for _, fk := range tbl.ForeignKeys {
		if len(fk.Columns) != 1 || len(fk.ReferencedColumns) != 1 {
			continue // composite FK пока пропускаем
		}
		targetTable := fk.ReferencedTable
		if idx := strings.LastIndex(targetTable, "."); idx >= 0 {
			targetTable = targetTable[idx+1:]
		}
		relations = append(relations, config.Relation{
			Field:   fk.Columns[0],
			Kind:    config.RelationManyToOne,
			Table:   targetTable,
			LocalFK: fk.Columns[0],
		})
	}

	return config.Entity{
		Name:      shortName,
		Table:     tbl.Name,
		IDColumn:  idCol,
		Fields:    fields,
		Relations: relations,
	}
}

// firstPK возвращает первую PK-колонку или пустую строку.
func firstPK(pk []string) string {
	if len(pk) > 0 {
		return pk[0]
	}
	return ""
}

// shouldSkip проверяет, начинается ли имя с одного из skip-префиксов.
func shouldSkip(name string, prefixes []string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(name, p) {
			return true
		}
	}
	return false
}

// fieldTypeToParamType конвертирует generic тип колонки в ParamType для MCP-параметров.
func fieldTypeToParamType(col datasource.Column) config.ParamType {
	switch col.Type {
	case datasource.TypeInt:
		return config.ParamTypeInt
	case datasource.TypeFloat:
		return config.ParamTypeFloat
	case datasource.TypeBool:
		return config.ParamTypeBool
	default:
		return config.ParamTypeString
	}
}

// buildFilterParams создаёт параметры фильтрации для find/list endpoints.
// Генерирует query-параметры для ВСЕХ колонок (кроме PK), чтобы агент мог
// фильтровать по любому полю, а не только по name/title.
//
// Для string-колонок: text search (LIKE)
// Для int/float-колонок: exact match
// Для bool-колонок: exact match
//
// searchCol — имя колонки для основного поиска (если есть). Она получает
// приоритетное описание "search by name". Остальные колонки — "filter by exact match".
func buildFilterParams(cols []datasource.Column, entity config.Entity, searchCol string) []config.EndpointParam {
	params := make([]config.EndpointParam, 0)

	for _, col := range cols {
		// Пропускаем PK — по нему есть get_by_id
		isPK := false
		for _, f := range entity.Fields {
			if f.Name == col.Name && f.PrimaryKey != nil && *f.PrimaryKey {
				isPK = true
				break
			}
		}
		if isPK {
			continue
		}

		paramRequired := false

		if col.Name == searchCol {
			// Основное поле поиска — текстовый LIKE-поиск
			params = append(params, config.EndpointParam{
				Name:     col.Name,
				In:       config.ParamInQuery,
				Type:     config.ParamTypeString,
				Required: &paramRequired,
				Description: fmt.Sprintf(
					"Text search on '%s' (LIKE match, partial). "+
						"If omitted, returns all records.", col.Name),
			})
		} else if col.Type == datasource.TypeInt || col.Type == datasource.TypeFloat {
			// Числовые колонки — точное совпадение
			params = append(params, config.EndpointParam{
				Name:     col.Name,
				In:       config.ParamInQuery,
				Type:     fieldTypeToParamType(col),
				Required: &paramRequired,
				Description: fmt.Sprintf(
					"Filter by exact '%s' value.", col.Name),
			})
		} else if col.Type == datasource.TypeString {
			// String колонки — точное совпадение (для FK, email, phone и т.д.)
			params = append(params, config.EndpointParam{
				Name:     col.Name,
				In:       config.ParamInQuery,
				Type:     config.ParamTypeString,
				Required: &paramRequired,
				Description: fmt.Sprintf(
					"Filter by exact '%s' value.", col.Name),
			})
		}
	}

	// Pagination params
	paginationRequired := false
	params = append(params, config.EndpointParam{
		Name:        "limit",
		In:          config.ParamInQuery,
		Type:        config.ParamTypeInt,
		Required:    &paginationRequired,
		Description: "Max records to return (default 100, max 1000).",
	})
	params = append(params, config.EndpointParam{
		Name:        "offset",
		In:          config.ParamInQuery,
		Type:        config.ParamTypeInt,
		Required:    &paginationRequired,
		Description: "Number of records to skip (for pagination).",
	})

	return params
}

// findEnumColumns ищет колонки, которые вероятно являются enum-полями.
// Возвращает имена колонок, которые являются строковыми и содержат
// типичные для enum суффиксы (status, type, role, city, country).
func findEnumColumns(cols []datasource.Column, entity config.Entity) []string {
	var enums []string
	for _, col := range cols {
		// Пропускаем PK
		isPK := false
		for _, f := range entity.Fields {
			if f.Name == col.Name && f.PrimaryKey != nil && *f.PrimaryKey {
				isPK = true
				break
			}
		}
		if isPK {
			continue
		}
		if col.Type != datasource.TypeString {
			continue
		}
		lower := strings.ToLower(col.Name)
		switch {
		case strings.Contains(lower, "status"):
			enums = append(enums, col.Name)
		case strings.Contains(lower, "type"):
			enums = append(enums, col.Name)
		case strings.Contains(lower, "role"):
			enums = append(enums, col.Name)
		case strings.Contains(lower, "city"):
			enums = append(enums, col.Name)
		case strings.Contains(lower, "country"):
			enums = append(enums, col.Name)
		}
	}
	return enums
}

func boolPtr(v bool) *bool {
	return &v
}

// formatFieldsHint форматирует подсказку о полях сущности для описания MCP-тула.
// Пример: "\nFields: name(string), email(string), city(string), status(string)"
func formatFieldsHint(ent *config.Entity) string {
	if len(ent.Fields) == 0 {
		return ""
	}
	parts := make([]string, 0, len(ent.Fields))
	for _, f := range ent.Fields {
		if f.PrimaryKey != nil && *f.PrimaryKey {
			continue
		}
		parts = append(parts, fmt.Sprintf("%s(%s)", f.Name, f.Type))
	}
	return fmt.Sprintf("\nFields: %s", strings.Join(parts, ", "))
}

// formatRelationsHint форматирует подсказку о связях сущности.
// Пример: "\nRelations: category → categories, order_items ← order_items"
func formatRelationsHint(ent *config.Entity) string {
	if len(ent.Relations) == 0 {
		return ""
	}
	parts := make([]string, 0, len(ent.Relations))
	for _, r := range ent.Relations {
		parts = append(parts, fmt.Sprintf("%s → %s", r.Field, r.Table))
	}
	return fmt.Sprintf("\nRelations: %s", strings.Join(parts, ", "))
}

// GenerateMCPTools создаёт MCP-тулы из эндпоинтов с разговорными описаниями для LLM.
// Экспортируемая функция — используется как configgen.Generate, так и
// handlers.MCPManifestHandler для рантайм-генерации без зависимости от дискового конфига.
func GenerateMCPTools(endpoints []config.Endpoint, entities []config.Entity) []config.MCPTool {
	// Быстрый lookup: entity name → entity
	entityMap := make(map[string]*config.Entity, len(entities))
	for i := range entities {
		entityMap[entities[i].Name] = &entities[i]
	}

	tools := make([]config.MCPTool, 0, len(endpoints))
	for _, ep := range endpoints {
		if ep.Op == config.OpBuiltinHealth || ep.Op == config.OpBuiltinStats {
			continue
		}

		var toolName, desc string
		switch ep.Op {
		case config.OpGetByID:
			toolName = fmt.Sprintf("get_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Returns a single %s record by its unique identifier. "+
					"Use when you already know the record ID (e.g. from find_%s).",
				ep.Entity, ep.Entity)

		case config.OpFind:
			toolName = fmt.Sprintf("find_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Searches for %s by text query on name field. "+
					"Supports filtering by any field. "+
					"If no parameter provided, returns all records (use limit to paginate).",
				ep.Entity)
			// Add field info
			if ent, ok := entityMap[ep.Entity]; ok {
				desc += formatFieldsHint(ent)
				desc += formatRelationsHint(ent)
			}

		case config.OpList:
			toolName = fmt.Sprintf("list_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Returns all %s records. "+
					"Supports filtering by any field and pagination (limit/offset).",
				ep.Entity)
			if ent, ok := entityMap[ep.Entity]; ok {
				desc += formatFieldsHint(ent)
				desc += formatRelationsHint(ent)
			}

		case config.OpDistinct:
			toolName = fmt.Sprintf("distinct_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Returns unique values for enum-like columns in %s. "+
					"Use this to discover valid filter values before searching.",
				ep.Entity)

		case config.OpCount:
			toolName = fmt.Sprintf("count_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Counts %s records matching the given filters. "+
					"Returns {entity, count}. Faster than fetching all records.",
				ep.Entity)

		case config.OpCustomQuery:
			toolName = fmt.Sprintf("query_%s", ep.Path)
			toolName = strings.ReplaceAll(toolName, "{", "")
			toolName = strings.ReplaceAll(toolName, "}", "")
			toolName = strings.ReplaceAll(toolName, "/", "_")
			toolName = strings.TrimPrefix(toolName, "_")
			if ep.Description != "" {
				desc = fmt.Sprintf("Executes custom query: %s", ep.Description)
			} else {
				desc = fmt.Sprintf("Executes custom query at %s", ep.Path)
			}
		}

		if toolName != "" {
			params := deriveToolParams(ep)
			tools = append(tools, config.MCPTool{
				Name:        toolName,
				Endpoint:    ep.Path,
				Description: desc,
				Params:      params,
			})
		}
	}
	return tools
}

// deriveToolParams извлекает параметры инструмента из структуры endpoint'а.
// Если endpoint имеет явные Params (из configgen), используем их.
// Иначе — auto-generate из path params + search field.
func deriveToolParams(ep config.Endpoint) []config.EndpointParam {
	// Если endpoint уже имеет Params (из configgen.buildFilterParams) — используем их
	if len(ep.Params) > 0 {
		return ep.Params
	}

	params := make([]config.EndpointParam, 0)

	// 1. Path params из {param} в URL
	pathParams := extractPathParams(ep.Path)
	for _, pp := range pathParams {
		required := true
		params = append(params, config.EndpointParam{
			Name:        pp,
			In:          config.ParamInPath,
			Type:        config.ParamTypeString,
			Required:    &required,
			Description: fmt.Sprintf("Unique identifier for %s", ep.Entity),
		})
	}

	// 2. Query param для поиска (find/list)
	if ep.Op == config.OpFind || ep.Op == config.OpList {
		qp := ep.QueryParam
		if qp == "" {
			qp = ep.SearchField
		}
		if qp != "" {
			required := false
			desc := fmt.Sprintf("Text query to search %s by field '%s'. If omitted, returns all records.",
				ep.Entity, ep.SearchField)
			params = append(params, config.EndpointParam{
				Name:        qp,
				In:          config.ParamInQuery,
				Type:        config.ParamTypeString,
				Required:    &required,
				Description: desc,
			})
		}
	}

	return params
}

// extractPathParams извлекает {param_name} из URL-паттерна.
func extractPathParams(path string) []string {
	params := make([]string, 0)
	for {
		start := strings.Index(path, "{")
		if start < 0 {
			break
		}
		end := strings.Index(path[start:], "}")
		if end < 0 {
			break
		}
		params = append(params, path[start+1:start+end])
		path = path[start+end+1:]
	}
	return params
}
