package runtime

import (
	"context"
	"database/sql"
	"log/slog"

	"github.com/trash2bin/helperium/data-service/internal/datasource"
)

// InstrumentedAdapter wraps datasource.Conn + datasource.Adapter into AdapterSubset.
// Replaces the server-level ConnAdapter so the same type lives in runtime/ where
// both server and other packages can use it without duplication.
type InstrumentedAdapter struct {
	Conn datasource.Conn
	Adp  datasource.Adapter
}

func (a *InstrumentedAdapter) QueryContext(ctx context.Context, query string, args ...any) (*sql.Rows, error) {
	if slog.Default().Enabled(ctx, slog.LevelDebug) {
		slog.Debug("DB Query", "sql", query, "args", args)
	}
	rows, err := a.Conn.QueryContext(ctx, query, args...)
	if err != nil {
		slog.Warn("DB Error", "error", err, "sql", query)
	}
	return rows, err
}

func (a *InstrumentedAdapter) PingContext(ctx context.Context) error {
	return a.Conn.PingContext(ctx)
}

func (a *InstrumentedAdapter) QuoteIdentifier(name string) string {
	return a.Adp.QuoteIdentifier(name)
}

func (a *InstrumentedAdapter) TranslatePlaceholder(index int) string {
	return a.Adp.TranslatePlaceholder(index)
}
