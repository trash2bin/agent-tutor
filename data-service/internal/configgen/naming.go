package configgen

import (
	"fmt"
	"strings"

	"github.com/trash2bin/helperium/helperium-go/config"
)

// DisplayPrefixes are common table name prefixes to strip when generating
// human-readable display names for entities and tools.
// Change these when recompiling for a project that uses different prefixes
// (e.g. "wp_" for WordPress, "ce_" for Concrete5).
var DisplayPrefixes = []string{"catalog_", "auth_", "django_"}

// shortBusinessName отрезает префикс (catalog_, auth_, django_) и
// возвращает читаемое имя.
func shortBusinessName(name string) string {
	for _, pfx := range DisplayPrefixes {
		if strings.HasPrefix(name, pfx) {
			result := strings.TrimPrefix(name, pfx)
			if result == "cartitem" {
				return "Cart item"
			}
			if result == "sitesettings" {
				return "Settings"
			}
			return titleCase(result)
		}
	}
	return titleCase(name)
}

// titleCase capitalises the first letter of an ASCII string.
func titleCase(s string) string {
	if s == "" {
		return ""
	}
	return strings.ToUpper(s[:1]) + s[1:]
}

// shortColumnName делает snake_case колонку читаемой для LLM.
func shortColumnName(name string) string {
	// Простейшее преобразование: _ → пробел
	result := strings.ReplaceAll(name, "_", " ")
	// Если выглядит как FK (_id), подчёркиваем
	if strings.HasSuffix(name, "_id") {
		result = strings.TrimSuffix(result, " id") + " ID"
	}
	return result
}

// pluralizeEntity returns the English plural form of an entity name.
func pluralizeEntity(name string) string {
	special := map[string]string{
		"product":      "products",
		"brand":        "brands",
		"category":     "categories",
		"order":        "orders",
		"cart":         "cart",
		"cartitem":     "cart_items",
		"sitesettings": "settings",
		"user":         "users",
		"group":        "groups",
	}
	if p, ok := special[name]; ok {
		return p
	}
	short := name
	for _, prefix := range DisplayPrefixes {
		if strings.HasPrefix(short, prefix) {
			short = strings.TrimPrefix(short, prefix)
			break
		}
	}
	if p, ok := special[short]; ok {
		return p
	}
	if strings.HasSuffix(short, "s") {
		return short
	}
	if strings.HasSuffix(short, "y") {
		return short[:len(short)-1] + "ies"
	}
	return short + "s"
}

// toolDisplayName generates a human-readable English display name for a tool.
func toolDisplayName(op, entityName string) string {
	short := entityName
	for _, prefix := range DisplayPrefixes {
		if strings.HasPrefix(short, prefix) {
			short = strings.TrimPrefix(short, prefix)
			break
		}
	}
	plural := pluralizeEntity(entityName)
	switch op {
	case string(config.OpGetByID):
		return fmt.Sprintf("%s by ID", short)
	case string(config.OpFind):
		return fmt.Sprintf("Find %s", short)
	case string(config.OpList):
		return fmt.Sprintf("All %s", plural)
	case string(config.OpCount):
		return fmt.Sprintf("Count %s", plural)
	case string(config.OpDistinct):
		return fmt.Sprintf("Distinct %s", plural)
	default:
		return ""
	}
}
