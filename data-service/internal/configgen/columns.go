// Package configgen — анализ колонок и генерация фильтр-параметров.
//
// Все функции работают с config.EntityField, а не с datasource.Column.
// Это изолирует слой генерации конфига от низкоуровневого datasource.
package configgen

import (
	"fmt"
	"strings"

	"github.com/trash2bin/helperium/helperium-go/config"
)

// findSearchFieldFromEntity ищет name-поле в Entity.Fields.
// Критерий: тип string, название содержит name/first_name/last_name/title.
func findSearchFieldFromEntity(entity config.Entity) string {
	for _, f := range entity.Fields {
		lower := strings.ToLower(f.Name)
		if f.Type == config.FieldTypeString &&
			(lower == "name" ||
				strings.HasSuffix(lower, "_name") ||
				strings.HasSuffix(lower, "_title") ||
				strings.HasPrefix(lower, "name")) {
			return f.Name
		}
	}
	return ""
}

// findEnumColumnsFromEntity ищет enum-подобные поля в Entity.Fields.
// Возвращает имена полей, содержащие status/type/role/city/country.
func findEnumColumnsFromEntity(entity config.Entity) []string {
	var enums []string
	for _, f := range entity.Fields {
		if f.PrimaryKey != nil && *f.PrimaryKey {
			continue
		}
		if f.Type != config.FieldTypeString {
			continue
		}
		lower := strings.ToLower(f.Name)
		switch {
		case strings.Contains(lower, "status"),
			strings.Contains(lower, "type"),
			strings.Contains(lower, "role"),
			strings.Contains(lower, "city"),
			strings.Contains(lower, "country"):
			enums = append(enums, f.Name)
		}
	}
	return enums
}

// fieldTypeToParamTypeFromEntity конвертирует FieldType в ParamType.
func fieldTypeToParamTypeFromEntity(ft config.FieldType) config.ParamType {
	switch ft {
	case config.FieldTypeInt:
		return config.ParamTypeInt
	case config.FieldTypeFloat:
		return config.ParamTypeFloat
	case config.FieldTypeBool:
		return config.ParamTypeBool
	default:
		return config.ParamTypeString
	}
}

// buildFilterParamsFromEntity создаёт параметры фильтрации для find/list
// из Entity.Fields. searchCol — колонка для текстового поиска (LIKE),
// остальные — exact match.
func buildFilterParamsFromEntity(entity config.Entity, searchCol string) []config.EndpointParam {
	params := make([]config.EndpointParam, 0)
	nonPKFields := make([]config.EntityField, 0, len(entity.Fields))
	for _, f := range entity.Fields {
		if f.PrimaryKey != nil && *f.PrimaryKey {
			continue
		}
		nonPKFields = append(nonPKFields, f)
	}

	for _, f := range nonPKFields {
		paramRequired := false
		paramType := fieldTypeToParamTypeFromEntity(f.Type)

		if f.Name == searchCol {
			params = append(params, config.EndpointParam{
				Name:        f.Name,
				In:          config.ParamInQuery,
				Type:        config.ParamTypeString,
				Required:    &paramRequired,
				Description: fmt.Sprintf("Text search on '%s' (partial match).", f.Name),
			})
		} else if paramType == config.ParamTypeFloat || paramType == config.ParamTypeInt {
			params = append(params, config.EndpointParam{
				Name:        f.Name,
				In:          config.ParamInQuery,
				Type:        paramType,
				Required:    &paramRequired,
				Description: fmt.Sprintf("Filter by exact '%s' value.", f.Name),
			})
		} else if paramType == config.ParamTypeBool {
			params = append(params, config.EndpointParam{
				Name:        f.Name,
				In:          config.ParamInQuery,
				Type:        paramType,
				Required:    &paramRequired,
				Description: fmt.Sprintf("Filter by '%s' (true/false).", f.Name),
			})
		} else {
			params = append(params, config.EndpointParam{
				Name:        f.Name,
				In:          config.ParamInQuery,
				Type:        paramType,
				Required:    &paramRequired,
				Description: fmt.Sprintf("Filter by exact '%s' value.", f.Name),
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
