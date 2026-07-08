package server

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"testing"
)

func TestHealthEndpoint(t *testing.T) {
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}

	var body map[string]string
	if err := json.NewDecoder(w.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode response body: %v", err)
	}

	if body["status"] != "ok" {
		t.Errorf("expected status 'ok', got '%s'", body["status"])
	}
}

func TestHealthEndpointWithoutToken(t *testing.T) {
	s := New(Options{Addr: ":0", AdminToken: ""})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}

	var body map[string]string
	if err := json.NewDecoder(w.Body).Decode(&body); err != nil {
		t.Fatalf("failed to decode response body: %v", err)
	}

	if body["status"] != "ok" {
		t.Errorf("expected status 'ok', got '%s'", body["status"])
	}
}

// clearCORS unsets CORS_ALLOW_ORIGINS and returns a restore func.
func clearCORS() func() {
	prev, ok := os.LookupEnv("CORS_ALLOW_ORIGINS")
	os.Unsetenv("CORS_ALLOW_ORIGINS")
	if ok {
		return func() { os.Setenv("CORS_ALLOW_ORIGINS", prev) }
	}
	return func() {}
}

// withCORS sets CORS_ALLOW_ORIGINS and returns a restore func.
func withCORS(val string) func() {
	prev, ok := os.LookupEnv("CORS_ALLOW_ORIGINS")
	os.Setenv("CORS_ALLOW_ORIGINS", val)
	if ok {
		return func() { os.Setenv("CORS_ALLOW_ORIGINS", prev) }
	}
	return func() { os.Unsetenv("CORS_ALLOW_ORIGINS") }
}

func TestCORSAllowOrigin_Default(t *testing.T) {
	defer clearCORS()()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(w, req)

	got := w.Header().Get("Access-Control-Allow-Origin")
	if got != "*" {
		t.Errorf("Access-Control-Allow-Origin = %q, want %q", got, "*")
	}
}

func TestCORSAllowOrigin_Custom(t *testing.T) {
	defer withCORS("https://example.com")()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(w, req)

	got := w.Header().Get("Access-Control-Allow-Origin")
	if got != "https://example.com" {
		t.Errorf("Access-Control-Allow-Origin = %q, want %q", got, "https://example.com")
	}
}

func TestCORSAllowOrigin_Empty(t *testing.T) {
	defer withCORS("")()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/health", nil)
	router.ServeHTTP(w, req)

	got := w.Header().Get("Access-Control-Allow-Origin")
	if got != "*" {
		t.Errorf("Access-Control-Allow-Origin = %q, want %q", got, "*")
	}
}

func TestStaticFileSecurityHeaders(t *testing.T) {
	defer clearCORS()()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}

	csp := w.Header().Get("Content-Security-Policy")
	if csp == "" {
		t.Error("Content-Security-Policy header is missing on static file response")
	}

	xcto := w.Header().Get("X-Content-Type-Options")
	if xcto != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want %q", xcto, "nosniff")
	}
}

func TestStaticFileSecurityHeaders_JSFile(t *testing.T) {
	defer clearCORS()()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/app.js", nil)
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}

	csp := w.Header().Get("Content-Security-Policy")
	if csp == "" {
		t.Error("Content-Security-Policy header is missing on static JS file response")
	}

	xcto := w.Header().Get("X-Content-Type-Options")
	if xcto != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want %q", xcto, "nosniff")
	}
}

func TestStaticFileSecurityHeaders_CSSFile(t *testing.T) {
	defer clearCORS()()
	s := New(Options{Addr: ":0"})
	router := s.Router()

	w := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/styles.css", nil)
	router.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected status %d, got %d", http.StatusOK, w.Code)
	}

	csp := w.Header().Get("Content-Security-Policy")
	if csp == "" {
		t.Error("Content-Security-Policy header is missing on static CSS file response")
	}

	xcto := w.Header().Get("X-Content-Type-Options")
	if xcto != "nosniff" {
		t.Errorf("X-Content-Type-Options = %q, want %q", xcto, "nosniff")
	}
}
