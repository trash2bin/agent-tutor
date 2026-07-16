package configgen

import (
	"fmt"
	"strings"

	"github.com/trash2bin/helperium/helperium-go/config"
)

// GenerateMCPTools creates compact MCP tools from endpoints with LLM-friendly descriptions.
func GenerateMCPTools(endpoints []config.Endpoint, entities []config.Entity) []config.MCPTool {
	entityMap := make(map[string]*config.Entity, len(entities))
	for i := range entities {
		entityMap[entities[i].Name] = &entities[i]
	}

	tools := make([]config.MCPTool, 0, len(endpoints))
	for _, ep := range endpoints {
		if ep.Op == config.OpBuiltinHealth || ep.Op == config.OpBuiltinStats {
			continue
		}

		var toolName, desc, displayName string
		ent := entityMap[ep.Entity]

		switch ep.Op {
		case config.OpGetByID:
			toolName = fmt.Sprintf("get_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Get a single %s by its ID. "+
					"Use after find_%s when you have a specific ID.",
				ep.Entity, ep.Entity)
			displayName = toolDisplayName(string(config.OpGetByID), ep.Entity)

		case config.OpFind:
			toolName = fmt.Sprintf("find_%s", ep.Entity)
			filters := compactFilterSummary(ent)
			if filters != "" {
				desc = fmt.Sprintf(
					"Search %s by name (partial match). Filters: %s. "+
						"If user asks about a type (e.g. 'muffler', 'brake pads'), "+
						"search categories first, then navigate to products.",
					pluralizeEntity(ep.Entity), filters)
			} else {
				desc = fmt.Sprintf(
					"Search %s by text query. Example: find_%s(name='query')",
					pluralizeEntity(ep.Entity), ep.Entity)
			}
			displayName = toolDisplayName(string(config.OpFind), ep.Entity)

		case config.OpList:
			toolName = fmt.Sprintf("list_%s", ep.Entity)
			desc = fmt.Sprintf(
				"List all %s. Supports filters and pagination. "+
					"Use when find_%s returns no results or you need all records.",
				pluralizeEntity(ep.Entity), ep.Entity)
			displayName = toolDisplayName(string(config.OpList), ep.Entity)

		case config.OpDistinct:
			toolName = fmt.Sprintf("distinct_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Get unique values for enum columns in %s. "+
					"Use to discover valid filter values.",
				pluralizeEntity(ep.Entity))
			displayName = toolDisplayName(string(config.OpDistinct), ep.Entity)

		case config.OpCount:
			toolName = fmt.Sprintf("count_%s", ep.Entity)
			desc = fmt.Sprintf(
				"Count %s matching filters. Returns {entity, count}.",
				pluralizeEntity(ep.Entity))
			displayName = toolDisplayName(string(config.OpCount), ep.Entity)

		case config.OpCustomQuery:
			// Short name: {child_plural}_by_{parent} (e.g. "products_by_brand")
			pathParts := strings.Split(strings.Trim(ep.Path, "/"), "/")
			parentName := ""
			if len(pathParts) >= 1 {
				parentName = pathParts[0]
			}
			if parentName == "" {
				parts := strings.Split(ep.QueryID, "_by_")
				if len(parts) == 2 {
					parentName = parts[1]
				}
			}
			childShort := ep.Entity
			for _, pfx := range DisplayPrefixes {
				childShort = strings.TrimPrefix(childShort, pfx)
			}
			parentShort := parentName
			for _, pfx := range DisplayPrefixes {
				parentShort = strings.TrimPrefix(parentShort, pfx)
			}
			toolName = fmt.Sprintf("%s_by_%s", pluralizeEntity(ep.Entity), parentShort)
			displayName = fmt.Sprintf("%s by %s", pluralizeEntity(ep.Entity), parentShort)

			// Strategic description: guides LLM workflow
			desc = fmt.Sprintf(
				"Get all %s for a given %s. "+
					"Use after find_%s to get the ID, then call this to list related %s. "+
					"Supports filters and pagination.",
				pluralizeEntity(ep.Entity), parentShort,
				parentName, pluralizeEntity(ep.Entity))
		}

		if toolName != "" {
			params := deriveToolParams(ep)
			tools = append(tools, config.MCPTool{
				Name:        toolName,
				DisplayName: displayName,
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
