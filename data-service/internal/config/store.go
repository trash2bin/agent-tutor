package config

import "context"

// Store — интерфейс хранилища конфигов.
//
// В фазе 3.2.a реализована только FileStore. DbStore (чтение из
// platform-БД для reload-режима) появится позже.
//
// Save запланирован на фазу 3.7 — пока возвращает ErrNotImplemented.
type Store interface {
	// Load читает конфиг из источника.
	// ctx используется для отмены (например, на старте сервера).
	Load(ctx context.Context) (*Config, error)

	// Save сохраняет конфиг в источник.
	// В фазе 3.2.a возвращает ErrNotImplemented.
	Save(ctx context.Context, cfg *Config) error
}

// FileStore — реализация Store поверх файловой системы.
//
// Простейший случай: путь фиксируется при создании, Load читает
// этот файл через Load(). Для reload-режима нужно будет создавать
// новый FileStore при каждом reload.
type FileStore struct {
	// Path — путь к config.json.
	Path string
}

// NewFileStore — конструктор FileStore.
func NewFileStore(path string) *FileStore {
	return &FileStore{Path: path}
}

// Load читает config.json через функцию Load() пакета.
func (f *FileStore) Load(_ context.Context) (*Config, error) {
	return Load(f.Path)
}

// Save возвращает ErrNotImplemented — запланировано на фазу 3.7.
func (f *FileStore) Save(_ context.Context, _ *Config) error {
	return ErrNotImplemented
}

// Compile-time interface compliance check.
var _ Store = (*FileStore)(nil)