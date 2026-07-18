package runtime

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"strconv"
)

// MapRow сканирует одну строку *sql.Rows в map[string]any с публичными
// именами полей сущности и type coercion по entity.Fields.
//
// Сканирует напрямую в нативные Go-типы (int64, float64, bool, string) вместо
// sql.RawBytes, что устраняет лишнюю аллокацию на RawBytes→string и даёт
// правильные типы в JSON ({"id": 123} вместо {"id": "123"}).
func (b *Builder) MapRow(rows *sql.Rows, entity Entity) (map[string]any, error) {
	columns, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("runtime: MapRow: read columns: %w", err)
	}

	dest := make([]any, len(columns))
	for i := range dest {
		dest[i] = new(any)
	}

	if err := rows.Scan(dest...); err != nil {
		return nil, fmt.Errorf("runtime: MapRow: scan: %w", err)
	}

	result := make(map[string]any, len(columns))
	for i, col := range columns {
		var publicName string
		if name, ok := b.publicFor(entity, col); ok {
			publicName = name
		} else {
			continue // неизвестная колонка — пропускаем
		}

		ptr := dest[i].(*any)
		if ptr == nil || *ptr == nil {
			result[publicName] = nil
			continue
		}

		val := *ptr

		// Type coercion по конфигу поля
		ft := b.fieldTypeFor(entity, publicName)
		result[publicName] = coerceNative(val, ft)
	}
	return result, nil
}

// MapCustomQueryRow сканирует одну строку *sql.Rows в map[string]any
// для custom_query. При наличии маппинга сканирует в нативные Go-типы
// и приводит по ResultMappingField.Type. Без маппинга возвращает строки
// (как legacy-поведение).
func (b *Builder) MapCustomQueryRow(rows *sql.Rows, mapping map[string]ResultMappingField) (map[string]any, error) {
	columns, err := rows.Columns()
	if err != nil {
		return nil, fmt.Errorf("runtime: MapCustomQueryRow: read columns: %w", err)
	}

	dest := make([]any, len(columns))
	for i := range dest {
		dest[i] = new(any)
	}

	if err := rows.Scan(dest...); err != nil {
		return nil, fmt.Errorf("runtime: MapCustomQueryRow: scan: %w", err)
	}

	result := make(map[string]any, len(columns))
	for i, col := range columns {
		ptr := dest[i].(*any)
		if ptr == nil || *ptr == nil {
			result[col] = nil
			continue
		}

		val := *ptr

		// Type coercion по маппингу custom_query
		if mf, ok := mapping[col]; ok {
			result[col] = coerceNative(val, string(mf.Type))
		} else {
			// Без маппинга — legacy поведение: строки
			result[col] = fmt.Sprintf("%v", val)
		}
	}
	return result, nil
}

// MapRows итерирует rows и вызывает mapper для каждой строки.
func (b *Builder) MapRows(
	rows *sql.Rows,
	mapper func(*sql.Rows) (map[string]any, error),
	maxRows int,
) ([]map[string]any, error) {
	defer func() {
		_ = rows.Close()
	}()

	out := make([]map[string]any, 0)
	count := 0
	for rows.Next() {
		row, err := mapper(rows)
		if err != nil {
			return out, err
		}
		out = append(out, row)
		count++
		if maxRows > 0 && count >= maxRows {
			// early close: release connection back to pool immediately
			_ = rows.Close()
			break
		}
	}
	if err := rows.Err(); err != nil && err != io.EOF {
		return out, fmt.Errorf("runtime: MapRows: iterate: %w", err)
	}
	return out, nil
}

// coerceValue приводит строковое значение к типу из конфига.
// Сохранён для обратной совместимости (используется в тестах).
func coerceValue(val, typ string) any {
	if val == "" {
		return val
	}
	switch typ {
	case "int":
		if n, err := strconv.Atoi(val); err == nil {
			return n
		}
		return val
	case "float":
		if f, err := strconv.ParseFloat(val, 64); err == nil {
			return f
		}
		return val
	case "bool":
		if b, err := strconv.ParseBool(val); err == nil {
			return b
		}
		return val
	case "json":
		var js any
		if err := json.Unmarshal([]byte(val), &js); err == nil {
			return js
		}
		return val
	default:
		return val
	}
}

// coerceNative приводит нативное значение (int64, float64, bool, string)
// к ожидаемому типу из конфига. Если значение уже правильного типа —
// возвращает как есть. Это позволяет JSON-маршаллеру сериализовать
// числа как числа, а не строки.
func coerceNative(val any, typ string) any {
	if val == nil {
		return nil
	}

	switch typ {
	case "int":
		switch v := val.(type) {
		case int64:
			return v
		case float64:
			return int64(v)
		case string:
			if n, err := strconv.ParseInt(v, 10, 64); err == nil {
				return n
			}
		}
		return val

	case "float":
		switch v := val.(type) {
		case float64:
			return v
		case int64:
			return float64(v)
		case string:
			if f, err := strconv.ParseFloat(v, 64); err == nil {
				return f
			}
		}
		return val

	case "bool":
		switch v := val.(type) {
		case bool:
			return v
		case int64:
			return v != 0
		case float64:
			return v != 0
		case string:
			if b, err := strconv.ParseBool(v); err == nil {
				return b
			}
		}
		return val

	case "json":
		switch v := val.(type) {
		case string:
			var js any
			if err := json.Unmarshal([]byte(v), &js); err == nil {
				return js
			}
			return v
		case []byte:
			var js any
			if err := json.Unmarshal(v, &js); err == nil {
				return js
			}
			return string(v)
		}
		return val

	case "datetime", "date":
		// Pass through as-is — the adapter already returns a string or time.Time
		return val

	default:
		// string, datetime, date, unknown → конвертируем в строку
		switch v := val.(type) {
		case string:
			return v
		case fmt.Stringer:
			return v.String()
		default:
			return fmt.Sprintf("%v", v)
		}
	}
}

// publicFor — поиск публичного имени по имени колонки.
func (b *Builder) publicFor(entity Entity, column string) (string, bool) {
	for _, f := range entity.Fields {
		if f.Column == column {
			return f.Name, true
		}
	}
	return "", false
}

// fieldTypeFor — поиск типа поля по публичному имени.
func (b *Builder) fieldTypeFor(entity Entity, publicName string) string {
	for _, f := range entity.Fields {
		if f.Name == publicName {
			return f.Type
		}
	}
	return ""
}
