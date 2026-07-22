package search

import (
	"fmt"
	"net/http"

	"github.com/trash2bin/helperium/data-service/internal/query"
	"github.com/trash2bin/helperium/helperium-go/config"
)

const (
	// maxSimpleValueLen — максимальная длина одного значения для simple-стратегии.
	maxSimpleValueLen = 200
)

// SimpleStrategy — backward-compatible search with LIKE on one field
// and exact match on others. Replicates the old FindHandler behaviour.
//
// LLM-facing name: simple_{entity}
// Uses entity's IDColumn for the search (LIKE), other fields for exact match.
type SimpleStrategy struct {
	idCol       string
	nameCol     string
	searchField string // public field name for LIKE search
}

// NewSimpleStrategy creates a SimpleStrategy.
// searchField is the public field name for LIKE search (e.g. "name").
func NewSimpleStrategy(idCol, nameCol, searchField string) *SimpleStrategy {
	return &SimpleStrategy{idCol: idCol, nameCol: nameCol, searchField: searchField}
}

func (s *SimpleStrategy) Name() string { return "simple" }

func (s *SimpleStrategy) EntityIDCol() string   { return s.idCol }
func (s *SimpleStrategy) EntityNameCol() string { return s.nameCol }

func (s *SimpleStrategy) ToolName(entity config.Entity) string {
	return "simple_" + entity.Name
}

func (s *SimpleStrategy) ToolDescription(entity config.Entity) string {
	return "Search " + entity.Name + " by field values. Uses LIKE search on the main text field and exact match on other fields."
}

func (s *SimpleStrategy) ToolParams(entity config.Entity) []config.EndpointParam {
	f := false

	params := make([]config.EndpointParam, 0, len(entity.Fields)+2)

	if s.searchField != "" {
		// Search field: LIKE search.
		params = append(params, config.EndpointParam{
			Name: s.searchField, In: config.ParamInQuery, Type: config.ParamTypeString, Required: &f,
			Description: "Search by " + s.searchField + " (partial match, LIKE).",
		})
	}

	for _, field := range entity.Fields {
		if field.Name == s.searchField {
			continue
		}
		if field.PrimaryKey != nil && *field.PrimaryKey {
			continue
		}
		params = append(params, config.EndpointParam{
			Name: field.Name, In: config.ParamInQuery,
			Type: fieldTypeToParamType(field.Type), Required: &f,
			Description: "Filter by exact " + field.Name + ".",
		})
	}

	params = append(params, config.EndpointParam{
		Name: "limit", In: config.ParamInQuery, Type: config.ParamTypeInt, Required: &f,
		Description: "Max results (1-1000, default: 50).",
	})
	params = append(params, config.EndpointParam{
		Name: "offset", In: config.ParamInQuery, Type: config.ParamTypeInt, Required: &f,
		Description: "Skip N results (for pagination).",
	})
	params = append(params, config.EndpointParam{
		Name: "sort_by", In: config.ParamInQuery, Type: config.ParamTypeString, Required: &f,
		Description: "Sort by field name. Prefix with \"-\" for descending.",
	})

	return params
}

// ParseRequest разбирает HTTP-запрос в QueryPlan для simple-стратегии.
func (s *SimpleStrategy) ParseRequest(r *http.Request, entity config.Entity, a Adapter) (*query.QueryPlan, error) {
	q := r.URL.Query()

	fieldMap := make(map[string]config.EntityField, len(entity.Fields))
	for _, f := range entity.Fields {
		fieldMap[f.Name] = f
	}

	var conditions []query.Condition

	for key, vals := range q {
		if len(vals) == 0 || vals[0] == "" {
			continue
		}
		val := vals[0]

		switch key {
		case "limit", "offset", "sort_by", "format":
			continue
		}

		f, ok := fieldMap[key]
		if !ok {
			continue
		}

		qName := a.QuoteIdentifier(f.Column)

		if key == s.searchField {
			// LIKE search on the search field (case-insensitive).
			if len(val) > maxSimpleValueLen {
				return nil, fmt.Errorf("search value for '%s' too long (%d chars, max %d)", key, len(val), maxSimpleValueLen)
			}
			escaped := a.QuoteString(val)
			conditions = append(conditions, query.Condition{
				Field:    qName,
				Operator: query.OpILike,
				Value:    "%" + escaped + "%",
				RawValue: true, // Already escaped, builder must not QuoteString again
			})
		} else {
			// Exact match on other fields.
			if f.Type == config.FieldTypeString && len(val) > maxSimpleValueLen {
				return nil, fmt.Errorf("search value for '%s' too long (%d chars, max %d)", key, len(val), maxSimpleValueLen)
			}
			typed, err := convertValue(val, f.Type)
			if err != nil {
				continue
			}
			conditions = append(conditions, query.Condition{
				Field:    qName,
				Operator: query.OpEq,
				Value:    typed,
			})
		}
	}

	// Default to standard limit=50 for simple strategy.
	limit := parseLimitParam(q, 50)

	return &query.QueryPlan{
		Select: selectClauseFull(entity, a),
		From:   a.QuoteIdentifier(entity.Table),
		Where:  conditions,
		Limit:  limit,
		Offset: parseOffset(q),
		Order:  parseOrder(q, entity, a),
		Format: query.FormatFull, // Simple returns full by default.
	}, nil
}
