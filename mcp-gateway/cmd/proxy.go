package main

import (
	"io"
	"net/http"
	"github.com/agent-tutor/mcp-gateway/internal/httpclient"
)

func manifestProxyHandler(client *httpclient.Client) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			tenantID = r.URL.Query().Get("tenant_id")
		}

		// Call data-service /mcp/manifest with the tenant ID
		req, _ := http.NewRequest("GET", client.BaseURL()+"/mcp/manifest", nil)
		if tenantID != "" {
			req.Header.Set("X-Tenant-ID", tenantID)
		}

		resp, err := http.DefaultClient.Do(req)
		if err != nil {
			http.Error(w, err.Error(), http.StatusInternalServerError)
			return
		}
		defer resp.Body.Close()

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(resp.StatusCode)
		io.Copy(w, resp.Body)
	}
}
