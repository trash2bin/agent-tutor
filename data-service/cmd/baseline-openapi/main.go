// Baseline OpenAPI exporter.
//
// Утилита для фазы 3.0: сохраняет текущий /openapi.json работающего
// data-service в файл. Используется как baseline для drift-теста
// (после фазы 3.2 OpenAPI начнёт генерироваться из конфига, и этот
// baseline станет эталоном «как было до»).
//
// Использование:
//
//	go run ./cmd/baseline-openapi/ -out specs/openapi.baseline.json
//	go run ./cmd/baseline-openapi/ -out specs/openapi.baseline.json -url http://127.0.0.1:8084
//
// Файл-выход кладётся в specs/ и коммитится как эталон.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

func main() {
	outPath := flag.String("out", "specs/openapi.baseline.json", "путь к выходному файлу")
	url := flag.String("url", "http://127.0.0.1:8084/openapi.json", "URL эндпоинта /openapi.json")
	flag.Parse()

	client := &http.Client{Timeout: 30 * time.Second}

	resp, err := client.Get(*url)
	if err != nil {
		log.Fatalf("GET %s: %v", *url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		log.Fatalf("GET %s: unexpected status %d", *url, resp.StatusCode)
	}

	// Парсим как generic JSON для pretty-print.
	var raw any
	if err := json.NewDecoder(resp.Body).Decode(&raw); err != nil {
		log.Fatalf("decode JSON: %v", err)
	}

	pretty, err := json.MarshalIndent(raw, "", "  ")
	if err != nil {
		log.Fatalf("marshal JSON: %v", err)
	}

	// Убеждаемся, что директория существует.
	dir := filepath.Dir(*outPath)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		log.Fatalf("mkdir %s: %v", dir, err)
	}

	if err := os.WriteFile(*outPath, append(pretty, '\n'), 0o644); err != nil {
		log.Fatalf("write %s: %v", *outPath, err)
	}

	fmt.Printf("baseline OpenAPI saved to %s (%d bytes)\n", *outPath, len(pretty))
}
